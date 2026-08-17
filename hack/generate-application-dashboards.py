#!/usr/bin/env python3
"""Build the checked-in application dashboards from small, reusable panel recipes.

The source dashboards remain normal Grafana JSON. This helper only owns the
cross-project overview, the ZeroCut delivery/data dashboard, and the extra
capacity row on the ZeroCut runtime dashboard. Keeping those panels generated
makes the project variables and the query conventions easy to reuse for Kidays.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARDS = ROOT / "kubernetes/apps/observability/grafana/app/dashboards"

PROM = {"type": "prometheus", "uid": "prometheus-davidapps-cluster"}
SPAN_PROM = {"type": "prometheus", "uid": "prometheus-home-cluster"}
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

    dashboard["title"] = "All Projects / Overview"
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

    app_selector = f'namespace=~"{APP_NAMESPACES}",deployment=~"{APP}"'
    pod_selector = f'namespace=~"{APP_NAMESPACES}",pod=~"({APP})-.*"'
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
                        f'sum by (node) (kube_pod_status_phase{{namespace=~"{APP_NAMESPACES}",phase="Running",pod=~"({APP})-.*"}} * on (namespace, pod) group_left(node) kube_pod_info{{namespace=~"{APP_NAMESPACES}",pod=~"({APP})-.*"}})',
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
                        f'_stream: {{k_namespace_name="personal-projects", cluster="davidapps-cluster"}} app:~"{APP}" | stats by (app) count()',
                        "A",
                        stats=True,
                    ),
                    logs_target(
                        f'_stream: {{k_namespace_name="kidays-fr", cluster="davidapps-cluster"}} app:~"{APP}" | stats by (app) count()',
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
                        f'_stream: {{k_namespace_name="personal-projects", cluster="davidapps-cluster"}} app:~"{APP}" _msg:~"(?i)(error|exception|fatal|panic)" | fields _time, _msg, app, k_pod_name, k_container_name, trace_id, span_id | sort desc | limit 200',
                        "A",
                    ),
                    logs_target(
                        f'_stream: {{k_namespace_name="kidays-fr", cluster="davidapps-cluster"}} app:~"{APP}" _msg:~"(?i)(error|exception|fatal|panic)" | fields _time, _msg, app, k_pod_name, k_container_name, trace_id, span_id | sort desc | limit 200',
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
                    f'max by (namespace, pod, node, host_ip, pod_ip) (kube_pod_info{{namespace=~"{APP_NAMESPACES}",pod=~"({APP})-.*"}})',
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
            "title": "ZeroCut / Delivery & data",
            "description": (
                "ZeroCut-scoped NGINX delivery, Cloudflare tunnel health, and the "
                "personal-projects CloudNativePG service used by the application. "
                "The postgres17 cluster is namespace-shared, so database panels are an "
                "impact view rather than per-query attribution."
            ),
            "tags": ["apps", "zerocut", "delivery", "nginx", "cloudflare", "cnpg"],
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

    dashboard["panels"] = panels
    save("zerocut-delivery-data.json", dashboard)


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
    dashboard["title"] = "MBRetrofit Tools / Overview"
    dashboard["description"] = (
        "MBRetrofit Tools application overview for the primary and Zenzefi deployments."
    )
    dashboard["tags"] = sorted(set(dashboard.get("tags", [])) | {"mbretrofit-tools"})
    for link in dashboard.get("links", []):
        if link.get("title") == "Open MB Retrofit":
            link["title"] = "Open MBRetrofit Tools"
    save("mbretrofit-overview.json", dashboard)


def main() -> None:
    build_all_projects()
    build_zerocut_delivery()
    enrich_zerocut_runtime()
    normalize_project_names()


if __name__ == "__main__":
    main()
