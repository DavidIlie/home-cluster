# Application observability

This stack deliberately does not use PostHog. It keeps application telemetry in the existing home-cluster observability systems:

- The DavidApps Prometheus stores Kubernetes metrics, gateway metrics, and application OTLP metrics.
- The home Prometheus stores Tempo health and Tempo-derived span metrics.
- VictoriaLogs stores Kubernetes container logs, OTLP logs, and Faro browser logs.
- Tempo stores distributed traces on the analytics SSD and produces span-metrics and service-graph series.
- Grafana is the shared UI and correlates traces with VictoriaLogs by `trace_id`.

## Shared endpoints

| Producer | Endpoint | Protocol |
| --- | --- | --- |
| Workloads in davidapps-cluster | `alloy.observability.svc.cluster.local:4317` | OTLP/gRPC |
| Workloads in davidapps-cluster | `http://alloy.observability.svc.cluster.local:4318` | OTLP/HTTP |
| Browsers and mobile clients | Project-specific randomized gateway host | Faro or OTLP/HTTP |
| davidapps Alloy | `192.168.100.98:4317` | OTLP/gRPC to home Tempo |
| Agents on the home LAN | `http://192.168.100.98:3200/api/mcp` | Tempo MCP |

The public gateway is deployed before any application SDK is connected. Each project gets an unrelated hostname, a public routing key, an exact browser-origin allowlist, and rate limits. See [the agent query protocol](./runbooks/application-telemetry-agent-queries.md#project-registry) for the registry. The former `telemetry.davidapps.dev` endpoint is only a migration fallback.

Public gateway routes are stateless: they validate and forward data to Alloy, which then sends metrics to Prometheus, logs to VictoriaLogs, and traces to Tempo. The gateway creates no PVC. Tempo continues to use the retained `tempo-analytics` volume on `/var/mnt/mdadm-analytics-storage/tempo/data`; VictoriaLogs and the standalone Prometheus instances keep their existing analytics-SSD paths.

Alloy parses Faro records before forwarding them, so fields such as `app_name`, `app_version`, `app_environment`, `page_url`, `session_id`, and browser or custom context are indexed individually in VictoriaLogs. Faro `traceID` and `spanID` values are also normalized to the shared `trace_id` and `span_id` field names used by Grafana correlation links. Set the Faro app version to the deployed Git commit SHA when each project is connected.

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

### Server, rendering, and dependency telemetry

Every web project should expose enough bounded telemetry to answer the same operational questions:

- server request rate, error ratio, and p50/p95/p99 latency;
- stable route-template latency and error throughput;
- framework phases such as route rendering, API execution, middleware, metadata, and server-component work;
- aggregate database, cache, queue, and external-provider latency and failures;
- runtime CPU, memory, replicas, restarts, pod placement, and active release;
- browser Web Vitals, frontend errors, and exact release comparison;
- product-specific business signals such as revenue, donations, subscriptions, or jobs.

Automatic client spans are not safe dashboard dimensions by default: their span names can contain raw URLs, SQL, query parameters, identifiers, or user-controlled values. Dependency and query instrumentation must emit bounded semantic attributes such as `dependency.system`, `operation`, and an allowlisted `query.name`. Never use raw SQL, URLs, request bodies, emails, payment IDs, user IDs, or arbitrary error messages as metric labels.

### Per-project dashboard suite

Use the ZeroCut folder as the reference implementation for each instrumented project:

| Dashboard | Required scope |
| --- | --- |
| `Overview` | Grouped business, revenue, reliability, browser, runtime, release, logs, and traces |
| `Revenue & donations` or equivalent | Project-specific business movements and outcomes, with currencies kept separate |
| `Server & rendering` | RED metrics, route and framework-phase performance, aggregate dependencies, resources, and correlated errors |
| `Browser experience` | Web Vitals, client signal volume, frontend errors, and browser release |
| `Runtime & deployments` | Desired/ready/updated replicas, pods, nodes, CPU, memory, restarts, image, and commit |

All dashboards in a project folder share a project tag and expose a Grafana dashboard-link dropdown so the selected time range follows the user between scopes. Keep the overview concise enough for triage; focused dashboards carry the detailed breakdowns.

## Provisioned Grafana scopes

Infrastructure dashboards use a consistent folder taxonomy instead of the Grafana root folder:

| Folder | Scope |
| --- | --- |
| `Kubernetes` | Cluster, API server, namespaces, nodes, pods, persistent volumes, CoreDNS, and pod logs |
| `Network / UniFi` | Access points, clients, switches, sites, gateways, and DPI |
| `Network / Kubernetes` | Cilium, ingress NGINX, request handling, and Cloudflare tunnels |
| `Infrastructure / Hosts` | Proxmox, iDRAC, node-exporter, disks, and GPU |
| `Infrastructure / Storage` | TrueNAS and analytics-storage health |
| `Infrastructure / Databases` | CloudNativePG and Dragonfly |
| `Observability / Platform` | Prometheus and platform-level observability |
| `Observability / Telemetry` | OTLP/Faro gateway, Tempo, logs, and telemetry pipeline |
| `AI / Operations` | AI gateway usage and cost |
| `CI / GitHub Actions` | Runner fleet and workflow infrastructure |

Grafana provisions these folders and dashboard UIDs:

| Folder | Dashboard UID | Current scope |
| --- | --- | --- |
| `Apps / Fleet` | `apps-fleet` | Cross-project health, resources, logs, latency, and errors |
| `Apps / ZeroCut` | `zerocut-overview` | Grouped ZeroCut overview |
| `Apps / ZeroCut` | `zerocut-revenue` | Platform payments and supporter-to-creator donations |
| `Apps / ZeroCut` | `zerocut-reliability` | Server, rendering, dependency, resource, log, and trace performance |
| `Apps / ZeroCut` | `zerocut-browser` | Browser Web Vitals, client signals, errors, and release |
| `Apps / ZeroCut` | `zerocut-runtime` | Kubernetes placement, rollout, resources, image, and commit |
| `Apps / MB Retrofit` | `mbretrofit-overview` | Main and Zenzefi deployments |
| `Apps / Kidays` | `kidays-overview` | Web and Convex backend deployments |
| `Observability / Telemetry` | `telemetry-platform` | Gateway outcomes, Tempo ingestion health, Faro volume, and gateway errors |

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

For a repeatable source-selection and correlation workflow, use the [application telemetry agent query protocol](./runbooks/application-telemetry-agent-queries.md).
