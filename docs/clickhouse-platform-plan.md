# ZeroCut ClickHouse platform plan

## Decision

Move **only ZeroCut** to `davidapps-cluster` using the final large-scale shape
from the beginning: three shards, two replicas per shard, and three ClickHouse
Keeper members. Six ClickHouse server pods are placed cyclically so every node
stores, merges, and queries two different shard replicas.

```text
                    davidapps-cluster

  electron                neutron                 proton
  ┌───────────────┐       ┌───────────────┐       ┌───────────────┐
  │ shard 1 / r1  │<----->│ shard 1 / r2  │       │               │
  │ shard 3 / r2  │<----------------------------->│ shard 3 / r1  │
  │               │       │ shard 2 / r1  │<----->│ shard 2 / r2  │
  │ Keeper 1      │       │ Keeper 2      │       │ Keeper 3      │
  └───────────────┘       └───────────────┘       └───────────────┘
        local ZFS/NVMe           local ZFS/NVMe          local ZFS/NVMe
```

For a logical hot dataset of size `L`:

- the cluster stores `2L`, not `3L`;
- each node stores roughly `2L/3`, not the complete dataset;
- a distributed read sends one shard of work to each of three replicas, so all
  three nodes participate;
- loss of any one node leaves one complete replica of every shard.

The rejected one-shard/two-replica design left the third node as Keeper-only.
One shard with three replicas would use all nodes but put all bytes on all
nodes. Three shards with one replica would store only `L`, but losing one node
would make one third of the dataset unavailable.

Do not start at one shard and promise to reshard later. ZeroCut is tiny now, so
this is the cheapest time to choose and test the permanent sharding key. A
future one-to-three-shard rewrite would need temporary double capacity,
network-copy every historical part, reconcile both layouts, and cut over writes
when the data is hardest to move.

## Current state (2026-08-17)

| Workload | Location | Layout | MergeTree data | Rows | Migration scope |
| --- | --- | --- | ---: | ---: | --- |
| ZeroCut | home-cluster, `databases/clickhouse-0` | One pod, hostPath | ~0.5 MB | 3,132 | Move to davidapps-cluster |
| Plausible | home-cluster, `observability/plausible-clickhouse-0` | One pod, hostPath | ~39.6 MB | Explicitly excluded |

The three davidapps nodes each expose about 24 allocatable CPU cores, 123 GiB
of allocatable memory, and roughly 3 TiB free on `superfastzfs`. Actual CPU and
memory use are low, but declared CPU requests are already close to allocatable;
the initial ClickHouse pods need small CPU requests and realistic memory
requests until existing request inflation is corrected.

Both current instances already expose native ClickHouse Prometheus metrics.
Per-instance storage must use `TotalBytesOfMergeTreeTables`; the ClickHouse
disk gauges describe the shared host filesystem and cannot attribute bytes to
one database.

Plausible contains a tiny, apparently stale three-row `zerocut.donations`
table. Treat it as an audit item; do not delete it as part of this migration.

## Runtime topology

- Use the mature Altinity ClickHouse Operator for the first production move.
  Canary the newer official operator separately while its API remains young.
- Create six server pods: two per node, placed exactly as the topology above.
  Required shard anti-affinity prevents both replicas of a shard from sharing a
  node. A PodDisruptionBudget must not pretend Kubernetes can preserve quorum
  during a physical two-node loss.
- Run one persistent Keeper member per node. Keeper paths for the ZeroCut
  installation are independent of every other ClickHouse workload.
- Give every server pod its own expandable `superfastzfs` PVC. Never mount one
  ReadWriteOnce PVC into several ClickHouse servers.
- Publish a stable service/load-balancing endpoint. Applications address the
  service or a Distributed table, never a pod or node.
- Set `internal_replication=true`: a Distributed insert chooses one replica of
  the target shard and ReplicatedMergeTree copies it to the second replica.
- Use a stable, well-distributed event sharding key from day one. The key must
  be derived from immutable bounded fields and tested for creator/tenant skew;
  changing it later is a full data rewrite.
