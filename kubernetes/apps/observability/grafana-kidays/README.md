# Kidays developer Grafana

`https://kidays-monitoring.davidapps.dev` is a dedicated Grafana OSS instance
for Kidays developers. It shows only the `Apps / Kidays` dashboards
(folder uid `afv5x41dfcw00c`, the same uid as the shared Grafana). Its only
datasource endpoint is `kidays-query-gateway`, which forwards a query only when
the query is byte-identical to a template in these dashboard files. The design,
request contracts, and canary gates are in the davidapps-auth runbook
`docs/runbooks/query-gateway.md`.

## What decides access

| Question | Answer |
| --- | --- |
| Who can sign in | DavidApps application `grafana-kidays` (closed). The owner approves the `Kidays Team` group grant; nothing here grants anyone. |
| What they can do | `Viewer` for everyone, the owner included. No login form, basic auth, Explore, alerting, snapshots, public dashboards, Live, or plugin admin. |
| What they can query | Only the gateway allowlist, compiled from `app/dashboards/*.json` at gateway start. |
| How long a revoked person keeps access | Up to 10 minutes, plus the duration of any request already running. The session lifetime is absolute (`login_maximum_lifetime_duration`, anchored on the session's `created_at` in Grafana v12.3.10). After it, `auto_login` re-checks the grant at `id.davidapps.dev`. Revocation is not per request, and the live interactive owner OIDC flow has not been verified yet. |

## Files

- `app/dashboards/kidays-*.json`: copies of the canonical dashboards in
  `../grafana/app/dashboards/` with identical queries and dedicated navigation.
  The only difference is that the "Trace search (shared admin Grafana only)"
  link is removed, because this instance has no Tempo and its viewers hold no
  shared-Grafana grant. Grafana and the gateway both read these files. When the
  canonical dashboards change, copy them and remove that link again. The
  gateway refuses to start on an unscoped query, a dashboard variable, or any
  Explore link, since this config lists no foreign Explore origin.
- `app/gateway/config.json`: datasource uid to backend mapping, label scope,
  and limits. It never contains a query.
- `app/*-secret.sops.yaml`: written only by the audited non-model mover in
  davidapps-auth (`scripts/davidapps-sops-import.mjs`). Do not re-run it for
  this client, because the source reference has been consumed. Never decrypt
  these files into a prompt or a log.

## Startup

Grafana installs `victoriametrics-logs-datasource@0.32.0` in the background
after it starts (`[plugins] preinstall`, the only async entry). A
`preinstall_sync`-only configuration installs nothing in Grafana v12.3.10: the
installer service is disabled whenever the async list is empty
(`plugininstaller/service.go` `IsDisabled`), and `disable_plugins` has removed
every default. `/api/health` answers before the install finishes, so the pod
becomes Ready only when both of these hold:

- `plugins/victoriametrics-logs-datasource/plugin.json` names that id at
  exactly version `0.32.0`;
- `/api/health` succeeds.

The plugins directory is on the persistent volume, so later starts find 0.32.0
already installed and skip the download. Liveness stays the chart's
`/api/health` check, so an install in progress never restarts the pod. If the
download fails, the pod stays NotReady and receives no traffic; check the
Grafana log for `Installing plugin`.

## Network

| Pod | Ingress | Egress |
| --- | --- | --- |
| `grafana-kidays` | external ingress-nginx controller pods only (`network` namespace and `app.kubernetes.io/{name=ingress-nginx,instance=external-ingress-nginx,component=controller}`) on 3000 | gateway 8080, DNS, and HTTPS to `id.davidapps.dev` (OIDC), `grafana.com`, and `storage.googleapis.com` (pinned `victoriametrics-logs-datasource@0.32.0` background preinstall only) |
| `kidays-query-gateway` | `grafana-kidays` only, on 8080 | DNS, `prometheus-{davidapps,home}-cluster` 9090, `victoria-logs` 9428 |

The hostname is routed by the home tunnel
(`network/external/cloudflared/configs/config.yaml`). The DNS record for
`kidays-monitoring.davidapps.dev` must point at the home tunnel, following the
same pattern as `monitoring.davidapps.dev`.

## Image pin

Both gateway containers use the published immutable image
`ghcr.io/davidilie/davidapps-auth-query-gateway@sha256:e8a40a8a7329b7d3659669744d3b45a35770de399349be544676a3592ed039e9`.
It was published from the merged davidapps-auth PR215 by its isolated query-gateway workflow.

Readiness also checks the public plugin module route. In Grafana v12.3.10 this route returns 404 until the plugin exists in the registry; merely finding plugin.json on disk is insufficient during extraction. This check uses no authenticated API or credentials.
