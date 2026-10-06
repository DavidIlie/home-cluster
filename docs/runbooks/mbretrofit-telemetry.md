# MB Retrofit telemetry

The shared administrator dashboard is `/d/mbretrofit-overview`. It covers the
`mbretrofit-tools` and `mbretrofit-tools-zenzefi` deployments in
`personal-projects`. Its repository is
[DavidIlie/mbretrofit-tools](https://github.com/davidilie/mbretrofit-tools).

## Identity and ingestion

The existing gateway project is `mbretrofit-tools`. Browser Faro ingestion uses
`https://v4m8kp2d.mbretrofit.it/collect`. Allowed origins are
`https://mbretrofit.it`, `https://www.mbretrofit.it`,
`https://zenzefi.davidapps.dev` and `https://unlockecu.davidapps.dev`.
The public routing key belongs in the application deployment contract and is
not an authentication credential. Server workloads export directly to private
Alloy. Never put its endpoint or credentials in a browser bundle.

Server telemetry queries use `mbretrofit-tools`. Browser panels use
`mbretrofit-tools-web`, confirmed by the application onboarding contract.
Zenzefi uses a separate image and is outside this instrumentation PR. Application
resources must include `davidapps.project.id=mbretrofit-tools` and the same full
40-character deployed SHA in `service.version` and commit identity. The
resource namespace is `mbretrofit-tools`; the release query uses project ID and
`job` so it does not assume a Kubernetes namespace is an OTel namespace.

Do not infer a full SHA from the short image tag, use a moving branch as the
release, or pin a runtime SHA independently of the deployed image. Zenzefi Kubernetes health panels remain available independently of application
instrumentation. The separate MB Retrofit landing service and its
`.ro` / `.es` origins are outside this dashboard's contract.

## Query contract

| Signal | Datasource UID | Scope |
| --- | --- | --- |
| Replica availability, restarts, CPU, memory, images | `prometheus-davidapps-cluster` | `personal-projects`, two named deployments |
| Browser gateway outcomes | `prometheus-davidapps-cluster` | `telemetry_gateway_requests_total{project="mbretrofit-tools"}` |
| Server span rate, errors, p50 and p95 | `prometheus-home-cluster` | `service="mbretrofit-tools"`, `span_kind="SPAN_KIND_SERVER"`, `span_name!~"GET /api/health.*"` |
| Node runtime: event-loop delay and utilization, heap, GC, active resources | `prometheus-davidapps-cluster` | `service_name="mbretrofit-tools"`, by per-process `instance` |
| Resource releases | `prometheus-home-cluster` | `traces_target_info`, project ID, full SHA only |
| Server errors | `victoria-logs` | Exact application names in `personal-projects` |
| Browser error classifications, LCP, INP, CLS | `victoria-logs` | Alloy Faro `app_name="mbretrofit-tools-web"` |
| Traces | `tempo` | Explicit service allowlist in TraceQL |

Span throughput counts sampled server spans, not billable requests or people.
Kubernetes probes `GET /api/health`, and every server-span panel excludes that
span name. Until the cluster probe change lands, probes hit `/` and still count
as `GET /` page requests. Request errors are internal-kind spans
(`mbretrofit.request_error`), so they never inflate the server-span counts.
Runtime panels use the closed metric set in the application's
`runtime-metrics.ts`, remote-written by Alloy with unit suffixes; each process
has a random `service.instance.id`, shown as `instance`.
Latency panels use histogram buckets grouped by service and `le`. Gateway
outcomes group only by route and result; acceptance confirms the upstream
receiver response, not backend persistence. Web Vitals use the established
Faro numeric fields `lcp`, `inp` and `cls`, with p75 over 15-minute buckets.
No panel groups by user, vehicle, session, URL or error message. Resource SHA
is used only for release inspection, not span metric dimensions.

In Grafana Explore, use the release query below with the home Prometheus:

```promql
max by (job, service_version) (
  traces_target_info{
    davidapps_project_id="mbretrofit-tools",
    service_version=~"[0-9a-f]{40}"
  }
)
```

`target_info` identifies services through `job`, not the span metric `service`
label. Click the `service_version` field to open the exact repository commit.
A recently retired release can persist until target metadata expires. Compare
its observation window with the running image panel and deployment time before
calling it current.

Search slow server traces with:

```traceql
{ resource.service.name = "mbretrofit-tools" && span:kind = server && span:duration > 2s }
```

Constrain a release by adding
`resource.service.version = "FULL_DEPLOYED_GIT_SHA"`. Browser resource fields come from an untrusted client and are diagnostic
evidence only. The browser does not emit traces.

Recent server error rows retain `trace_id`. Expand that field and follow the
VictoriaLogs datasource's **View trace** link. Tempo's log link searches the
same trace ID. A direct read-only LogsQL lookup is:

```logsql
_stream:{cluster="davidapps-cluster",k_namespace_name="personal-projects"}
app:in("mbretrofit-tools","mbretrofit-tools-zenzefi")
trace_id:="TRACE_ID"
| fields _time, _msg, app, trace_id
| sort desc
| limit 200
```

Use an explicit UTC time window. Browser errors use the event `mbretrofit.browser_error` with bounded
`event_data_error_class` and `event_data_route`. The dashboard displays those
classifications without messages or trace links; the browser emits no traces,
console logs, exception logs, sessions or stored identifiers. Review log messages
for personal data before quoting them elsewhere.

## Verification and privacy

The application bakes the full SHA from `GIT_COMMIT_SHA` into server and browser
resources. GitOps must not override that build identity. The operational browser
collector skips Global Privacy Control, Do Not Track and credential-bearing
pages. On 2026-10-06 the owner authorized this operational browser collection
without a new consent banner in the merge-all release instruction, recorded in
application PR #159. The existing privacy guards remain required.
Browser telemetry must preserve redaction and consent, with no replay, product
autocapture, identifiers, form contents or secrets. An empty panel can reflect
absent instrumentation, denied consent, sampling, an idle service or retention.
It is not a zero error count or a successful end-to-end check.

After a separately authorized rollout, compare gateway outcomes, a known
release in Tempo, Faro measurements in VictoriaLogs, server span metrics and
the commit link. Read-only query parsing alone cannot prove that an application
emits the proposed contract. The general investigation sequence lives in
[application-telemetry-agent-queries.md](application-telemetry-agent-queries.md).