- Keep `skip_unavailable_shards=0` for finance and correctness dashboards.
  Partial results are allowed only in an explicitly labeled exploratory view.

Small donation/payment facts remain authoritative in PostgreSQL/Stripe.
ClickHouse is a read model. Initially keep those ClickHouse tables on the same
3x2 topology with no TTL; avoid a second logical 1x3 cluster unless a concrete
three-copy requirement justifies its extra DDL, Keeper paths, and operations.
Small dimensions should use dictionaries or bounded replicated reference data,
not force the massive event table into a three-copy layout.

## Data lifecycle

### Hot and warm native data

Keep recent append-only event/API/browser parts on local NVMe/ZFS with two
replicas. Start with a conservative local boundary such as 90 days and tune it
from measured query age, compression, merge pressure, and restore time rather
than an arbitrary byte threshold.

Phase one deliberately does **not** use a ClickHouse S3 disk. Standard S3 disks
need unique replica prefixes and can duplicate objects; a local filesystem cache
is disposable; and two replicas using one TrueNAS/MinIO endpoint are not two
storage failure domains. Unsafe or experimental zero-copy replication is not a
foundation for the donation analytics platform.

If measured queries later require transparent access between 90 days and the
archive boundary, canary an S3-disk policy separately and document its exact
object layout, cache-loss behavior, and TrueNAS-outage behavior before enabling
TTL movement.

### Single-copy archive

Old sealed partitions leave ReplicatedMergeTree entirely and become one logical
Parquet archive on the TrueNAS S3 endpoint. `s3Cluster` spreads reads of those
objects across the three ClickHouse nodes, so all nodes can compute on archived
data without storing it locally.

Archive is a controlled handoff, not a blind TTL:

1. Wait through a table-specific late-event window and seal one time partition.
2. Export deterministic, reasonably sized Parquet objects under a versioned
   schema/time/shard path.
3. Publish an immutable manifest containing schema version, archive boundary,
   source shard, file list, object hashes, row count, min/max event time, and
   table-specific checksums or sums.
4. Read the objects back through `s3Cluster` and reconcile the manifest against
   the native partition.
5. Mark the manifest complete atomically. Only a completed manifest permits
   `DROP PARTITION ON CLUSTER` from both replicas.
6. Route hot/archive union queries through a single recorded cutoff: native
   data is `>= cutoff`, archive data is `< cutoff`. This prevents gaps and
   double counting.

Late data older than the cutoff goes into a correction file/new manifest
version; it never silently reopens a dropped native partition. If TrueNAS is
unavailable, archive reads fail visibly, export pauses, and native partitions
must not be dropped.

Donation/payment facts and their reconciliation materializations have no
archive TTL. Their source-of-truth retention belongs to PostgreSQL/Stripe.

### Backup is separate

Archive is not backup. Use `clickhouse-backup` for native tables, DDL, and
metadata in a dedicated versioned/object-locked bucket or prefix. Protect the
archive separately with TrueNAS snapshots and an independently retained copy,
ideally encrypted off-site. Warm data, archive, and backup on one TrueNAS
chassis remain one site-level failure domain no matter how many bucket names
exist.

Initial native-backup policy:

- hourly incremental and daily full recovery points;
- retain 48 hourly, 30 daily, and 12 monthly points;
- monthly scratch restore with per-table rows and monetary checksums;
- alert on backup age only after the job exports a trustworthy success time;
- delete and recover an archive object during a restore drill, not only test a
  healthy read.

Target objectives after drills are RPO <= 1 hour and RTO <= 2 hours for native
analytics. Archive-object recovery has its own measured objective.

## Write and failure semantics

Use a PostgreSQL outbox or another durable replay source for events that matter.
The worker marks an event delivered only after ClickHouse acknowledges the
chosen insert policy. This keeps ClickHouse out of the financial transaction
boundary and makes backpressure safer than dropping analytics.

