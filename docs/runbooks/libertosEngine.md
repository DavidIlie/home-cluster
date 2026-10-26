# Libertos engine observability

Open the [engine pipeline](https://monitoring.davidapps.dev/d/libertos-engine-pipeline),
[archive sweep](https://monitoring.davidapps.dev/d/libertos-archive-sweep),
[cost](https://monitoring.davidapps.dev/d/libertos-cost), or
[briefing drill-down](https://monitoring.davidapps.dev/d/libertos-briefing-drilldown)
in the existing Apps / Bostan folder. Use a trace id from the admin or a trace
table to inspect a run. No data means unknown, not zero or healthy.

## Where telemetry lives

Grafana runs in home-cluster's observability namespace. The Grafana HelmRelease
downloads these JSON files from this repository's main branch at pod startup;
the dashboard sidecar is disabled. Changing a JSON file alone does not restart
Grafana. Bump the existing `davidapps.dev/url-dashboards-revision` pod annotation
when updating dashboard JSON without changing its provisioning entries.

Libertos Convex sends traces to davidapps-cluster Alloy at
`http://alloy.observability.svc.cluster.local:4318/v1/traces`. Alloy forwards
traces to home-cluster Tempo and logs to VictoriaLogs. Grafana datasource UIDs:

| UID | Data |
| --- | --- |
| `tempo` | Traces, including `libertos-convex` and `libertos-web` |
| `prometheus-home-cluster` | Tempo-generated span metrics |
| `prometheus-davidapps-cluster` | Direct OTLP metrics forwarded by Alloy |
| `victoria-logs` | Structured OTLP logs and cluster container logs |

There is no Loki datasource. VictoriaLogs accepts Loki ingestion, but dashboard
queries use LogsQL through the VictoriaLogs plugin.

## Current evidence and limits

The current Convex contract is
`BostanEnterprise/libertos/packages/convex/convex/telemetryContract.ts`.
It emits terminal job spans named `eve.job.<capability> <outcome>`, including
`eve.job.briefing succeeded`, `eve.job.briefing failed`, and
`eve.job.archive_sweep succeeded`. `libertos.outcome` carries the outcome;
`error.type=job_failed` marks failed jobs. Job duration begins at creation and
includes queue time and retries. Each job export currently has its own trace id.

Tempo emits `traces_spanmetrics_calls_total` and
`traces_spanmetrics_latency_bucket`, `_count`, and `_sum`, with `service`,
`span_name`, `span_kind`, and `status_code` labels. These metrics count exported
terminal spans, not active jobs or deliveries. Current latency buckets end at
16.384 seconds; their quantiles are unsuitable for long engine steps.

The drill-down matches the exact trace id and limits logs to diagnostic fields.
It omits raw messages, which may contain private content. Correlated engine logs
are not exported yet. Do not interpret an empty log panel as proof of no activity.

## Alert delivery

The standalone `prometheus-home-cluster` evaluates `libertosRules.yaml`, where
Tempo writes the data. An operator `PrometheusRule` would be evaluated by the
other Prometheus instance and would not see these series.

Alerts go to the existing home-cluster
`kube-prometheus-stack-alertmanager:9093`. Its existing `email` receiver handles
warning and critical alerts. No new contact point or credentials are introduced.

`LibertosEngineErrorRateHigh` fires after five minutes with more than 10% failed
jobs in a rolling ten-minute window, at least five failures, and at least ten
completed jobs. It excludes Stripe and web spans. Open failed engine traces,
identify the capability, and inspect its job in the admin before retrying.
Absence of traffic does not trigger this rate alert.

## Engine contract and collector dependency

Names and labels match the [engine contract at 4f0f30a](https://github.com/BostanEnterprise/libertos/blob/4f0f30aebbaf6966a721ca1e916b91fa3ae755da/docs/telemetryEngine.md).
The pipeline and cost dashboards keep the names in constant variables;
the engine datasource is selectable:

- `libertos_engine_step_duration_seconds`, with `_bucket` for quantiles
- `libertos_engine_step_failures_total`
- `libertos_engine_step_cost_usd_total`
- `libertos_engine_briefings_total`, with `outcome=on_time|late|short`
- `libertos_engine_stuck_total`, with `step` and `reason`

Duration labels are step/status/tier, failures and cost use step/tier, and
briefing outcomes use outcome/tier. Failure counters have no error_code label;
the Tempo breakdown groups `libertos.engine.step` and
`libertos.engine.error_code` span attributes. Engine spans are named
`libertos.engine.<step>`. The duration histogram has buckets through 3600 seconds.

Cost uses step as the layer label. Its default UTC-aligned range and one-day query interval show the
counter increase for the day preceding each midnight point. Counter increases
are estimates, not the accounting ledger. The on-time chart is a rolling
24-hour share at web publication, not a per-reader-morning view. Outcomes are
mutually exclusive: short takes precedence over late. Manual publications with
enough items count as on_time. Email and push delivery are separate. Cost counters
come from committed ledgers and first settlements; shared costs use tier=shared.

`LibertosBriefingLateOrShort` uses the canonical outcome counter. It is
evaluated by the standalone `prometheus-davidapps-cluster` in home-cluster,
which receives Alloy's direct metrics, and routes to the same existing email
receiver. `libertosDeliveryRules.yaml` holds this rule in one place.

Direct metrics depend on [davidapps-cluster PR #527](https://github.com/DavidIlie/davidapps-cluster/pull/527).
The producer stays on delta. The three Alloy frontends route metrics with
`service.namespace=libertos` to one dedicated Alloy replica. Its `Recreate`
strategy prevents overlapping accumulators. A delta-to-cumulative processor
retains inactive streams for 72 hours, bounded to 20,000 streams, before the
Prometheus exporter. Start-timestamp zero ingestion preserves the first delta
and the first sample after a reset. Only the dedicated writer enables
experimental components. Traces, logs and other applications keep their paths.

The singleton trades availability for one cumulative writer. Frontend queues
retry for up to five minutes, but queues, converter state and the remote-write
WAL are ephemeral. Concurrent or delayed actions can still arrive out of order;
monitor converter error labels. These are monitoring estimates, not accounting
records. Keep both PRs draft pending review and verify actual ingestion after
Flux deploys them. No cluster changes were applied by hand.

Tempo duration and error-code panels query stored spans directly and do not
need OTLP metric conversion. The archive short-cell panel uses the gauge from
[noThinCells at ea293d0](https://github.com/BostanEnterprise/libertos/blob/ea293d003ea6919fdf7642b8007b4cba7ea4c3bf/packages/convex/convex/archiveCoverageTelemetry.ts).
It remains provisional until that producer is deployed. The OTLP name is
`libertos_engine_thin_cells`, but Alloy 1.21.2 exports
`libertos_engine_thin_cells_ratio` because its unit is `1`. A local end-to-end
probe verified that name. Values are cell counts grouped by kind and primary
reason. The chart shows audit samples without extending them across days;
missing samples do not mean zero short cells.

The following missing semantics still block their corresponding panels and
alerts. TODO panels remain visible. Do not substitute completed jobs for
delivery state or a stuck-event counter for active-job age.

| Signal | Required semantics | Alert |
| --- | --- | --- |
| Stuck work | Active job age since last progress, refreshed periodically and cleared on terminal state | Active briefing older than 900 seconds; do not add a second 15-minute hold |
| Morning sweep | Daily UTC deadline and last successful completion, including a heartbeat when no sweep starts | At or after 04:00Z, today's sweep has not completed; distinguish missing telemetry |
| Delivery mornings | Scheduled/manual distinction and reader-morning cohorts; email/push outcomes separate from web publication | Exact morning on-time rate beyond the implemented publication alert |
| Spend | Authoritative USD spend since UTC midnight and configured ceiling, plus layer/tier | Today's spend above the same day's ceiling; missing ceiling remains unknown |
| Archive coverage | Feeds polled, articles stored, usable full-text articles, start/completion times; short-cell gauge deployment still unverified | Sweep completeness and deadline diagnosis |
| Trace logs | Diagnostic structured log fields sharing the deterministic delivery/generation trace id | Logs alongside the implemented trace inspection |

Keep ids in traces/logs, not metric labels. Never export reader text, email,
interests, prompts, or private lane wording. Costs must be counted once at the
accounting boundary, including shared sweep costs without copying them onto each
reader. Tiers come from the canonical model plan.

## Validate and roll back

Build the Grafana app and standalone Prometheus home-cluster directories with
`kustomize build`. Run the pinned Flux Local command from
`.github/workflows/flux-local.yaml` and `promtool check config` with the mounted
rule file. Validate dashboard JSON and query syntax against the configured datasource
versions. This repository has no pnpm lint command.

Merge through normal review and let Flux reconcile. Never apply these files by
hand. After reconciliation, verify dashboard provisioning, rule health and the
Alertmanager target without sending a test notification. A local render is not
proof of deployment or a production replay. To roll back, revert the PR and let
Flux restore the previous dashboard provisioning and Prometheus configuration.
