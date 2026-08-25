# Altinity ClickHouse canary

This stack installs Altinity Operator 0.27.3 and a disposable one-shard,
one-replica ClickHouse 26.3 installation with one Keeper. It does not select,
mount, or modify the existing ZeroCut source ClickHouse.

The canary includes a pinned `clickhouse-backup` 2.8.0 sidecar, a dedicated
bucket-scoped MinIO credential, six-hour incremental backups, weekly full
backups, authenticated backup metrics, and operator/ClickHouse/Keeper metrics.
Its versioned bucket is `clickhouse-zerocut-canary-backups`.

## Hardware boundary

`home-cluster` has one node and only `openebs-hostpath`. It cannot prove
multi-node placement, ZFS retention, or PVC expansion. This canary proves the
operator, Keeper, SOPS, network, metrics, and logical backup/restore path. The
empty davidapps target must prove the ZFS and placement gates before cutover.

## Acceptance

After review and merge, reconcile in dependency order:

```sh
flux reconcile kustomization altinity-clickhouse-operator -n databases --with-source
flux reconcile kustomization clickhouse-canary -n databases
kubectl -n databases get chi,chk,pods,pvc
```

The ClickHouse and Keeper pods must be ready, both PVCs must be bound, and the
operator, Keeper, ClickHouse, and backup targets must be up in Prometheus.

Create disposable data with the canary user, then prove a remote backup and a
mapped restore without overwriting the source database:

```sh
pod="$(kubectl -n databases get pod -l clickhouse.altinity.com/chi=zerocut-canary -o jsonpath='{.items[0].metadata.name}')"
password="$(kubectl -n databases get secret zerocut-canary-credentials -o jsonpath='{.data.password}' | base64 -d)"
kubectl -n databases exec "$pod" -c clickhouse -- clickhouse-client --user zerocut_canary --password "$password" --multiquery --query "CREATE DATABASE IF NOT EXISTS backup_probe; CREATE TABLE IF NOT EXISTS backup_probe.events (id UInt64, value String) ENGINE=MergeTree ORDER BY id; INSERT INTO backup_probe.events VALUES (1, 'canary');"
unset password
backup="canary-manual-$(date -u +%Y%m%dT%H%M%SZ)"
kubectl -n databases exec "$pod" -c clickhouse-backup -- clickhouse-backup create_remote '--tables=backup_probe.*' "$backup"
kubectl -n databases exec "$pod" -c clickhouse-backup -- clickhouse-backup restore_remote --restore-database-mapping=backup_probe:backup_probe_restore "$backup"
kubectl -n databases exec "$pod" -c clickhouse -- clickhouse-client --query "SELECT count(), groupArray(value) FROM backup_probe_restore.events"
```

Acceptance requires a count of one from the restored database and the backup
visible in MinIO. Do not delete the canary until retained-PVC behavior and an
operator upgrade have also been observed.
