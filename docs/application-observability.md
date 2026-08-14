# Application observability

This stack deliberately does not use PostHog. It keeps application telemetry in the existing home-cluster observability systems:

- Prometheus stores Kubernetes metrics, application OTLP metrics, and Tempo-derived span metrics.
- VictoriaLogs stores Kubernetes container logs, OTLP logs, and Faro browser logs.
- Tempo stores distributed traces and produces span-metrics and service-graph series.
- Grafana is the shared UI and correlates traces with VictoriaLogs by `trace_id`.

## Shared endpoints

| Producer | Endpoint | Protocol |
| --- | --- | --- |
| Workloads in davidapps-cluster | `alloy.observability.svc.cluster.local:4317` | OTLP/gRPC |
| Workloads in davidapps-cluster | `http://alloy.observability.svc.cluster.local:4318` | OTLP/HTTP |
| Browsers | `https://telemetry.davidapps.dev/collect` | Grafana Faro |
| davidapps Alloy | `192.168.100.98:4317` | OTLP/gRPC to home Tempo |
| Agents on the home LAN | `http://192.168.100.98:3200/api/mcp` | Tempo MCP |

The Faro endpoint is deployed before any application SDK is connected. Its CORS allowlist contains only the current ZeroCut, MB Retrofit, and Kidays production origins.

## Instrumentation contract

Every project integration should set these OpenTelemetry resource attributes consistently:

| Attribute | Value |
| --- | --- |
| `service.name` | Stable deployed service name, such as `zerocut` |
| `service.namespace` | Product name, such as `zerocut`, `mbretrofit`, or `kidays` |
| `service.version` | Full Git commit SHA for the deployed image |
| `deployment.environment.name` | `production` |
| `k8s.namespace.name` | Kubernetes namespace |
| `k8s.deployment.name` | Kubernetes Deployment name |

Logs emitted through OTLP should carry valid span and trace context. Alloy promotes the service, deployment, and Kubernetes resource attributes to VictoriaLogs stream labels. Tempo and Grafana use `service.version` to make the active release and commit discoverable.

Use the standard error semantic conventions: record the exception on the active span and set its status to error. Do not place secrets, authorization headers, request bodies, email addresses, or other personal data in span attributes or logs.

## Provisioned Grafana scopes

Grafana provisions these folders and dashboard UIDs:

| Folder | Dashboard UID | Current scope |
| --- | --- | --- |
| `Apps / Fleet` | `apps-fleet` | Cross-project health, resources, logs, latency, and errors |
| `Apps / ZeroCut` | `zerocut-overview` | `personal-projects/zerocut` |
| `Apps / MB Retrofit` | `mbretrofit-overview` | Main and Zenzefi deployments |
| `Apps / Kidays` | `kidays-overview` | Web and Convex backend deployments |

Kubernetes availability, resource, image, restart, and container-log panels work before application instrumentation. Span latency, span error-rate, and active-commit panels populate after the project sends traces with the resource contract above.

## Agent queries

The local Codex configuration exposes three read-only MCP servers to new agent sessions:

- `observability_grafana`: dashboards, alerts, PromQL, and datasource metadata. It uses a Grafana Viewer service account and starts with `--disable-write`.
- `observability_logs`: read-only LogsQL access to VictoriaLogs.
- `observability_traces`: Tempo trace search and retrieval.

Useful requests include:

- “Query the last hour of error logs for `zerocut` and correlate any `trace_id` with Tempo.”
- “Compare p95 span latency for the current and previous `service.version` of `mbretrofit-tools`.”
- “Show firing project alerts, then inspect the affected deployment's restarts and logs.”
- “Find traces for `kidays-fr-app` slower than two seconds and group them by route.”

The MCP servers are intentionally read-only. Changes to dashboards, alert rules, retention, or collectors remain GitOps changes in this repository or `davidapps-cluster`.