| Failure | Reads | Writes | Required behavior |
| --- | --- | --- | --- |
| One ClickHouse pod | Full | Full after replica routing | Rebuild from its shard peer; alert on replica queue/delay |
| One node | Full, one replica per shard remains | `insert_quorum=2` pauses affected shards; replayable backlog waits | Do not lower quorum silently; restore redundancy first |
| Two nodes | At least one shard missing | Stop | Keeper loses quorum; alert and restore, never show partial finance |
| One Keeper | Full | Full | Remaining 2/3 Keeper quorum continues |
| TrueNAS/S3 | Native hot/warm full | Native writes continue; archive handoff pauses | Archive queries fail visibly; no partition deletion |
| Archive object deleted/corrupt | Affected historical range fails | Native unaffected | Recover from independent retention and revalidate manifest |

`insert_quorum=2` favors correctness: a one-node outage can pause writes for
shards whose second replica is gone. The durable outbox absorbs that outage.
If a future event class deliberately chooses quorum one for availability, its
RPO risk and replay contract must be explicit and must not apply to revenue or
donation reconciliation.

## Migration course

1. **Observe and classify.** Record current table DDL, partition/order keys,
   query age, growth, late events, materialized views, row counts, and monetary
   checksums. Assign every table to native-no-TTL, native-then-archive, or
   rebuildable-derived.
2. **Provision the final topology.** Install the operator, six ClickHouse pods,
   three Keepers, six PVCs, topology rules, ServiceMonitor, SOPS secrets,
   NetworkPolicies, and backup configuration.
3. **Prove the empty platform.** Drain each node in turn. Verify every shard is
   readable, Keeper stays 2/3, a replayable insert follows the chosen quorum
   policy, replica queues recover, and no pod pair violates placement.
4. **Create final DDL.** Use ReplicatedMergeTree local tables plus Distributed
   front doors with the permanent sharding key. Preserve ordering, partitions,
   TTL exclusions, materialized views, dictionaries, and bounded labels.
5. **Shadow-copy by partition.** Copy the tiny source, then compare shard
   balance, per-table rows, monetary sums, min/max timestamps, and sampled
   records. Exercise an archive manifest and `s3Cluster` read on disposable
   data.
6. **Cut over briefly.** Pause source writes, copy the delta, repeat checks, and
   change the SOPS-managed application endpoint. Keep the old instance
   read-only through the rollback window.
7. **Retire deliberately.** Remove the old workload only after one node-loss
   test, one native restore, one archive-object recovery, and expiry of the
   rollback window.

Plausible remains on home-cluster. It is not bundled into this operator,
topology, credentials, quotas, storage lifecycle, or migration.

## Observability acceptance gates

The ClickHouse dashboard must add the future cluster's shard/replica topology,
not merely reuse single-instance panels:

- bytes, rows, parts, inserts, queries, and merge pressure by shard and replica;
- shard-balance ratio and per-node `2L/3` distribution;
- replica queue size, absolute delay, read-only state, lost parts, and fetches;
- Keeper quorum/session health;
- Distributed insert failures, quorum failures, and replay-backlog age;
- local PVC free space alert below 30 percent;
- archive cutoff/manifest age, export verification, object count/bytes, and last
  successful archive-object recovery;
- native backup age and last successful scratch restore.

Before accepting migration, drain each node and verify full row counts through
the Distributed tables. The two-node-loss test must alert and refuse partial
financial results. No donation/payment table may have an archive/delete TTL.

## References

- [Official ClickHouse scaling material](https://clickhouse.com/company/events/scaling-clickhouse)
- [Official ClickHouse Kubernetes Operator announcement](https://clickhouse.com/blog/clickhouse-kubernetes-operator)
- [Altinity ClickHouse Operator](https://github.com/Altinity/clickhouse-operator)
- [`clickhouse-backup`](https://github.com/Altinity/clickhouse-backup)
- [ClickHouse hot/cold storage guidance](https://clickhouse.com/resources/engineering/observability-cost-optimization-playbook)
- [ClickHouse S3 integration](https://clickhouse.com/integrations/amazon_s3)

## Security follow-up

A credential-bearing ClickHouse URL was surfaced by a local diagnostic command
during reconnaissance. Do not copy it into issues, commits, dashboards, or
chat. Rotate that credential before migration and update the SOPS-managed
clients; credential rotation is intentionally not performed by this planning
change.
