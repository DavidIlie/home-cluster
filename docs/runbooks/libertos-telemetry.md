# Libertos telemetry queries

The `Apps / Bostan` folder (`apps-bostan`) contains `libertos-overview` and
`libertos-browser`. These are operational dashboards. They do not count people,
record sessions, or provide a billing/security ledger.

## Identity contract

| Field | Value |
| --- | --- |
| Project ID / service namespace | `libertos` |
| Next server | `libertos-web` |
| Future browser / Faro app_name | `libertos-browser` |
| Convex actions, including embedded Eve jobs | `libertos-convex` |
| Kubernetes namespace | `bostan-libertos` |
| Workloads | `bostan-libertos-app`, `bostan-libertos-convex`, `bostan-libertos-pdf` |
| Repository | `https://github.com/BostanEnterprise/libertos` |

These identities match the application onboarding contract. They do not imply
that the telemetry has been deployed.
Server/Convex `service.version` and `vcs.ref.head.revision`, and browser
`app_version`, must be the full deployed 40-character Git SHA. Container image
rows remain separate from telemetry releases. Convex's runtime image version is
not a Libertos application commit. Eve jobs run inside Convex and do not have a standalone service or deployment.

Browser collection is disabled pending an owner consent decision. The existing
necessary/reading/marketing consent categories do not authorize Faro diagnostics.
Keep browser panels empty until the application PR defines and implements that
policy and confirms its error-event schema. The reserved browser route uses its
own exact-origin public ingest project for
`https://libertos.org` and `https://www.libertos.org`. The corporate
`bostanenterprise.com` project is separate. Public routing keys are not secrets
or proof of payload identity. Servers export to private Alloy. Consent,
redaction, and sampling belong to the application integration; no replay,
product autocapture, or credentials belong in client configuration.

## Read-only investigation

1. Fix a UTC time window. In `prometheus-davidapps-cluster`, run the dashboard's
   availability/restarts queries for `namespace="bostan-libertos"`.
2. Check `telemetry_gateway_requests_total{project="libertos"}` grouped by
   `route,result` in that same datasource.
3. In `prometheus-home-cluster`, run throughput, p50/p95, and error queries for
   `service="libertos-web"`. These count sampled server spans, not users.
4. In `victoria-logs`, start with the exact namespace stream filter or the Faro
   `app_name:="libertos-browser"` prefix in the checked-in dashboard. Keep errors
   limited to 200. Do not quote raw messages before redacting them.
5. Open a non-empty `trace_id` with the shared Grafana datasource link. Tempo's
   reverse link searches that trace in VictoriaLogs. A scoped TraceQL search is
   `{ resource.service.name = "libertos-web" }`.
6. For backend outcomes, the Convex span name carries the closed operation and
   outcome: `eve.job.<capability> <outcome>` and
   `stripe.webhook <event type> <outcome>`. The `Backend outcomes` tables sum
   `traces_spanmetrics_calls_total{service="libertos-convex"}` by `span_name`
   over the selected range. They are bounded by the closed vocabularies in
   `packages/convex/convex/telemetryContract.ts`. They are not a job or payment
   ledger; use Convex and Stripe for a single job or payment.
7. Query releases using the target-info `job` label, not the span metric's
   `service` label:

```promql
max by (job, service_version) (
  traces_target_info{
    davidapps_project_id="libertos",
    job=~"libertos/libertos-web|libertos/libertos-convex",
    service_version=~"[0-9a-f]{40}"
  }
)
```

Only the SHA field links to
`https://github.com/BostanEnterprise/libertos/commit/FULL_GIT_SHA`.
Server target metadata can retain a retired release until it expires; compare
its observation window with deployment state. Browser releases list versions
observed in the selected range; an old open tab
can continue sending an old version. They do not prove the active deployment.

The canonical query contracts are the dashboard JSON targets. Replace Grafana
macros with bounded durations for API calls. Browser Web Vitals are p75 by
release and time bucket, without user IDs, raw paths, or session labels.

## Verification boundary

Read-only inspection on 2026-10-04 found available replicas for web (3), Convex
(1), and PDF (2). No matching release target-info series existed. New telemetry
panels are explicitly event-dependent. Missing data may mean pending rollout,
consent, sampling, ingest failure, or retention. It is not proof of zero errors.

After the user deploys the coordinated changes, verify a server request carries
the deployed SHA, find a redacted server error with its trace, and open both the
trace and exact commit links. Browser verification remains blocked until the
owner approves a consent policy and the application implements it. Dedicated Bostan
Grafana access is a separate GitOps change with a query allowlist; shared folder
visibility does not constrain shared datasource queries.

Default error rows omit raw messages from both shared and dedicated dashboards;
existing web/Convex/PDF logs may predate application redaction. Investigate text
only with the appropriate backend access and redact it before quoting. No
browser error panel is provisioned until the consent and event contract exist.
