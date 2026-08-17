#!/usr/bin/env python3
"""Build the checked-in application dashboards from small, reusable panel recipes.

The source dashboards remain normal Grafana JSON. This helper owns the
cross-project overview, ClickHouse monitoring, the ZeroCut delivery/data
dashboard, CLIProxyAPI provider normalization, and the extra capacity row on
the ZeroCut runtime dashboard. Keeping those panels generated makes the query
conventions easy to reuse for Kidays.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARDS = ROOT / "kubernetes/apps/observability/grafana/app/dashboards"

PROM = {"type": "prometheus", "uid": "prometheus-davidapps-cluster"}
SPAN_PROM = {"type": "prometheus", "uid": "prometheus-home-cluster"}
KUBE_PROM = {"type": "prometheus", "uid": "prometheus-kube-stack"}
VLOGS = {"type": "victoriametrics-logs-datasource", "uid": "victoria-logs"}

APP = "${application:regex}"
APP_NAMESPACES = "personal-projects|kidays-fr"


def load(name: str) -> dict:
    return json.loads((DASHBOARDS / name).read_text())


def save(name: str, dashboard: dict) -> None:
    (DASHBOARDS / name).write_text(json.dumps(dashboard, indent=2) + "\n")


def prom_target(
    expr: str,
    legend: str = "",
    *,
    datasource: dict = PROM,
    instant: bool = False,
    ref_id: str = "A",
    table: bool = False,
) -> dict:
    target = {
        "datasource": copy.deepcopy(datasource),
        "editorMode": "code",
        "expr": expr,
        "legendFormat": legend,
        "range": not instant,
        "instant": instant,
        "refId": ref_id,
    }
    if table:
        target["format"] = "table"
    return target


def logs_target(expr: str, ref_id: str = "A", *, stats: bool = False) -> dict:
    target = {
        "datasource": copy.deepcopy(VLOGS),
        "editorMode": "code",
        "expr": expr,
        "refId": ref_id,
    }
    if stats:
        target["legendFormat"] = "{{app}}"
        target["queryType"] = "statsRange"
    else:
        target["queryType"] = "range"
    return target


def row(panel_id: int, title: str, y: int, *, collapsed: bool = False) -> dict:
    return {
        "collapsed": collapsed,
        "gridPos": {"h": 1, "w": 24, "x": 0, "y": y},
        "id": panel_id,
        "panels": [],
        "title": title,
        "type": "row",
    }


def timeseries(
    prototype: dict,
    panel_id: int,
    title: str,
    x: int,
    y: int,
    width: int,
    targets: list[dict],
    *,
    unit: str = "short",
    height: int = 8,
    description: str | None = None,
) -> dict:
    panel = copy.deepcopy(prototype)
    panel.update(
        {
            "id": panel_id,
            "title": title,
            "type": "timeseries",
            "datasource": copy.deepcopy(targets[0]["datasource"]),
            "gridPos": {"h": height, "w": width, "x": x, "y": y},
            "targets": targets,
        }
    )
    panel.pop("transformations", None)
    panel["fieldConfig"]["defaults"]["unit"] = unit
    if description:
        panel["description"] = description
    else:
        panel.pop("description", None)
    return panel


def stat(
    prototype: dict,
    panel_id: int,
    title: str,
    x: int,
    y: int,
    width: int,
    target: dict,
    *,
    unit: str = "short",
    height: int = 5,
    description: str | None = None,
) -> dict:
    panel = copy.deepcopy(prototype)
    panel.update(
        {
            "id": panel_id,
            "title": title,
            "type": "stat",
            "datasource": copy.deepcopy(target["datasource"]),
            "gridPos": {"h": height, "w": width, "x": x, "y": y},
            "targets": [target],
        }
    )
    panel.pop("transformations", None)
    panel["fieldConfig"]["defaults"]["unit"] = unit
    panel["fieldConfig"]["defaults"].pop("decimals", None)
    if description:
        panel["description"] = description
    else:
        panel.pop("description", None)
    return panel


def logs_panel(
    prototype: dict,
    panel_id: int,
    title: str,
    x: int,
    y: int,
    width: int,
    targets: list[dict],
    *,
    height: int = 10,
    description: str | None = None,
) -> dict:
    panel = copy.deepcopy(prototype)
    panel.update(
        {
            "id": panel_id,
            "title": title,
            "type": "logs",
            "datasource": copy.deepcopy(VLOGS),
            "gridPos": {"h": height, "w": width, "x": x, "y": y},
            "targets": targets,
        }
    )
    if description:
        panel["description"] = description
    return panel


def application_variable() -> dict:
    query = (
        'label_values(kube_deployment_labels{namespace=~"personal-projects|kidays-fr",'
        'label_app_kubernetes_io_managed_by="Helm",'
        'label_app_kubernetes_io_name!~".*(cloudflared|external-dns).*"}, deployment)'
    )
    return {
        "allValue": ".*",
        "current": {"selected": True, "text": ["All"], "value": ["$__all"]},
        "datasource": copy.deepcopy(PROM),
        "definition": query,
        "description": (
            "Auto-discovered Helm application Deployments in the personal-projects and "
            "kidays-fr namespaces. Edge support Deployments are excluded."
        ),
        "hide": 0,
        "includeAll": True,
        "label": "Application",
        "multi": True,
        "name": "application",
        "options": [],
        "query": {"query": query, "refId": "PrometheusVariableQueryEditor-VariableQuery"},
        "refresh": 1,
        "regex": "",
        "skipUrlSync": False,
        "sort": 1,
        "type": "query",
    }


def clickhouse_variable() -> dict:
    query = (
        'label_values(ClickHouseAsyncMetrics_Uptime{'
        'job=~"clickhouse|plausible-clickhouse"}, job)'
    )
    return {
        "allValue": "clickhouse|plausible-clickhouse",
        "current": {"selected": True, "text": ["All"], "value": ["$__all"]},
        "datasource": copy.deepcopy(KUBE_PROM),
        "definition": query,
        "description": "ClickHouse ServiceMonitor scrape job.",
        "hide": 0,
        "includeAll": True,
        "label": "Instance",
        "multi": True,
        "name": "instance",
        "options": [],
        "query": {"query": query, "refId": "PrometheusVariableQueryEditor-VariableQuery"},
        "refresh": 1,
        "regex": "",
        "skipUrlSync": False,
        "sort": 1,
        "type": "query",
    }


def build_all_projects() -> None:
    dashboard = load("apps-fleet.json")
    overview = load("zerocut-overview.json")
    runtime = load("zerocut-runtime.json")
    stat_proto = next(panel for panel in dashboard["panels"] if panel["type"] == "stat")
    ts_proto = next(panel for panel in dashboard["panels"] if panel["type"] == "timeseries")
    log_ts_proto = next(
        panel
        for panel in dashboard["panels"]
        if panel["type"] == "timeseries" and panel["datasource"]["uid"] == "victoria-logs"
    )
    logs_proto = next(panel for panel in overview["panels"] if panel["type"] == "logs")
    table_proto = next(panel for panel in runtime["panels"] if panel["type"] == "table")

    dashboard["title"] = "Overview"
    dashboard["description"] = (
        "Auto-discovered DavidApps application health plus delivery, nodes, databases, "
        "OpenTelemetry, logs, and operational revenue. Select one or more applications; "
        "edge and database rows stay namespace/platform scoped where the exporter cannot "
        "attribute a signal to one workload."
    )
    dashboard["tags"] = ["apps", "all-projects", "otel", "operations"]
    dashboard["time"] = {"from": "now-24h", "to": "now"}
    dashboard["templating"] = {"list": [application_variable()]}
    dashboard["links"] = [
        {
            "type": "link",
            "title": "ZeroCut",
            "url": "/d/zerocut-overview",
            "targetBlank": False,
            "includeVars": False,
            "keepTime": True,
        },
        {
            "type": "link",
            "title": "MBRetrofit Tools",
            "url": "/d/mbretrofit-overview",
            "targetBlank": False,
            "includeVars": False,
            "keepTime": True,
        },
        {
            "type": "link",
            "title": "Kidays",
            "url": "/d/kidays-overview",
            "targetBlank": False,
            "includeVars": False,
            "keepTime": True,
        },
        {
            "type": "link",
            "title": "Kubernetes nodes",
            "url": "/d/k8s_views_nodes",
            "targetBlank": False,
            "includeVars": False,
            "keepTime": True,
        },
        {
            "type": "link",
            "title": "Ingress detail",
            "url": "/d/4GFbkOsZk",
            "targetBlank": False,
            "includeVars": False,
            "keepTime": True,
        },
        {
            "type": "link",
            "title": "CloudNativePG detail",
            "url": "/d/cloudnative-pg",
            "targetBlank": False,
            "includeVars": False,
            "keepTime": True,
        },
        {
            "type": "link",
            "title": "Trace search",
            "url": "/explore?schemaVersion=1&panes=%7B%22trace%22:%7B%22datasource%22:%22tempo%22%7D%7D",
            "targetBlank": True,
            "includeVars": False,
            "keepTime": True,
        },
    ]

    app_selector = (
        f'namespace=~"{APP_NAMESPACES}",deployment=~"{APP}",'
        'deployment!~".*(cloudflared|external-dns).*"'
    )
    pod_selector = (
        f'namespace=~"{APP_NAMESPACES}",pod=~"({APP})-.*",'
        'pod!~".*(cloudflared|external-dns).*"'
    )
    ingress_selector = f'exported_namespace=~"{APP_NAMESPACES}",ingress=~"{APP}"'

    panels: list[dict] = []
    panels.append(row(100, "Application health", 0))
    panels.extend(
        [
            stat(
                stat_proto,
                1,
                "Ready replicas",
                0,
                1,
                6,
                prom_target(
                    f"sum(kube_deployment_status_replicas_ready{{{app_selector}}})",
                    instant=True,
                ),
            ),
            stat(
                stat_proto,
                2,
                "Desired replicas",
                6,
                1,
                6,
                prom_target(f"sum(kube_deployment_spec_replicas{{{app_selector}}})", instant=True),
            ),
            stat(
                stat_proto,
                3,
                "Restarts · selected range",
                12,
                1,
                6,
                prom_target(
                    f'sum(increase(kube_pod_container_status_restarts_total{{{pod_selector}}}[$__range]))',
                    instant=True,
                ),
            ),
            stat(
                stat_proto,
                4,
                "OOM events · selected range",
                18,
                1,
                6,
                prom_target(
                    f'sum(increase(container_oom_events_total{{{pod_selector},container!=""}}[$__range]))',
                    instant=True,
                ),
            ),
            timeseries(
                ts_proto,
                5,
                "Replica availability by application",
                0,
                6,
                12,
                [
                    prom_target(
                        f'kube_deployment_status_replicas_available{{{app_selector}}}',
                        "{{namespace}} / {{deployment}}",
                    )
                ],
            ),
            timeseries(
                ts_proto,
                6,
                "Container restarts by pod",
                12,
                6,
                12,
                [
                    prom_target(
                        f'sum by (namespace, pod) (increase(kube_pod_container_status_restarts_total{{{pod_selector}}}[$__rate_interval]))',
                        "{{namespace}} / {{pod}}",
                    )
                ],
            ),
            timeseries(
                ts_proto,
                7,
                "CPU usage by pod",
                0,
                14,
                12,
                [
                    prom_target(
                        f'sum by (namespace, pod) (rate(container_cpu_usage_seconds_total{{{pod_selector},container!="POD",image!=""}}[$__rate_interval]))',
                        "{{namespace}} / {{pod}}",
                    )
                ],
                unit="cores",
            ),
            timeseries(
                ts_proto,
                8,
                "Memory working set by pod",
                12,
                14,
                12,
                [
                    prom_target(
                        f'sum by (namespace, pod) (container_memory_working_set_bytes{{{pod_selector},container!="POD",image!=""}})',
                        "{{namespace}} / {{pod}}",
                    )
                ],
                unit="bytes",
            ),
            timeseries(
                ts_proto,
                12,
                "CPU request utilization",
                0,
                22,
                12,
                [
                    prom_target(
                        f'100 * sum by (namespace, pod) (rate(container_cpu_usage_seconds_total{{{pod_selector},container!="POD",image!=""}}[$__rate_interval])) / clamp_min(sum by (namespace, pod) (kube_pod_container_resource_requests{{{pod_selector},resource="cpu"}}), 0.001)',
                        "{{namespace}} / {{pod}}",
                    )
                ],
                unit="percent",
            ),
            timeseries(
                ts_proto,
                13,
                "CPU throttled periods",
                12,
                22,
                12,
                [
                    prom_target(
                        f'100 * sum by (namespace, pod) (rate(container_cpu_cfs_throttled_periods_total{{{pod_selector},container!="POD",image!=""}}[$__rate_interval])) / clamp_min(sum by (namespace, pod) (rate(container_cpu_cfs_periods_total{{{pod_selector},container!="POD",image!=""}}[$__rate_interval])), 0.001)',
                        "{{namespace}} / {{pod}}",
                    )
                ],
                unit="percent",
            ),
            timeseries(
                ts_proto,
                14,
                "Pod network throughput",
                0,
                30,
                12,
                [
                    prom_target(
                        f'sum by (namespace, pod) (rate(container_network_receive_bytes_total{{{pod_selector}}}[$__rate_interval]))',
                        "RX {{namespace}} / {{pod}}",
                        ref_id="A",
                    ),
                    prom_target(
                        f'sum by (namespace, pod) (rate(container_network_transmit_bytes_total{{{pod_selector}}}[$__rate_interval]))',
                        "TX {{namespace}} / {{pod}}",
                        ref_id="B",
                    ),
                ],
                unit="Bps",
            ),
            timeseries(
                ts_proto,
                15,
                "Running application pods by node",
                12,
                30,
                12,
                [
                    prom_target(
                        f'sum by (node) (kube_pod_status_phase{{namespace=~"{APP_NAMESPACES}",phase="Running",pod=~"({APP})-.*",pod!~".*(cloudflared|external-dns).*"}} * on (namespace, pod) group_left(node) kube_pod_info{{namespace=~"{APP_NAMESPACES}",pod=~"({APP})-.*",pod!~".*(cloudflared|external-dns).*"}})',
                        "{{node}}",
                    )
                ],
            ),
        ]
    )

    panels.append(row(110, "Nodes serving the applications", 38))
    panels.extend(
        [
            timeseries(
                ts_proto,
                16,
                "Node CPU busy",
                0,
                39,
                12,
                [
                    prom_target(
                        '100 * (1 - avg by (kubernetes_node) (rate(node_cpu_seconds_total{cluster="davidapps-cluster",mode="idle"}[$__rate_interval])))',
                        "{{kubernetes_node}}",
                    )
                ],
                unit="percent",
            ),
            timeseries(
                ts_proto,
                17,
                "Node memory used",
                12,
                39,
                12,
                [
                    prom_target(
                        '100 * (1 - node_memory_MemAvailable_bytes{cluster="davidapps-cluster"} / node_memory_MemTotal_bytes{cluster="davidapps-cluster"})',
                        "{{kubernetes_node}}",
                    )
                ],
                unit="percent",
            ),
            timeseries(
                ts_proto,
                18,
                "Node load (1 minute)",
                0,
                47,
                12,
                [prom_target('node_load1{cluster="davidapps-cluster"}', "{{kubernetes_node}}")],
            ),
            timeseries(
                ts_proto,
                19,
                "Node network errors",
                12,
                47,
                12,
                [
                    prom_target(
                        'sum by (kubernetes_node) (rate(node_network_receive_errs_total{cluster="davidapps-cluster",device!~"lo|veth.*|cali.*|cilium.*"}[$__rate_interval]))',
                        "RX {{kubernetes_node}}",
                        ref_id="A",
                    ),
                    prom_target(
                        'sum by (kubernetes_node) (rate(node_network_transmit_errs_total{cluster="davidapps-cluster",device!~"lo|veth.*|cali.*|cilium.*"}[$__rate_interval]))',
                        "TX {{kubernetes_node}}",
                        ref_id="B",
                    ),
                ],
                unit="ops",
            ),
        ]
    )

    panels.append(row(120, "Ingress request delivery", 55))
    panels.extend(
        [
            timeseries(
                ts_proto,
                20,
                "Request rate by application and status",
                0,
                56,
                12,
                [
                    prom_target(
                        f'sum by (ingress, status) (rate(nginx_ingress_controller_requests{{{ingress_selector}}}[$__rate_interval]))',
                        "{{ingress}} / {{status}}",
                    )
                ],
                unit="reqps",
            ),
            timeseries(
                ts_proto,
                21,
                "HTTP error ratio by application",
                12,
                56,
                12,
                [
                    prom_target(
                        f'100 * sum by (ingress) (rate(nginx_ingress_controller_requests{{{ingress_selector},status=~"4..|5.."}}[$__rate_interval])) / clamp_min(sum by (ingress) (rate(nginx_ingress_controller_requests{{{ingress_selector}}}[$__rate_interval])), 0.001)',
                        "{{ingress}}",
                    )
                ],
                unit="percent",
            ),
            timeseries(
                ts_proto,
                22,
                "Ingress p95 request latency",
                0,
                64,
                12,
                [
                    prom_target(
                        f'histogram_quantile(0.95, sum by (le, ingress) (rate(nginx_ingress_controller_request_duration_seconds_bucket{{{ingress_selector}}}[$__rate_interval])))',
                        "{{ingress}}",
                    )
                ],
                unit="s",
            ),
            timeseries(
                ts_proto,
                23,
                "Top request delivery paths",
                12,
                64,
                12,
                [
                    prom_target(
                        f'topk(20, sum by (method, host, path, status) (rate(nginx_ingress_controller_requests{{{ingress_selector}}}[$__rate_interval])))',
                        "{{method}} {{host}}{{path}} / {{status}}",
                    )
                ],
                unit="reqps",
                description="NGINX route-template labels, not raw application URLs.",
            ),
            timeseries(
                ts_proto,
                24,
                "Ingress p95 upstream response",
                0,
                72,
                12,
                [
                    prom_target(
                        f'histogram_quantile(0.95, sum by (le, ingress) (rate(nginx_ingress_controller_response_duration_seconds_bucket{{{ingress_selector}}}[$__rate_interval])))',
                        "{{ingress}}",
                    )
                ],
                unit="s",
            ),
            timeseries(
                ts_proto,
                25,
                "Ingress response bytes",
                12,
                72,
                12,
                [
                    prom_target(
                        f'sum by (ingress, host) (rate(nginx_ingress_controller_bytes_sent_sum{{{ingress_selector}}}[$__rate_interval]))',
                        "{{ingress}} / {{host}}",
                    )
                ],
                unit="Bps",
            ),
        ]
    )

    panels.append(row(130, "Cloudflare tunnel delivery", 80))
    cloudflare_scope = 'cluster="davidapps-cluster",namespace=~"network|kidays-fr"'
    panels.extend(
        [
            timeseries(
                ts_proto,
                26,
                "Tunnel request rate",
                0,
                81,
                12,
                [
                    prom_target(
                        f'sum by (service) (rate(cloudflared_tunnel_total_requests{{{cloudflare_scope}}}[$__rate_interval]))',
                        "{{service}}",
                    )
                ],
                unit="reqps",
                description="Tunnel exporters do not expose the final HTTP route; this row is tunnel-service scoped.",
            ),
            timeseries(
                ts_proto,
                27,
                "Tunnel request errors",
                12,
                81,
                12,
                [
                    prom_target(
                        f'sum by (service) (rate(cloudflared_tunnel_request_errors{{{cloudflare_scope}}}[$__rate_interval]))',
                        "{{service}}",
                    )
                ],
                unit="reqps",
            ),
            timeseries(
                ts_proto,
                28,
                "Tunnel responses by code",
                0,
                89,
                12,
                [
                    prom_target(
                        f'sum by (service, status_code) (rate(cloudflared_tunnel_response_by_code{{{cloudflare_scope}}}[$__rate_interval]))',
                        "{{service}} / {{status_code}}",
                    )
                ],
                unit="reqps",
            ),
            timeseries(
                ts_proto,
                29,
                "Tunnel HA connections",
                12,
                89,
                12,
                [
                    prom_target(
                        f'sum by (service) (cloudflared_tunnel_ha_connections{{{cloudflare_scope}}})',
                        "{{service}}",
                    )
                ],
            ),
        ]
    )

    panels.append(row(140, "CloudNativePG data services", 97))
    cnpg_scope = f'namespace=~"{APP_NAMESPACES}"'
    panels.extend(
        [
            stat(
                stat_proto,
                30,
                "Healthy database collectors",
                0,
                98,
                6,
                prom_target(f'sum(cnpg_collector_up{{{cnpg_scope}}})', instant=True),
                description="All CNPG instances in application namespaces.",
            ),
            stat(
                stat_proto,
                31,
                "Database connections",
                6,
                98,
                6,
                prom_target(f'sum(cnpg_backends_total{{{cnpg_scope}}})', instant=True),
            ),
            stat(
                stat_proto,
                32,
                "Maximum replication lag",
                12,
                98,
                6,
                prom_target(f'max(cnpg_pg_replication_lag{{{cnpg_scope}}})', instant=True),
                unit="s",
            ),
            stat(
                stat_proto,
                33,
                "Oldest base backup",
                18,
                98,
                6,
                prom_target(
                    f'time() - min(cnpg_collector_last_available_backup_timestamp{{{cnpg_scope}}} > 0)',
                    instant=True,
                ),
                unit="s",
                description="Empty means CNPG currently reports no available base backup timestamp for these application namespaces.",
            ),
            timeseries(
                ts_proto,
                34,
                "Transactions per second",
                0,
                103,
                12,
                [
                    prom_target(
                        f'sum by (namespace, job) (rate(cnpg_pg_stat_database_xact_commit{{{cnpg_scope}}}[$__rate_interval])) + sum by (namespace, job) (rate(cnpg_pg_stat_database_xact_rollback{{{cnpg_scope}}}[$__rate_interval]))',
                        "{{namespace}} / {{job}}",
                    )
                ],
                unit="ops",
            ),
            timeseries(
                ts_proto,
                35,
                "Database size",
                12,
                103,
                12,
                [
                    prom_target(
                        f'max by (namespace, job, datname) (cnpg_pg_database_size_bytes{{{cnpg_scope},datname!~"template0|template1"}})',
                        "{{namespace}} / {{job}} / {{datname}}",
                    )
                ],
                unit="bytes",
            ),
            timeseries(
                ts_proto,
                36,
                "Connections by database instance",
                0,
                111,
                12,
                [
                    prom_target(
                        f'sum by (namespace, job, pod, state) (cnpg_backends_total{{{cnpg_scope}}})',
                        "{{namespace}} / {{job}} / {{pod}} / {{state}}",
                    )
                ],
            ),
            timeseries(
                ts_proto,
                37,
                "Rollbacks and deadlocks",
                12,
                111,
                12,
                [
                    prom_target(
                        f'sum by (namespace, job) (rate(cnpg_pg_stat_database_xact_rollback{{{cnpg_scope}}}[$__rate_interval]))',
                        "rollbacks {{namespace}} / {{job}}",
                        ref_id="A",
                    ),
                    prom_target(
                        f'sum by (namespace, job) (rate(cnpg_pg_stat_database_deadlocks{{{cnpg_scope}}}[$__rate_interval]))',
                        "deadlocks {{namespace}} / {{job}}",
                        ref_id="B",
                    ),
                ],
                unit="ops",
            ),
        ]
    )

    panels.append(row(150, "OpenTelemetry, logs, and business signals", 119))
    panels.extend(
        [
            timeseries(
                ts_proto,
                9,
                "p95 latency by traced service",
                0,
                120,
                12,
                [
                    prom_target(
                        f'histogram_quantile(0.95, sum by (le, service) (rate(traces_spanmetrics_latency_bucket{{service=~"{APP}"}}[$__rate_interval])))',
                        "{{service}}",
                        datasource=SPAN_PROM,
                    )
                ],
                unit="s",
            ),
            timeseries(
                ts_proto,
                10,
                "Span error ratio by service",
                12,
                120,
                12,
                [
                    prom_target(
                        f'100 * sum by (service) (rate(traces_spanmetrics_calls_total{{service=~"{APP}",status_code="STATUS_CODE_ERROR"}}[$__rate_interval])) / clamp_min(sum by (service) (rate(traces_spanmetrics_calls_total{{service=~"{APP}"}}[$__rate_interval])), 0.000001)',
                        "{{service}}",
                        datasource=SPAN_PROM,
                    )
                ],
                unit="percent",
            ),
            timeseries(
                ts_proto,
                38,
                "Span throughput by operation",
                0,
                128,
                12,
                [
                    prom_target(
                        f'sum by (service, span_name) (rate(traces_spanmetrics_calls_total{{service=~"{APP}"}}[$__rate_interval]))',
                        "{{service}} / {{span_name}}",
                        datasource=SPAN_PROM,
                    )
                ],
                unit="reqps",
            ),
            timeseries(
                log_ts_proto,
                11,
                "Application log volume",
                12,
                128,
                12,
                [
                    logs_target(
                        f'_stream: {{k_namespace_name="personal-projects", cluster="davidapps-cluster"}} app:~"{APP}" app:!~".*(cloudflared|external-dns).*" | stats by (app) count()',
                        "A",
                        stats=True,
                    ),
                    logs_target(
                        f'_stream: {{k_namespace_name="kidays-fr", cluster="davidapps-cluster"}} app:~"{APP}" app:!~".*(cloudflared|external-dns).*" | stats by (app) count()',
                        "B",
                        stats=True,
                    ),
                ],
            ),
            logs_panel(
                logs_proto,
                39,
                "Recent application errors",
                0,
                136,
                16,
                [
                    logs_target(
                        f'_stream: {{k_namespace_name="personal-projects", cluster="davidapps-cluster"}} app:~"{APP}" app:!~".*(cloudflared|external-dns).*" _msg:~"(?i)(error|exception|fatal|panic)" | fields _time, _msg, app, k_pod_name, k_container_name, trace_id, span_id | sort desc | limit 200',
                        "A",
                    ),
                    logs_target(
                        f'_stream: {{k_namespace_name="kidays-fr", cluster="davidapps-cluster"}} app:~"{APP}" app:!~".*(cloudflared|external-dns).*" _msg:~"(?i)(error|exception|fatal|panic)" | fields _time, _msg, app, k_pod_name, k_container_name, trace_id, span_id | sort desc | limit 200',
                        "B",
                    ),
                ],
                description="Bounded server error sweep. Open trace_id through the VictoriaLogs derived field when present.",
            ),
            stat(
                stat_proto,
                40,
                "Revenue movements · selected range",
                16,
                136,
                8,
                prom_target(
                    'sum by (service_name, revenue_stream, revenue_net_direction, commerce_currency) (increase({__name__=~".*_revenue_amount(_minor_currency_unit)?_sum",revenue_stream!=""}[$__range]))',
                    "{{service_name}} / {{revenue_stream}} / {{revenue_net_direction}} / {{commerce_currency}}",
                    instant=True,
                ),
                unit="short",
                height=10,
                description="Operational minor-currency movements. Currencies and directions remain separate; this is not an accounting ledger.",
            ),
        ]
    )

    # Keep a current deployment/image table at the bottom. The query is dynamic,
    # while the transformations remain the battle-tested ZeroCut table layout.
    release_table = copy.deepcopy(table_proto)
    release_table.update(
        {
            "id": 41,
            "title": "Application pod placement and release",
            "description": "Current application pods, nodes, images, and restart state for the selected deployments.",
            "gridPos": {"h": 10, "w": 24, "x": 0, "y": 146},
            "targets": [
                prom_target(
                    f'max by (namespace, pod, container, image, image_id) (kube_pod_container_info{{{pod_selector},container!="POD"}})',
                    instant=True,
                    ref_id="A",
                    table=True,
                ),
                prom_target(
                    f'max by (namespace, pod, node, host_ip, pod_ip) (kube_pod_info{{namespace=~"{APP_NAMESPACES}",pod=~"({APP})-.*",pod!~".*(cloudflared|external-dns).*"}})',
                    instant=True,
                    ref_id="B",
                    table=True,
                ),
                prom_target(
                    f'sum by (namespace, pod) (kube_pod_container_status_restarts_total{{{pod_selector}}})',
                    instant=True,
                    ref_id="C",
                    table=True,
                ),
            ],
        }
    )
    # A generic outer join is safer than the old ZeroCut field ordering when
    # multiple namespaces and containers are selected.
    release_table["transformations"] = [
        {"id": "joinByField", "options": {"byField": "pod", "mode": "outer"}}
    ]
    panels.append(release_table)

    dashboard["panels"] = panels
    save("apps-fleet.json", dashboard)


def build_zerocut_delivery() -> None:
    base = load("zerocut-reliability.json")
    fleet = load("apps-fleet.json")
    stat_proto = next(panel for panel in fleet["panels"] if panel["type"] == "stat")
    ts_proto = next(panel for panel in fleet["panels"] if panel["type"] == "timeseries")

    dashboard = {
        key: copy.deepcopy(base[key])
        for key in (
            "annotations",
            "editable",
            "fiscalYearStartMonth",
            "graphTooltip",
            "links",
            "liveNow",
            "refresh",
            "schemaVersion",
            "style",
            "time",
            "timepicker",
            "timezone",
        )
        if key in base
    }
    dashboard.update(
        {
            "id": None,
            "uid": "zerocut-delivery-data",
            "title": "Delivery & data",
            "description": (
                "ZeroCut-scoped NGINX delivery, Cloudflare tunnel health, and the "
                "PostgreSQL and ClickHouse services used by the application. The "
                "postgres17 cluster is namespace-shared, so its panels are an impact "
                "view rather than per-query attribution. ClickHouse panels are scoped "
                "to ZeroCut's dedicated instance."
            ),
            "tags": [
                "apps",
                "zerocut",
                "delivery",
                "nginx",
                "cloudflare",
                "cnpg",
                "clickhouse",
            ],
            "templating": {"list": []},
            "version": 1,
        }
    )

    ingress = 'exported_namespace="personal-projects",ingress=~"zerocut.*"'
    tunnel = 'cluster="davidapps-cluster",service="zerocut-cloudflared"'
    # The Prometheus external label overwrites the CNPG cluster label on most
    # custom-query series. The scrape job is therefore the stable database
    # cluster identity; datname gives the honest ZeroCut-specific subset.
    database = 'namespace="personal-projects",job="personal-projects/postgres17"'
    zerocut_database = database + ',datname="zerocut"'
    panels: list[dict] = [row(1, "Request delivery", 0)]
    panels.extend(
        [
            stat(
                stat_proto,
                2,
                "Ingress requests / second",
                0,
                1,
                6,
                prom_target(
                    f'sum(rate(nginx_ingress_controller_requests{{{ingress}}}[$__rate_interval]))',
                    instant=True,
                ),
                unit="reqps",
            ),
            stat(
                stat_proto,
                3,
                "Ingress 5xx ratio",
                6,
                1,
                6,
                prom_target(
                    f'100 * sum(rate(nginx_ingress_controller_requests{{{ingress},status=~"5.."}}[$__rate_interval])) / clamp_min(sum(rate(nginx_ingress_controller_requests{{{ingress}}}[$__rate_interval])), 0.001)',
                    instant=True,
                ),
                unit="percent",
            ),
            stat(
                stat_proto,
                4,
                "Ingress p95 latency",
                12,
                1,
                6,
                prom_target(
                    f'histogram_quantile(0.95, sum by (le) (rate(nginx_ingress_controller_request_duration_seconds_bucket{{{ingress}}}[$__rate_interval])))',
                    instant=True,
                ),
                unit="s",
            ),
            stat(
                stat_proto,
                5,
                "Tunnel errors / second",
                18,
                1,
                6,
                prom_target(
                    f'sum(rate(cloudflared_tunnel_request_errors{{{tunnel}}}[$__rate_interval]))',
                    instant=True,
                ),
                unit="reqps",
            ),
            timeseries(
                ts_proto,
                6,
                "Requests by status",
                0,
                6,
                12,
                [
                    prom_target(
                        f'sum by (method, status) (rate(nginx_ingress_controller_requests{{{ingress}}}[$__rate_interval]))',
                        "{{method}} / {{status}}",
                    )
                ],
                unit="reqps",
            ),
            timeseries(
                ts_proto,
                7,
                "Request rate by route template",
                12,
                6,
                12,
                [
                    prom_target(
                        f'topk(20, sum by (method, host, path, status) (rate(nginx_ingress_controller_requests{{{ingress}}}[$__rate_interval])))',
                        "{{method}} {{host}}{{path}} / {{status}}",
                    )
                ],
                unit="reqps",
            ),
            timeseries(
                ts_proto,
                8,
                "Request latency percentiles",
                0,
                14,
                12,
                [
                    prom_target(
                        f'histogram_quantile(0.50, sum by (le) (rate(nginx_ingress_controller_request_duration_seconds_bucket{{{ingress}}}[$__rate_interval])))',
                        "p50",
                        ref_id="A",
                    ),
                    prom_target(
                        f'histogram_quantile(0.95, sum by (le) (rate(nginx_ingress_controller_request_duration_seconds_bucket{{{ingress}}}[$__rate_interval])))',
                        "p95",
                        ref_id="B",
                    ),
                    prom_target(
                        f'histogram_quantile(0.99, sum by (le) (rate(nginx_ingress_controller_request_duration_seconds_bucket{{{ingress}}}[$__rate_interval])))',
                        "p99",
                        ref_id="C",
                    ),
                ],
                unit="s",
            ),
            timeseries(
                ts_proto,
                9,
                "Upstream response p95 by route",
                12,
                14,
                12,
                [
                    prom_target(
                        f'histogram_quantile(0.95, sum by (le, method, host, path) (rate(nginx_ingress_controller_response_duration_seconds_bucket{{{ingress}}}[$__rate_interval])))',
                        "{{method}} {{host}}{{path}}",
                    )
                ],
                unit="s",
            ),
            timeseries(
                ts_proto,
                10,
                "Response bandwidth",
                0,
                22,
                12,
                [
                    prom_target(
                        f'sum by (host) (rate(nginx_ingress_controller_bytes_sent_sum{{{ingress}}}[$__rate_interval]))',
                        "{{host}}",
                    )
                ],
                unit="Bps",
            ),
            timeseries(
                ts_proto,
                11,
                "4xx and 5xx responses by route",
                12,
                22,
                12,
                [
                    prom_target(
                        f'sum by (method, host, path, status) (rate(nginx_ingress_controller_requests{{{ingress},status=~"4..|5.."}}[$__rate_interval]))',
                        "{{method}} {{host}}{{path}} / {{status}}",
                    )
                ],
                unit="reqps",
            ),
        ]
    )

    panels.append(row(20, "Cloudflare tunnel", 30))
    panels.extend(
        [
            timeseries(
                ts_proto,
                21,
                "Tunnel requests and errors",
                0,
                31,
                12,
                [
                    prom_target(
                        f'sum(rate(cloudflared_tunnel_total_requests{{{tunnel}}}[$__rate_interval]))',
                        "requests",
                        ref_id="A",
                    ),
                    prom_target(
                        f'sum(rate(cloudflared_tunnel_request_errors{{{tunnel}}}[$__rate_interval]))',
                        "errors",
                        ref_id="B",
                    ),
                ],
                unit="reqps",
            ),
            timeseries(
                ts_proto,
                22,
                "Tunnel responses by code",
                12,
                31,
                12,
                [
                    prom_target(
                        f'sum by (status_code) (rate(cloudflared_tunnel_response_by_code{{{tunnel}}}[$__rate_interval]))',
                        "{{status_code}}",
                    )
                ],
                unit="reqps",
            ),
            timeseries(
                ts_proto,
                23,
                "HA connections and concurrent requests",
                0,
                39,
                12,
                [
                    prom_target(
                        f'sum(cloudflared_tunnel_ha_connections{{{tunnel}}})',
                        "HA connections",
                        ref_id="A",
                    ),
                    prom_target(
                        f'sum(cloudflared_tunnel_concurrent_requests_per_tunnel{{{tunnel}}})',
                        "concurrent requests",
                        ref_id="B",
                    ),
                ],
            ),
            timeseries(
                ts_proto,
                24,
                "Tunnel registration failures",
                12,
                39,
                12,
                [
                    prom_target(
                        f'sum(rate(cloudflared_tunnel_tunnel_register_fail{{{tunnel}}}[$__rate_interval]))',
                        "registration failures",
                    )
                ],
                unit="ops",
            ),
        ]
    )

    panels.append(row(30, "PostgreSQL impact view", 47))
    panels.extend(
        [
            stat(
                stat_proto,
                31,
                "Healthy instances",
                0,
                48,
                6,
                prom_target(f'sum(cnpg_collector_up{{{database}}})', instant=True),
            ),
            stat(
                stat_proto,
                32,
                "Connections",
                6,
                48,
                6,
                prom_target(f'sum(cnpg_backends_total{{{zerocut_database}}})', instant=True),
            ),
            stat(
                stat_proto,
                33,
                "Max replication lag",
                12,
                48,
                6,
                prom_target(f'max(cnpg_pg_replication_lag{{{database}}})', instant=True),
                unit="s",
            ),
            stat(
                stat_proto,
                34,
                "Backup age",
                18,
                48,
                6,
                prom_target(
                    f'time() - max(cnpg_collector_last_available_backup_timestamp{{{database}}} > 0)',
                    instant=True,
                ),
                unit="s",
                description="Empty means the shared postgres17 cluster currently reports no available base backup timestamp.",
            ),
            timeseries(
                ts_proto,
                35,
                "Transactions per second",
                0,
                53,
                12,
                [
                    prom_target(
                        f'sum(rate(cnpg_pg_stat_database_xact_commit{{{zerocut_database}}}[$__rate_interval]))',
                        "commits",
                        ref_id="A",
                    ),
                    prom_target(
                        f'sum(rate(cnpg_pg_stat_database_xact_rollback{{{zerocut_database}}}[$__rate_interval]))',
                        "rollbacks",
                        ref_id="B",
                    ),
                ],
                unit="ops",
            ),
            timeseries(
                ts_proto,
                36,
                "Connections by instance and state",
                12,
                53,
                12,
                [
                    prom_target(
                        f'sum by (pod, state) (cnpg_backends_total{{{zerocut_database}}})',
                        "{{pod}} / {{state}}",
                    )
                ],
            ),
            timeseries(
                ts_proto,
                37,
                "Database size",
                0,
                61,
                12,
                [
                    prom_target(
                        f'max by (datname) (cnpg_pg_database_size_bytes{{{zerocut_database}}})',
                        "{{datname}}",
                    )
                ],
                unit="bytes",
            ),
            timeseries(
                ts_proto,
                38,
                "Deadlocks and waiting backends",
                12,
                61,
                12,
                [
                    prom_target(
                        f'sum(rate(cnpg_pg_stat_database_deadlocks{{{zerocut_database}}}[$__rate_interval]))',
                        "deadlocks",
                        ref_id="A",
                    ),
                    prom_target(
                        f'sum(cnpg_backends_waiting_total{{{zerocut_database}}})',
                        "waiting backends",
                        ref_id="B",
                    ),
                ],
                unit="ops",
            ),
            timeseries(
                ts_proto,
                39,
                "Cache hits and disk reads",
                0,
                69,
                12,
                [
                    prom_target(
                        f'sum(rate(cnpg_cache_hits{{{database}}}[$__rate_interval]))',
                        "cache hits",
                        ref_id="A",
                    ),
                    prom_target(
                        f'sum(rate(cnpg_cache_miss{{{database}}}[$__rate_interval]))',
                        "cache misses",
                        ref_id="B",
                    ),
                ],
                unit="ops",
            ),
            timeseries(
                ts_proto,
                40,
                "Temporary data written",
                12,
                69,
                12,
                [
                    prom_target(
                        f'sum(rate(cnpg_pg_stat_database_temp_bytes{{{zerocut_database}}}[$__rate_interval]))',
                        "temp bytes / second",
                    )
                ],
                unit="Bps",
            ),
        ]
    )

    panels.append(row(41, "ClickHouse event analytics", 77))
    clickhouse = 'job="clickhouse"'
    clickhouse_pod = 'namespace="databases",pod=~"clickhouse-.*",container="app"'
    panels.extend(
        [
            stat(
                stat_proto,
                42,
                "Available",
                0,
                78,
                6,
                prom_target(f'min(up{{{clickhouse}}})', datasource=KUBE_PROM, instant=True),
                description="One means Prometheus can scrape the ZeroCut ClickHouse instance.",
            ),
            stat(
                stat_proto,
                43,
                "MergeTree data",
                6,
                78,
                6,
                prom_target(
                    f'sum(ClickHouseAsyncMetrics_TotalBytesOfMergeTreeTables{{{clickhouse}}})',
                    datasource=KUBE_PROM,
                    instant=True,
                ),
                unit="bytes",
            ),
            stat(
                stat_proto,
                44,
                "Rows",
                12,
                78,
                6,
                prom_target(
                    f'sum(ClickHouseAsyncMetrics_TotalRowsOfMergeTreeTables{{{clickhouse}}})',
                    datasource=KUBE_PROM,
                    instant=True,
                ),
            ),
            stat(
                stat_proto,
                45,
                "Parts",
                18,
                78,
                6,
                prom_target(
                    f'sum(ClickHouseAsyncMetrics_TotalPartsOfMergeTreeTables{{{clickhouse}}})',
                    datasource=KUBE_PROM,
                    instant=True,
                ),
            ),
            timeseries(
                ts_proto,
                46,
                "Queries by operation",
                0,
                83,
                12,
                [
                    prom_target(
                        f'sum(rate(ClickHouseProfileEvents_SelectQuery{{{clickhouse}}}[$__rate_interval]))',
                        "select",
                        datasource=KUBE_PROM,
                        ref_id="A",
                    ),
                    prom_target(
                        f'sum(rate(ClickHouseProfileEvents_InsertQuery{{{clickhouse}}}[$__rate_interval]))',
                        "insert",
                        datasource=KUBE_PROM,
                        ref_id="B",
                    ),
                ],
                unit="qps",
            ),
            timeseries(
                ts_proto,
                47,
                "Latency and failed-query ratio",
                12,
                83,
                12,
                [
                    prom_target(
                        f'1e-6 * sum(rate(ClickHouseProfileEvents_QueryTimeMicroseconds{{{clickhouse}}}[$__rate_interval])) / clamp_min(sum(rate(ClickHouseProfileEvents_Query{{{clickhouse}}}[$__rate_interval])), 0.000001)',
                        "average query seconds",
                        datasource=KUBE_PROM,
                        ref_id="A",
                    ),
                    prom_target(
                        f'100 * sum(rate(ClickHouseProfileEvents_FailedQuery{{{clickhouse}}}[$__rate_interval])) / clamp_min(sum(rate(ClickHouseProfileEvents_Query{{{clickhouse}}}[$__rate_interval])), 0.000001)',
                        "failed query percent",
                        datasource=KUBE_PROM,
                        ref_id="B",
                    ),
                ],
            ),
            timeseries(
                ts_proto,
                48,
                "Errors and active work",
                0,
                91,
                12,
                [
                    prom_target(
                        f'sum(rate(ClickHouseErrorMetric_ALL{{{clickhouse}}}[$__rate_interval]))',
                        "errors / second",
                        datasource=KUBE_PROM,
                        ref_id="A",
                    ),
                    prom_target(
                        f'sum(ClickHouseMetrics_Query{{{clickhouse}}})',
                        "queries",
                        datasource=KUBE_PROM,
                        ref_id="B",
                    ),
                    prom_target(
                        f'sum(ClickHouseMetrics_Merge{{{clickhouse}}})',
                        "merges",
                        datasource=KUBE_PROM,
                        ref_id="C",
                    ),
                ],
                unit="ops",
            ),
            timeseries(
                ts_proto,
                49,
                "Memory and shared SSD headroom",
                12,
                91,
                12,
                [
                    prom_target(
                        f'sum(container_memory_working_set_bytes{{{clickhouse_pod}}})',
                        "container memory",
                        datasource=KUBE_PROM,
                        ref_id="A",
                    ),
                    prom_target(
                        f'min(ClickHouseAsyncMetrics_DiskAvailable_default{{{clickhouse}}})',
                        "shared analytics SSD free",
                        datasource=KUBE_PROM,
                        ref_id="B",
                    ),
                ],
                unit="bytes",
                description="Disk free is for the shared analytics filesystem; MergeTree data is the instance-specific footprint.",
            ),
        ]
    )

    dashboard["panels"] = panels
    save("zerocut-delivery-data.json", dashboard)


def build_clickhouse_dashboard() -> None:
    base = load("apps-fleet.json")
    stat_proto = next(panel for panel in base["panels"] if panel["type"] == "stat")
    ts_proto = next(panel for panel in base["panels"] if panel["type"] == "timeseries")

    dashboard = {
        key: copy.deepcopy(base[key])
        for key in (
            "annotations",
            "editable",
            "fiscalYearStartMonth",
            "graphTooltip",
            "liveNow",
            "refresh",
            "schemaVersion",
            "style",
            "timepicker",
            "timezone",
        )
        if key in base
    }
    dashboard.update(
        {
            "id": None,
            "uid": "clickhouse-instances",
            "title": "ClickHouse Instances",
            "description": (
                "Health, query workload, MergeTree storage, errors, and Kubernetes resources "
                "for the ZeroCut and Plausible ClickHouse instances. Disk-free metrics describe "
                "their shared analytics SSD; MergeTree bytes are instance-specific."
            ),
            "links": [],
            "tags": ["clickhouse", "databases", "plausible", "zerocut"],
            "templating": {"list": [clickhouse_variable()]},
            "time": {"from": "now-24h", "to": "now"},
            "version": 1,
        }
    )

    instance = 'job=~"${instance:regex}"'
    clickhouse_pods = (
        'namespace=~"databases|observability",'
        'pod=~"(${instance:regex})-.*",container="app"'
    )
    panels: list[dict] = [row(1, "Overview", 0)]
    overview_stats = [
        (2, "Available", 'min(up{' + instance + '})', "short", "Minimum scrape health across the selection."),
        (3, "Minimum uptime", 'min(ClickHouseAsyncMetrics_Uptime{' + instance + '})', "s", None),
        (4, "MergeTree data", 'sum(ClickHouseAsyncMetrics_TotalBytesOfMergeTreeTables{' + instance + '})', "bytes", None),
        (5, "Rows", 'sum(ClickHouseAsyncMetrics_TotalRowsOfMergeTreeTables{' + instance + '})', "short", None),
        (6, "Parts", 'sum(ClickHouseAsyncMetrics_TotalPartsOfMergeTreeTables{' + instance + '})', "short", None),
        (7, "Resident memory", 'sum(ClickHouseAsyncMetrics_MemoryResident{' + instance + '})', "bytes", None),
        (8, "Shared SSD free", 'min(ClickHouseAsyncMetrics_DiskAvailable_default{' + instance + '})', "bytes", "Free space on the shared analytics filesystem, not an instance allocation."),
        (9, "Restarts · selected range", 'sum(increase(kube_pod_container_status_restarts_total{namespace=~"databases|observability",pod=~"(${instance:regex})-.*",container="app"}[$__range]))', "short", None),
    ]
    for offset, (panel_id, title, expr, unit, description) in enumerate(overview_stats):
        panels.append(
            stat(
                stat_proto,
                panel_id,
                title,
                offset * 3,
                1,
                3,
                prom_target(expr, datasource=KUBE_PROM, instant=True),
                unit=unit,
                description=description,
            )
        )

    panels.append(row(10, "Query workload", 6))
    panels.extend(
        [
            timeseries(
                ts_proto,
                11,
                "Queries / second",
                0,
                7,
                12,
                [prom_target(f'sum by (job) (rate(ClickHouseProfileEvents_Query{{{instance}}}[$__rate_interval]))', "{{job}}", datasource=KUBE_PROM)],
                unit="qps",
            ),
            timeseries(
                ts_proto,
                12,
                "Operations / second",
                12,
                7,
                12,
                [
                    prom_target(f'sum by (job) (rate(ClickHouseProfileEvents_SelectQuery{{{instance}}}[$__rate_interval]))', "select · {{job}}", datasource=KUBE_PROM, ref_id="A"),
                    prom_target(f'sum by (job) (rate(ClickHouseProfileEvents_InsertQuery{{{instance}}}[$__rate_interval]))', "insert · {{job}}", datasource=KUBE_PROM, ref_id="B"),
                ],
                unit="qps",
            ),
            timeseries(
                ts_proto,
                13,
                "Failed-query ratio",
                0,
                15,
                12,
                [prom_target(f'100 * sum by (job) (rate(ClickHouseProfileEvents_FailedQuery{{{instance}}}[$__rate_interval])) / clamp_min(sum by (job) (rate(ClickHouseProfileEvents_Query{{{instance}}}[$__rate_interval])), 0.000001)', "{{job}}", datasource=KUBE_PROM)],
                unit="percent",
            ),
            timeseries(
                ts_proto,
                14,
                "Average query time",
                12,
                15,
                12,
                [prom_target(f'1e-6 * sum by (job) (rate(ClickHouseProfileEvents_QueryTimeMicroseconds{{{instance}}}[$__rate_interval])) / clamp_min(sum by (job) (rate(ClickHouseProfileEvents_Query{{{instance}}}[$__rate_interval])), 0.000001)', "{{job}}", datasource=KUBE_PROM)],
                unit="s",
            ),
            timeseries(
                ts_proto,
                15,
                "Rows selected and inserted",
                0,
                23,
                12,
                [
                    prom_target(f'sum by (job) (rate(ClickHouseProfileEvents_SelectedRows{{{instance}}}[$__rate_interval]))', "selected · {{job}}", datasource=KUBE_PROM, ref_id="A"),
                    prom_target(f'sum by (job) (rate(ClickHouseProfileEvents_InsertedRows{{{instance}}}[$__rate_interval]))', "inserted · {{job}}", datasource=KUBE_PROM, ref_id="B"),
                ],
                unit="rows/s",
            ),
            timeseries(
                ts_proto,
                16,
                "Bytes selected and inserted",
                12,
                23,
                12,
                [
                    prom_target(f'sum by (job) (rate(ClickHouseProfileEvents_SelectedBytes{{{instance}}}[$__rate_interval]))', "selected · {{job}}", datasource=KUBE_PROM, ref_id="A"),
                    prom_target(f'sum by (job) (rate(ClickHouseProfileEvents_InsertedBytes{{{instance}}}[$__rate_interval]))', "inserted · {{job}}", datasource=KUBE_PROM, ref_id="B"),
                ],
                unit="Bps",
            ),
        ]
    )

    panels.append(row(20, "MergeTree and background work", 31))
    panels.extend(
        [
            timeseries(ts_proto, 21, "Data footprint", 0, 32, 12, [prom_target(f'sum by (job) (ClickHouseAsyncMetrics_TotalBytesOfMergeTreeTables{{{instance}}})', "{{job}}", datasource=KUBE_PROM)], unit="bytes"),
            timeseries(ts_proto, 22, "Rows and parts", 12, 32, 12, [prom_target(f'sum by (job) (ClickHouseAsyncMetrics_TotalRowsOfMergeTreeTables{{{instance}}})', "rows · {{job}}", datasource=KUBE_PROM, ref_id="A"), prom_target(f'sum by (job) (ClickHouseAsyncMetrics_TotalPartsOfMergeTreeTables{{{instance}}})', "parts · {{job}}", datasource=KUBE_PROM, ref_id="B")]),
            timeseries(ts_proto, 23, "Maximum parts in a partition", 0, 40, 12, [prom_target(f'max by (job) (ClickHouseAsyncMetrics_MaxPartCountForPartition{{{instance}}})', "{{job}}", datasource=KUBE_PROM)]),
            timeseries(ts_proto, 24, "Active background work", 12, 40, 12, [prom_target(f'sum by (job) (ClickHouseMetrics_Merge{{{instance}}})', "merges · {{job}}", datasource=KUBE_PROM, ref_id="A"), prom_target(f'sum by (job) (ClickHouseMetrics_PartMutation{{{instance}}})', "mutations · {{job}}", datasource=KUBE_PROM, ref_id="B"), prom_target(f'sum by (job) (ClickHouseMetrics_DelayedInserts{{{instance}}})', "delayed inserts · {{job}}", datasource=KUBE_PROM, ref_id="C")], unit="ops"),
            timeseries(ts_proto, 25, "Merge throughput", 0, 48, 12, [prom_target(f'sum by (job) (rate(ClickHouseProfileEvents_MergedRows{{{instance}}}[$__rate_interval]))', "{{job}}", datasource=KUBE_PROM)], unit="rows/s"),
            timeseries(ts_proto, 26, "Mark cache hit ratio", 12, 48, 12, [prom_target(f'100 * sum by (job) (rate(ClickHouseProfileEvents_MarkCacheHits{{{instance}}}[$__rate_interval])) / clamp_min(sum by (job) (rate(ClickHouseProfileEvents_MarkCacheHits{{{instance}}}[$__rate_interval]) + rate(ClickHouseProfileEvents_MarkCacheMisses{{{instance}}}[$__rate_interval])), 0.000001)', "{{job}}", datasource=KUBE_PROM)], unit="percent"),
        ]
    )

    panels.append(row(30, "Reliability", 56))
    panels.extend(
        [
            timeseries(ts_proto, 31, "All errors", 0, 57, 12, [prom_target(f'sum by (job) (rate(ClickHouseErrorMetric_ALL{{{instance}}}[$__rate_interval]))', "{{job}}", datasource=KUBE_PROM)], unit="ops"),
            timeseries(ts_proto, 32, "Resource-limit errors", 12, 57, 12, [prom_target(f'sum by (job) (rate(ClickHouseErrorMetric_MEMORY_LIMIT_EXCEEDED{{{instance}}}[$__rate_interval]))', "memory limit · {{job}}", datasource=KUBE_PROM, ref_id="A"), prom_target(f'sum by (job) (rate(ClickHouseErrorMetric_TOO_MANY_PARTS{{{instance}}}[$__rate_interval]))', "too many parts · {{job}}", datasource=KUBE_PROM, ref_id="B")], unit="ops"),
            timeseries(ts_proto, 33, "Timeout and network errors", 0, 65, 12, [prom_target(f'sum by (job) (rate(ClickHouseErrorMetric_TIMEOUT_EXCEEDED{{{instance}}}[$__rate_interval]))', "timeout · {{job}}", datasource=KUBE_PROM, ref_id="A"), prom_target(f'sum by (job) (rate(ClickHouseErrorMetric_NETWORK_ERROR{{{instance}}}[$__rate_interval]))', "network · {{job}}", datasource=KUBE_PROM, ref_id="B")], unit="ops"),
            timeseries(ts_proto, 34, "Current queries and merges", 12, 65, 12, [prom_target(f'sum by (job) (ClickHouseMetrics_Query{{{instance}}})', "queries · {{job}}", datasource=KUBE_PROM, ref_id="A"), prom_target(f'sum by (job) (ClickHouseMetrics_Merge{{{instance}}})', "merges · {{job}}", datasource=KUBE_PROM, ref_id="B")], unit="ops"),
        ]
    )

    panels.append(row(40, "Kubernetes resources", 73))
    panels.extend(
        [
            timeseries(ts_proto, 41, "Container memory", 0, 74, 12, [prom_target(f'sum by (namespace, pod) (container_memory_working_set_bytes{{{clickhouse_pods}}})', "{{namespace}} / {{pod}}", datasource=KUBE_PROM)], unit="bytes"),
            timeseries(ts_proto, 42, "Container CPU", 12, 74, 12, [prom_target(f'sum by (namespace, pod) (rate(container_cpu_usage_seconds_total{{{clickhouse_pods}}}[$__rate_interval]))', "{{namespace}} / {{pod}}", datasource=KUBE_PROM)], unit="cores"),
            timeseries(ts_proto, 43, "Container network", 0, 82, 12, [prom_target('sum by (namespace, pod) (rate(container_network_receive_bytes_total{namespace=~"databases|observability",pod=~"(${instance:regex})-.*"}[$__rate_interval]))', "receive · {{namespace}} / {{pod}}", datasource=KUBE_PROM, ref_id="A"), prom_target('sum by (namespace, pod) (rate(container_network_transmit_bytes_total{namespace=~"databases|observability",pod=~"(${instance:regex})-.*"}[$__rate_interval]))', "transmit · {{namespace}} / {{pod}}", datasource=KUBE_PROM, ref_id="B")], unit="Bps"),
            timeseries(ts_proto, 44, "Container filesystem I/O", 12, 82, 12, [prom_target(f'sum by (namespace, pod) (rate(container_fs_reads_bytes_total{{{clickhouse_pods}}}[$__rate_interval]))', "read · {{namespace}} / {{pod}}", datasource=KUBE_PROM, ref_id="A"), prom_target(f'sum by (namespace, pod) (rate(container_fs_writes_bytes_total{{{clickhouse_pods}}}[$__rate_interval]))', "write · {{namespace}} / {{pod}}", datasource=KUBE_PROM, ref_id="B")], unit="Bps"),
        ]
    )

    dashboard["panels"] = panels
    save("clickhouse-instances.json", dashboard)


def enrich_zerocut_runtime() -> None:
    dashboard = load("zerocut-runtime.json")
    fleet = load("apps-fleet.json")
    ts_proto = next(panel for panel in fleet["panels"] if panel["type"] == "timeseries")
    dashboard["panels"] = [panel for panel in dashboard["panels"] if panel["id"] < 100]
    dashboard["panels"].append(row(100, "Capacity, pressure, and node headroom", 40))
    pod = 'namespace="personal-projects",pod=~"zerocut-.*"'
    dashboard["panels"].extend(
        [
            timeseries(
                ts_proto,
                101,
                "CPU request utilization",
                0,
                41,
                12,
                [
                    prom_target(
                        f'100 * sum by (pod) (rate(container_cpu_usage_seconds_total{{{pod},container!="POD",image!=""}}[$__rate_interval])) / clamp_min(sum by (pod) (kube_pod_container_resource_requests{{{pod},resource="cpu"}}), 0.001)',
                        "{{pod}}",
                    )
                ],
                unit="percent",
            ),
            timeseries(
                ts_proto,
                102,
                "CPU throttled periods",
                12,
                41,
                12,
                [
                    prom_target(
                        f'100 * sum by (pod) (rate(container_cpu_cfs_throttled_periods_total{{{pod},container!="POD",image!=""}}[$__rate_interval])) / clamp_min(sum by (pod) (rate(container_cpu_cfs_periods_total{{{pod},container!="POD",image!=""}}[$__rate_interval])), 0.001)',
                        "{{pod}}",
                    )
                ],
                unit="percent",
            ),
            timeseries(
                ts_proto,
                103,
                "Pod network throughput",
                0,
                49,
                12,
                [
                    prom_target(
                        f'sum by (pod) (rate(container_network_receive_bytes_total{{{pod}}}[$__rate_interval]))',
                        "RX {{pod}}",
                        ref_id="A",
                    ),
                    prom_target(
                        f'sum by (pod) (rate(container_network_transmit_bytes_total{{{pod}}}[$__rate_interval]))',
                        "TX {{pod}}",
                        ref_id="B",
                    ),
                ],
                unit="Bps",
            ),
            timeseries(
                ts_proto,
                104,
                "OOM events and memory failures",
                12,
                49,
                12,
                [
                    prom_target(
                        f'sum by (pod) (increase(container_oom_events_total{{{pod},container!=""}}[$__rate_interval]))',
                        "OOM {{pod}}",
                        ref_id="A",
                    ),
                    prom_target(
                        f'sum by (pod) (increase(container_memory_failures_total{{{pod},container!=""}}[$__rate_interval]))',
                        "memory failures {{pod}}",
                        ref_id="B",
                    ),
                ],
            ),
            timeseries(
                ts_proto,
                105,
                "DavidApps node CPU busy",
                0,
                57,
                12,
                [
                    prom_target(
                        '100 * (1 - avg by (kubernetes_node) (rate(node_cpu_seconds_total{cluster="davidapps-cluster",mode="idle"}[$__rate_interval])))',
                        "{{kubernetes_node}}",
                    )
                ],
                unit="percent",
            ),
            timeseries(
                ts_proto,
                106,
                "DavidApps node memory used",
                12,
                57,
                12,
                [
                    prom_target(
                        '100 * (1 - node_memory_MemAvailable_bytes{cluster="davidapps-cluster"} / node_memory_MemTotal_bytes{cluster="davidapps-cluster"})',
                        "{{kubernetes_node}}",
                    )
                ],
                unit="percent",
            ),
        ]
    )
    dashboard["description"] = (
        "Kubernetes rollout state, pod placement, node distribution, CPU and memory "
        "capacity, throttling, network I/O, restarts, image, and exact release "
        "correlation for ZeroCut."
    )
    save("zerocut-runtime.json", dashboard)


def normalize_project_names() -> None:
    dashboard = load("mbretrofit-overview.json")
    dashboard["title"] = "Overview"
    dashboard["description"] = (
        "MBRetrofit Tools application overview for the primary and Zenzefi deployments."
    )
    dashboard["tags"] = sorted(set(dashboard.get("tags", [])) | {"mbretrofit-tools"})
    for link in dashboard.get("links", []):
        if link.get("title") == "Open MB Retrofit":
            link["title"] = "Open MBRetrofit Tools"
    save("mbretrofit-overview.json", dashboard)


def normalize_dashboard_titles() -> None:
    """Normalize generated files; hand-authored dashboards keep their source title."""
    titles = {
        "apps-fleet.json": "Overview",
        "mbretrofit-overview.json": "Overview",
        "zerocut-delivery-data.json": "Delivery & data",
        "zerocut-runtime.json": "Runtime & deployments",
    }
    for filename, title in titles.items():
        dashboard = load(filename)
        dashboard["title"] = title
        save(filename, dashboard)


def normalize_cliproxy_dashboard() -> None:
    """Keep CLIProxy provider-neutral while preserving honest exporter gaps."""
    dashboard = load("cliproxy-usage.json")
    top_level_panels = dashboard["panels"]
    account_row = next(panel for panel in top_level_panels if panel["id"] == 29)
    all_panels = top_level_panels + account_row.get("panels", [])
    panels = {panel["id"]: panel for panel in all_panels}

    def set_target(
        panel_id: int,
        ref_id: str,
        expr: str,
        legend: str | None = None,
    ) -> None:
        target = next(
            target for target in panels[panel_id]["targets"] if target["refId"] == ref_id
        )
        target["expr"] = expr
        if legend is not None:
            target["legendFormat"] = legend

    dashboard["title"] = "CLIProxyAPI / Usage & cost"
    dashboard["description"] = (
        "Provider-neutral operational usage for every model routed through CLIProxyAPI. "
        "The Usage window variable selects plugin-computed 24h or 30d aggregates; "
        "Grafana's time picker controls counter-rate panels. Costs are pricing-table "
        "estimates, not provider invoices."
    )
    dashboard["tags"] = ["ai", "claude", "cliproxy", "codex", "cost", "tokens", "usage"]

    datasource_variable = next(
        variable for variable in dashboard["templating"]["list"] if variable["name"] == "datasource"
    )
    provider_query = "label_values(cliproxy_usage_model_requests_total, provider)"
    provider_variable = {
        "allValue": ".*",
        "current": {"selected": True, "text": ["All"], "value": ["$__all"]},
        "datasource": {"type": "prometheus", "uid": "${datasource}"},
        "definition": provider_query,
        "description": "Real provider labels exported by CLIProxyAPI model and auth metrics.",
        "hide": 0,
        "includeAll": True,
        "label": "Provider",
        "multi": True,
        "name": "provider",
        "options": [],
        "query": {"query": provider_query, "refId": "PrometheusVariableQueryEditor-VariableQuery"},
        "refresh": 1,
        "regex": "",
        "skipUrlSync": False,
        "sort": 1,
        "type": "query",
    }
    window_variable = {
        "current": {"selected": True, "text": "30d", "value": "30d"},
        "description": "Plugin-computed aggregate window; independent of the Grafana time picker.",
        "hide": 0,
        "includeAll": False,
        "label": "Usage window",
        "multi": False,
        "name": "usage_window",
        "options": [
            {"selected": False, "text": "24h", "value": "24h"},
            {"selected": True, "text": "30d", "value": "30d"},
        ],
        "query": "24h,30d",
        "queryValue": "",
        "skipUrlSync": False,
        "type": "custom",
    }
    dashboard["templating"]["list"] = [
        datasource_variable,
        provider_variable,
        window_variable,
    ]

    panels[6]["title"] = "Estimated cost"
    panels[3]["title"] = "Cost coverage · active provider groups"
    panels[3]["description"] = (
        "One means every provider group with real requests resolved to the current "
        "pricing table. Empty scopes are excluded because the plugin reports zero "
        "coverage both for no traffic and for unpriced traffic."
    )
    set_target(
        3,
        "A",
        "min(cliproxy_usage_cost_available and on (scope) (cliproxy_usage_requests_total > 0))",
    )
    set_target(
        5,
        "A",
        'count(cliproxy_auth_info{provider=~"${provider:regex}",status=~"error|disabled"}) or vector(0)',
    )
    panels[7]["title"] = "Lifetime cost · selected providers"
    panels[7]["description"] = (
        "Lifetime model-level estimate for the selected providers. The reconciliation "
        "health tile must remain at 1.0 for this model sum to be complete."
    )
    set_target(
        7,
        "A",
        'sum(cliproxy_usage_model_cost_usd_total{provider=~"${provider:regex}"})',
    )

    panels[8]["title"] = "Estimated cost by model · $usage_window"
    panels[8]["description"] = (
        "Plugin-computed window values filtered by the Usage window and Provider controls. "
        "The 20m last-over-time range covers the deliberately slow 15m scrape of 30d "
        "aggregates. No rate() is used because pricing refreshes can move estimates down."
    )
    set_target(
        8,
        "A",
        'topk(20, sum by (model, provider) (last_over_time(cliproxy_usage_window_model_cost_usd{window="$usage_window",provider=~"${provider:regex}"}[20m])))',
        "{{provider}} / {{model}}",
    )

    panels[9]["title"] = "Estimated cost · $usage_window"
    panels[9]["description"] = (
        "Model-level plugin aggregate for exactly one selected window. This previously "
        "summed the 24h and 30d series and therefore overstated the result."
    )
    set_target(
        9,
        "A",
        'sum(last_over_time(cliproxy_usage_window_model_cost_usd{window="$usage_window",provider=~"${provider:regex}"}[20m]))',
    )

    panels[10]["title"] = "Estimated cost by provider · $usage_window"
    panels[10]["description"] = (
        "Provider comparison from model-level aggregates, so Claude, Codex, and future "
        "providers share the same path and scope=other is never treated as a provider."
    )
    set_target(
        10,
        "A",
        'sum by (provider) (last_over_time(cliproxy_usage_window_model_cost_usd{window="$usage_window",provider=~"${provider:regex}"}[20m]))',
        "{{provider}}",
    )

    panels[11]["title"] = "Lifetime estimated cost by model"
    set_target(
        11,
        "A",
        'topk(20, sum by (model, provider) (cliproxy_usage_model_cost_usd_total{provider=~"${provider:regex}"}))',
        "{{provider}} / {{model}}",
    )

    panels[13]["title"] = "Token mix by provider"
    panels[13]["description"] = (
        "Counter rates grouped by real provider labels. Cache-read dominance is useful "
        "for Claude Code, while Codex reasoning and output remain separately visible."
    )
    token_kinds = {
        "A": ("input", "cliproxy_usage_model_input_tokens_total"),
        "B": ("output", "cliproxy_usage_model_output_tokens_total"),
        "C": ("reasoning", "cliproxy_usage_model_reasoning_tokens_total"),
        "D": ("cache read", "cliproxy_usage_model_cache_read_tokens_total"),
        "E": ("cache write", "cliproxy_usage_model_cache_creation_tokens_total"),
    }
    for ref_id, (label, metric) in token_kinds.items():
        set_target(
            13,
            ref_id,
            f'sum by (provider) (rate({metric}{{provider=~"${{provider:regex}}"}}[1h]))',
            "{{provider}} · " + label,
        )

    panels[14]["title"] = "Token throughput by provider"
    set_target(
        14,
        "A",
        'sum by (provider) (rate(cliproxy_usage_model_tokens_total{provider=~"${provider:regex}"}[1h]))',
        "{{provider}}",
    )

    panels[15]["title"] = "Tokens by model · $usage_window"
    set_target(
        15,
        "A",
        'topk(20, sum by (model, provider) (last_over_time(cliproxy_usage_window_model_tokens{window="$usage_window",provider=~"${provider:regex}"}[20m])))',
        "{{provider}} / {{model}}",
    )

    panels[16]["title"] = "Lifetime usage by provider"
    panels[16]["description"] = (
        "Requests, tokens, and estimated cost use the same per-model source for every "
        "provider. Claude per-credential token and cost attribution is not exposed."
    )
    set_target(
        16,
        "A",
        'sum by (provider) (cliproxy_usage_model_tokens_total{provider=~"${provider:regex}"})',
    )
    set_target(
        16,
        "B",
        'sum by (provider) (cliproxy_usage_model_cost_usd_total{provider=~"${provider:regex}"})',
    )
    set_target(
        16,
        "C",
        'sum by (provider) (cliproxy_usage_model_requests_total{provider=~"${provider:regex}"})',
    )
    provider_derived = {
        "D": (
            'sum by (provider) (cliproxy_usage_model_tokens_total{provider=~"${provider:regex}"}) / clamp_min(sum by (provider) (cliproxy_usage_model_requests_total{provider=~"${provider:regex}"}), 1)',
            "Tokens / request",
            "short",
            1,
        ),
        "E": (
            'sum by (provider) (cliproxy_usage_model_cost_usd_total{provider=~"${provider:regex}"}) / clamp_min(sum by (provider) (cliproxy_usage_model_requests_total{provider=~"${provider:regex}"}), 1)',
            "Cost / request",
            "currencyUSD",
            6,
        ),
        "F": (
            '1e6 * sum by (provider) (cliproxy_usage_model_cost_usd_total{provider=~"${provider:regex}"}) / clamp_min(sum by (provider) (cliproxy_usage_model_tokens_total{provider=~"${provider:regex}"}), 1)',
            "Cost / 1M tokens",
            "currencyUSD",
            4,
        ),
    }
    for ref_id, (expr, display_name, unit, decimals) in provider_derived.items():
        target = next(
            (target for target in panels[16]["targets"] if target["refId"] == ref_id),
            None,
        )
        if target is None:
            target = copy.deepcopy(panels[16]["targets"][0])
            target["refId"] = ref_id
            panels[16]["targets"].append(target)
        target["expr"] = expr
        override = next(
            (
                override
                for override in panels[16]["fieldConfig"]["overrides"]
                if override["matcher"].get("options") == f"Value #{ref_id}"
            ),
            None,
        )
        if override is None:
            override = {
                "matcher": {"id": "byName", "options": f"Value #{ref_id}"},
                "properties": [],
            }
            panels[16]["fieldConfig"]["overrides"].append(override)
        override["properties"] = [
            {"id": "displayName", "value": display_name},
            {"id": "unit", "value": unit},
            {"id": "decimals", "value": decimals},
        ]
        panels[16]["transformations"][1]["options"]["renameByName"][
            f"Value #{ref_id}"
        ] = display_name

    panels[17]["title"] = "Credentials and provider health"
    for ref_id in ("A", "B"):
        target = next(target for target in panels[18]["targets"] if target["refId"] == ref_id)
        target["expr"] = target["expr"].replace(
            "cliproxy_auth_requests_",
            'cliproxy_auth_requests_',
        ).replace(
            "_total[5m]",
            '_total{provider=~"${provider:regex}"}[5m]',
        )
    for metric in ("success", "failed"):
        old = f"cliproxy_auth_requests_{metric}_total[15m]"
        new = f'cliproxy_auth_requests_{metric}_total{{provider=~"${{provider:regex}}"}}[15m]'
        panels[19]["targets"][0]["expr"] = panels[19]["targets"][0]["expr"].replace(old, new)
    set_target(
        20,
        "A",
        'cliproxy_auth_info{provider=~"${provider:regex}"}',
    )
    panels[20]["gridPos"]["w"] = 24

    panels[23]["title"] = "Latency and reliability"
    panels[24]["title"] = "Provider-group latency / TTFT · $usage_window"
    panels[24]["description"] = (
        "Window means, not quantiles. The upstream summary exposes only scope here: "
        "codex, other, and xai. 'other' can contain Claude, Gemini, or future providers, "
        "so this panel deliberately does not relabel it as Claude or obey Provider filtering."
    )
    set_target(
        24,
        "A",
        'last_over_time(cliproxy_usage_window_avg_latency_ms{window="$usage_window"}[20m])',
        "latency · {{scope}}",
    )
    set_target(
        24,
        "B",
        'last_over_time(cliproxy_usage_window_avg_ttft_ms{window="$usage_window"}[20m])',
        "TTFT · {{scope}}",
    )
    panels[25]["title"] = "Slow requests · $usage_window"
    panels[25]["description"] = (
        "Provider-group values because the upstream summary exposes only scope. "
        "Thresholds are fixed upstream: latency >= 12s and TTFT >= 3s."
    )
    set_target(
        25,
        "A",
        'last_over_time(cliproxy_usage_window_slow_requests{window="$usage_window"}[20m])',
        "latency >= 12s · {{scope}}",
    )
    set_target(
        25,
        "B",
        'last_over_time(cliproxy_usage_window_slow_ttft_requests{window="$usage_window"}[20m])',
        "TTFT >= 3s · {{scope}}",
    )
    panels[26]["title"] = "Rate limits by provider group"
    panels[26]["description"] = (
        "Counter rate by upstream scope. The current API does not expose Codex and "
        "non-Codex rate limits through one shared provider-labelled metric."
    )
    panels[27]["title"] = "Failed requests by provider group"
    panels[27]["description"] = (
        "Counter rate by upstream scope. 'other' remains explicit because it may "
        "aggregate Claude, Gemini, and future providers."
    )
    panels[28]["title"] = "Output tokens/sec by provider group · $usage_window"
    panels[28]["description"] = (
        "The plugin publishes this only by scope, not real provider label; 'other' is "
        "therefore kept explicit and may aggregate multiple non-Codex providers."
    )
    set_target(
        28,
        "A",
        'last_over_time(cliproxy_usage_window_output_tokens_per_second{window="$usage_window"}[20m])',
        "{{scope}}",
    )

    panels[29]["title"] = "Codex-only quota & account detail"
    panels[29]["collapsed"] = True
    panels[21]["gridPos"].update({"x": 0, "y": 65, "w": 6})
    panels[22]["gridPos"].update({"x": 6, "y": 65, "w": 6})
    panels[30]["gridPos"].update({"x": 12, "y": 65, "w": 12})
    panels[30]["title"] = "Per-account usage (Codex only)"
    panels[30]["description"] = (
        "The plugin exposes account token/cost/quota fields only for Codex. Claude and "
        "other provider credentials still appear in the provider-neutral auth panels, "
        "but missing per-account usage must not be interpreted as zero."
    )
    panels[29]["panels"] = [panels[21], panels[22], panels[30]]
    dashboard["panels"] = [
        panel for panel in top_level_panels if panel["id"] not in {21, 22, 30}
    ]
    for panel in dashboard["panels"] + panels[29]["panels"]:
        for target in panel.get("targets", []):
            expr = target.get("expr", "")
            if "cliproxy_usage_window" in expr and "window=" not in expr:
                raise ValueError(
                    f"CLIProxy panel {panel['id']} mixes plugin aggregate windows: {expr}"
                )
    save("cliproxy-usage.json", dashboard)


def main() -> None:
    build_all_projects()
    build_zerocut_delivery()
    build_clickhouse_dashboard()
    enrich_zerocut_runtime()
    normalize_project_names()
    normalize_dashboard_titles()
    normalize_cliproxy_dashboard()


if __name__ == "__main__":
    main()
