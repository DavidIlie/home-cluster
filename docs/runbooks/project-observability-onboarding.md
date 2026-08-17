# Project observability onboarding

Use this checklist for Kidays and every project after it. ZeroCut is the reference implementation; do not copy its product-specific metric names into another project.

## 1. Register stable identity

Choose one project ID and use it everywhere. Keep service names stable across releases.

| Layer | Required identity |
| --- | --- |
| Kubernetes | `app.kubernetes.io/name`, Deployment name, namespace, and eventually `davidapps.io/observability-scope: application` |
| OpenTelemetry | `service.name`, `service.namespace`, `service.version`, `deployment.environment.name`, `davidapps.project.id` |
| Browser or mobile | Project gateway host, public routing key, exact allowed origins, app name, and full release SHA |
| Source control | `vcs.repository.url.full` and `vcs.ref.head.revision` |

`service.version` and browser `app_version` must be the deployed 40-character commit SHA. Never use `latest`, a branch name, or a build timestamp as the release identity.

## 2. Wire private and public ingestion

- Servers send OTLP/gRPC or OTLP/HTTP to the private Alloy service in `davidapps-cluster`.
- Browsers and React Native clients send only approved signals through the project's randomized public gateway host.
- The gateway project must define an exact origin allowlist, body limit, rate limit, and allowed signal routes.
- Confirm the runtime environment supplies the active public origin and release; do not bake a preview domain into a browser bundle.
- Confirm excluded/private routes do not initialize browser telemetry.

## 3. Emit bounded semantics

Instrument server requests, stable route templates, rendering/API phases, dependencies, and errors. Dependency telemetry uses allowlisted names such as `dependency.system`, `operation`, and `query.name`; raw SQL, raw URLs, query strings, request bodies, payment IDs, and personal identifiers are forbidden.

Business metrics should use bounded dimensions and integer minor-currency units. Currency, provider, mode, stream, outcome, and credit/debit direction remain separate. Observability is not the accounting ledger.

## 4. Prove every signal before adding panels

Use the read-only agent connectors to confirm metric names and labels in the live backends:

1. `observability_grafana`: list Prometheus metric names, inspect label values, and execute the final PromQL.
2. `observability_logs`: query a small LogsQL sample and verify indexed fields, privacy scrubbing, release, and trace correlation.
3. `observability_traces`: verify service name, release, server/client span kinds, errors, and a representative slow trace.

Do not add a dashboard panel for a proposed label. Add it after the label is visible in production, or label the panel clearly as event-dependent.

## 5. Build the dashboard family

Create the smallest useful set for the project:

- `Overview`: business, reliability, browser, runtime, errors, and release.
- `Server & rendering`: RED metrics, stable routes, framework phases, and safe dependencies.
- `Browser experience`: Web Vitals, client errors, signal health, and release.
- `Runtime & deployments`: rollout state, pods, nodes, CPU, memory, throttling, network, restarts, image, and commit.
- `Delivery & data`: NGINX paths/status/latency, Cloudflare tunnel health, and only the databases that can be mapped honestly to the project.
- A product dashboard such as revenue, jobs, or subscriptions when the project has bounded business telemetry.

Run `python3 hack/generate-application-dashboards.py` after changing the generated cross-project, ZeroCut delivery/data, or ZeroCut runtime panel recipes. Kidays-specific dashboards may start from the same panel helpers, but their filters and descriptions must be project-correct.

## 6. Acceptance test

Before calling the project onboarded, prove all of the following over one real production visit and one server request:

- ready/desired replicas, pod/node placement, CPU, memory, restart, image, and commit panels populate;
- ingress request rate, statuses, stable paths, request latency, and upstream latency populate;
- the correct Cloudflare tunnel is visible without pretending tunnel metrics contain HTTP route attribution;
- server spans include stable operations and the exact release;
- browser signals reach the gateway once, do not retry-loop on CSP/network failure, and do not initialize on excluded routes;
- a synthetic handled exception appears in VictoriaLogs with the release and a trace ID, then opens its Tempo trace;
- agent tools can return a bounded error sweep without Grafana UI access;
- empty or event-dependent panels say why they are empty.

Record any missing signal as an instrumentation task rather than hiding it with an attractive but invalid query.
