# Bostan developer Grafana

`https://bostan-monitoring.davidapps.dev` is a dedicated Grafana OSS instance
for the Bostan Enterprise team. It shows only the `Apps / Bostan` dashboards
(folder uid `apps-bostan`, the same uid as the shared Grafana). Its only
datasource endpoint is `bostan-query-gateway`, which forwards a query only when
the query is byte-identical to a template in these dashboard files. It is the
Kidays design (`../grafana-kidays/README.md`); the gateway contract is the
davidapps-auth runbook `docs/runbooks/query-gateway.md`.

## What decides access

| Question | Answer |
| --- | --- |
| Who can sign in | DavidApps application `grafana-bostan` (closed OIDC). The group `Bostan Enterprise Employees` (`group_c85f5639-38a3-4f55-8061-65066da59e85`) holds an allow grant with role `member`. The group has `email_domain = bostanenterprise.com`: every verified @bostanenterprise.com member of the DavidApps organization joins it automatically. |
| What they can do | `Viewer` for everyone, the owner included. No login form, basic auth, Explore, alerting, snapshots, public dashboards, Live, or plugin admin. |
| What they can query | Only the gateway allowlist, compiled from `app/dashboards/*.json` at gateway start. |
| How long a revoked person keeps access | Up to 10 minutes plus any running request (`login_maximum_lifetime_duration`); `auto_login` then re-checks the grant at `id.davidapps.dev`. |

## Data in scope

`app/gateway/config.json` is the boundary every template must prove at load.

| Source | Scope |
| --- | --- |
| Kubernetes metrics (`prometheus-davidapps-cluster`) | `namespace` or `exported_namespace` in `bostan-enterprise`, `bostan-libertos`, `bostan-swish` |
| ingress-nginx metrics | `exported_namespace` above, `host` in the Bostan hostnames |
| Libertos span metrics (`prometheus-home-cluster`) | `service` in `libertos-web`, `libertos-convex`; `davidapps_project_id="libertos"` |
| Discord bot (`prometheus-home-cluster`) | `deployment="bostan-discord-bot"` |
| Bostan Cloudflare tunnel | `tunnel_id` of Bostan's own tunnel |
| Application logs (VictoriaLogs) | streams of the three Bostan namespaces, and `default/bostan-discord-bot` on home-cluster |
| Edge logs (VictoriaLogs) | Bostan's own cloudflared and external-dns streams, and ingress-nginx access logs restricted by an exact `vhost:in(...)` list |

A new Bostan hostname needs both the `host` list and the nginx `vhost:in(...)`
prefix updated, in the config and in the dashboards that filter by it. A new
namespace needs a `namespace`/`exported_namespace` value and a stream prefix.
The gateway refuses to start if a dashboard query falls outside this scope.

## Dashboards

`bostan-overview` (all sites), `bostan-edge` (nginx, Cloudflare tunnel,
external-dns), `bostan-front`, `bostan-employee-hub`, `bostan-swish`,
`libertos-overview` and `bostan-discord-bot`. Request panels use ingress-nginx
metrics and access logs; Libertos also has server span metrics. The shared
Grafana provisions byte-identical copies in `Apps / Bostan`. Change both
together and keep panels free of variables and Explore links, which the
gateway refuses.

Log panels aggregate by low-cardinality fields only. VictoriaLogs runs with a
1 GiB limit, and latency quantiles or user-agent groupings over a day of
ingress logs exhaust it; take latency from the nginx histograms instead.

## Files

- `app/dashboards/*.json`: read by Grafana and the gateway.
- `app/gateway/config.json`: datasource uid to backend mapping, label scope,
  and limits. It never contains a query.
- `app/*-secret.sops.yaml`: written only by the audited non-model mover in
  davidapps-auth (`scripts/davidapps-sops-import.mjs`, target
  `grafana-bostan`). Never decrypt these into a prompt or a log.

## Network

The same policies as Kidays: the Grafana pod is reachable only from the
external ingress-nginx controller and reaches only the gateway, DNS and HTTPS to
`id.davidapps.dev`, `grafana.com` and `storage.googleapis.com`. The gateway is
reachable only from the Grafana pod and reaches only the two Prometheus
instances and VictoriaLogs.

The hostname is routed by the home tunnel
(`network/external/cloudflared/configs/config.yaml`). Its DNS record is the
`home-tunnel` DNSEndpoint in davidapps-cluster, which owns the davidapps.dev
zone.
