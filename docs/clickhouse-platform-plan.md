# ClickHouse platform plan

## Decision

Move the ZeroCut ClickHouse workload to `davidapps-cluster` as **one shard with
two data replicas**, not three data replicas. Run three small ClickHouse Keeper
members for quorum, one on each Kubernetes node. Keep hot data on local ZFS/NVMe
PVCs and send independent backups to the TrueNAS-backed S3 endpoint.

This gives node-level data redundancy without paying for a third full copy:

```text
                         davidapps-cluster

  electron                  neutron                   proton
  ┌────────────────┐        ┌────────────────┐        ┌──────────────┐
  │ ClickHouse A   │<------>│ ClickHouse B   │        │ Keeper 3    │
  │ full replica   │        │ full replica   │        │ quorum only │
  │ local NVMe/ZFS │        │ local NVMe/ZFS │        │ small PVC   │
  └───────┬────────┘        └───────┬────────┘        └──────┬───────┘
          │ Keeper 1                 │ Keeper 2                │
          └──────────────────────────┴─────────────────────────┘
                                      │
                                      ▼
                       TrueNAS S3: versioned backups
```

Normal open-source `ReplicatedMergeTree` stores a full copy on each data
replica. Three compute pods sharing one remote copy is a SharedMergeTree-style
architecture and is a ClickHouse Cloud/BYOC design, not the right self-hosted
primitive for this cluster. Two replicas are the sensible availability/capacity
tradeoff here.

## Current state (2026-08-17)

| Workload | Location | Layout | MergeTree data | Rows | Notes |
| --- | --- | --- | ---: | ---: | --- |
| ZeroCut | home-cluster, `databases/clickhouse-0` | One pod, hostPath | ~0.5 MB | 3,132 | Donations and event/API tables; no replica |
| Plausible | home-cluster, `observability/plausible-clickhouse-0` | One pod, hostPath | ~39.6 MB | 2,240,729 | Primarily `events_v2`, `sessions_v2`, and ingest counters |

Both instances already expose ClickHouse's native Prometheus endpoint on port
9363 through a ServiceMonitor. The shared filesystem gauges report the whole
analytics SSD, so per-instance storage accounting must use
`TotalBytesOfMergeTreeTables` instead of `DiskUsed_default`.

Plausible currently contains a tiny, apparently stale three-row
`zerocut.donations` table. Treat it as a migration-audit item; do not delete it
until ownership and retention are confirmed.

## Runtime topology

- Use the mature Altinity ClickHouse Operator for the first production move.
  The newer official ClickHouse operator is promising and documents the exact
  two-replica/three-Keeper shape, but its API is still `v1alpha1`; canary it
  before making donation analytics depend on it.
- Create one `ClickHouseInstallation` with one shard and two replicas.
- Enforce required pod anti-affinity/topology spread so replicas cannot land on
  the same node. Pin each Keeper member to a distinct node as well.
- Give each data replica an expandable `superfastzfs` PVC, initially 100–200 GiB.
  The current dataset is tiny, so sizing is for growth and merge headroom rather
  than existing bytes.
- Give Keeper members small persistent volumes; Keeper metadata is not the
  analytical dataset.
- Publish a stable in-cluster service name and keep credentials in SOPS. The app
  should never depend on an individual pod or node address.
- Use replicated databases/tables and explicit macros. Do not use a single PVC
  mounted by multiple ClickHouse servers.

## Hot, cold, and backup storage

### Hot data

Keep active parts on both local NVMe/ZFS replicas. Local storage is what makes
queries and merges fast; replication handles one node or disk failure.

Do not cold-tier ZeroCut donation/payment facts initially. The data is tiny and
financial aggregates should remain quick to validate. Stripe/Postgres remains
the financial source of truth; ClickHouse is the operational analytics copy.

If append-only browser/API/event tables become large, add a ClickHouse storage
policy with an S3 cold volume and table-specific TTLs such as “local for 30–90
days, then move old parts to cold.” Cold storage is a capacity feature, not a
backup.

