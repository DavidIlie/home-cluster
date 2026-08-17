# CLIProxyAPI observability

The `CLIProxyAPI / Usage & cost` dashboard is provider-neutral. Claude, Codex,
and future providers use the same model-level panels whenever the exporter
exposes a real `provider` label.

## Metric boundaries

| Signal | Attribution available | Important limitation |
| --- | --- | --- |
| Model requests/tokens/estimated cost | `provider`, `model`, `scope` | Cost is recomputed from a pricing table; it is not an invoice |
| Rolling model aggregates | `provider`, `model`, `window` | Windows are plugin aggregates, not Prometheus `increase()` |
| Credential auth health/requests | `provider`, credential labels | Counters reset with CLIProxyAPI |
| Latency, TTFT, slow, failed, rate-limited totals | `scope`, `window` | `other` may contain several non-Codex providers; never relabel it as Claude |
| Account usage and quota | Codex accounts only | Claude per-credential tokens, cost, and quota do not exist in the current API |

The provider selector is applied only to model and auth metrics that actually
carry `provider`. Provider-group reliability panels remain labeled by `scope`
so the dashboard does not invent attribution.

## Window correctness

The plugin exports separate `window="24h"` and `window="30d"` gauges. Every
`cliproxy_usage_window*` query must select exactly one window. Omitting that
matcher sums or overlays both windows and can materially overstate cost.

The 30-day ServiceMonitor intentionally scrapes every 15 minutes. Prometheus's
normal five-minute instant-query lookback would make those gauges disappear
between scrapes, so dashboard queries use
`last_over_time(metric{window="$usage_window"}[20m])`.

The Grafana time picker controls rate panels; the `Usage window` variable
controls plugin-computed aggregates. They are separate concepts.

## Current honest coverage

As of 2026-08-17 the exporter contains real Claude and Codex credentials and
model history, including Claude Opus 5. The default 30-day view therefore shows
both providers. The current 24-hour window can legitimately show only Codex
when no Claude request occurred in that period.

Do not send synthetic production requests merely to make a panel colorful.
Use a genuine Claude Code session for normal data or a scratch exporter/storage
namespace for ingestion smoke tests. Synthetic traffic contaminates provider
share and unit-economics panels.

## Maintenance and acceptance

Run `python3 hack/generate-application-dashboards.py` after changing CLIProxy
panel recipes. Before deploying:

- parse the generated JSON;
- execute every PromQL expression with `provider=.*` and `usage_window=30d`;
- execute top-level queries again with `provider=claude`;
- verify the provider table includes both Claude and Codex;
- verify every window query contains `window=` and its 20-minute lookback;
- verify Codex quota/account panels are children of the collapsed Codex-only
  row, not merely positioned after it;
- verify Claude per-account missing data is described as unavailable, never
  zero.