### Backups

Run `clickhouse-backup` next to the cluster and write to a dedicated,
versioned TrueNAS S3 bucket/prefix. Keep backup and optional cold-data prefixes
separate so retention or lifecycle policy cannot erase both accidentally.

Initial policy:

- incremental backup every hour;
- full backup daily;
- retain 48 hourly, 30 daily, and 12 monthly recovery points;
- protect the bucket with versioning/object lock when available;
- perform and record a restore drill every month;
- alert on backup age only after the backup job exports a reliable success
  timestamp.

This protects against node loss and accidental table mutation. It does not give
site-level disaster recovery while TrueNAS remains in the same home; add an
encrypted off-site copy later if that risk matters.

Target objectives after a tested restore are RPO <= 1 hour and RTO <= 2 hours.

## Migration course

1. **Observe first.** Keep the two current instances on the new ClickHouse
   dashboard for at least several days and capture query rate, memory, parts,
   errors, and growth baselines.
2. **Provision davidapps-cluster.** Install the operator, three Keepers, two data
   replicas, PodDisruptionBudgets, anti-affinity, ServiceMonitor, SOPS secrets,
   NetworkPolicies, and backup object-store configuration.
3. **Prove recovery before data.** Back up and restore a disposable table, then
   simulate loss of one data pod and one Keeper member.
4. **Recreate the ZeroCut schema.** Generate reviewed DDL using replicated
   engines. Preserve ordering, partition keys, TTLs, materialized views, and
   dictionaries; never blindly restore single-node engine paths.
5. **Shadow-copy and verify.** Copy the tiny dataset into the new cluster,
   compare per-table row counts, sums for monetary fields, min/max timestamps,
   and sampled records. Take a final source backup.
6. **Cut over briefly.** Pause writes, copy the delta, repeat verification, then
   change the SOPS-managed application endpoint to the stable service. Keep the
   old instance read-only for a rollback window.
7. **Retire deliberately.** After the rollback window and a successful restore
   drill, remove the old workload while retaining its final backup under a
   documented expiry policy.

Plausible can use the same platform later, but should be a separate database,
credential, quota, backup policy, and preferably a separate installation if its
ingest growth could interfere with ZeroCut's financial analytics.

## Observability contract

The `ClickHouse Instances` dashboard in `Infrastructure / Databases` covers both
current instances and becomes the template for the future cluster. Required
signals are:

- scrape availability, uptime, restarts, pod placement, CPU, memory, network,
  filesystem I/O, and limits;
- query/select/insert rates, failed-query ratio, average query time, and rows or
  bytes processed;
- MergeTree bytes, rows, parts, maximum partition part count, merges, mutations,
  delayed inserts, and mark-cache effectiveness;
- all errors plus memory-limit, too-many-parts, timeout, and network errors;
- replication queue, replica delay/read-only state, Keeper health, and backup
  freshness after the replicated cluster exists.

The last group cannot be honest until the davidapps-cluster resources and backup
job exist, so it is a required acceptance gate for the migration rather than a
placeholder panel today.

## References

- [Official ClickHouse Kubernetes Operator announcement](https://clickhouse.com/blog/clickhouse-kubernetes-operator)
- [Official operator documentation](https://github.com/ClickHouse/clickhouse-operator)
- [Altinity ClickHouse Operator](https://github.com/Altinity/clickhouse-operator)
- [`clickhouse-backup`](https://github.com/Altinity/clickhouse-backup)
- [ClickHouse hot/cold observability storage guidance](https://clickhouse.com/resources/engineering/observability-cost-optimization-playbook)

## Security follow-up

A credential-bearing ClickHouse URL was surfaced by a local diagnostic command
during reconnaissance. Do not copy it into issues, commits, dashboards, or chat.
Rotate that credential before the migration and update the SOPS-managed clients;
credential rotation is intentionally not performed by this planning change.
