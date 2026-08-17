#!/usr/bin/env python3
"""Vendor upstream dashboards whose titles need stable local normalization.

Grafana.com's dashboard downloader cannot rename a dashboard while installing
it. Keeping these JSON files in Git lets the folder remain ``Kubernetes`` while
the child names stay concise, and prevents a Grafana restart from restoring the
upstream ``Kubernetes / ...`` prefixes.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DASHBOARDS = ROOT / "kubernetes/apps/observability/grafana/app/dashboards"

DASHBOARD_SOURCES = {
    "kubernetes-system-api-server.json": (15761, 18, "System / API Server"),
    "kubernetes-persistent-volumes.json": (13646, 2, "Persistent Volumes"),
    "kubernetes-system-coredns.json": (15762, 19, "System / CoreDNS"),
    "kubernetes-views-global.json": (15757, 42, "Views / Global"),
    "kubernetes-views-namespaces.json": (15758, 41, "Views / Namespaces"),
    "kubernetes-views-nodes.json": (15759, 32, "Views / Nodes"),
    "kubernetes-views-pods.json": (15760, 34, "Views / Pods"),
    "kubernetes-views-k3s-cluster.json": (16450, 3, "Views / K3s Cluster"),
}


def main() -> None:
    for filename, (dashboard_id, revision, title) in DASHBOARD_SOURCES.items():
        url = f"https://grafana.com/api/dashboards/{dashboard_id}/revisions/{revision}/download"
        request = Request(url, headers={"User-Agent": "home-cluster-dashboard-vendor/1.0"})
        with urlopen(request, timeout=30) as response:
            dashboard = json.load(response)
        dashboard["title"] = title
        # Provisioned dashboards receive their runtime ID from Grafana.
        dashboard["id"] = None
        (DASHBOARDS / filename).write_text(json.dumps(dashboard, indent=2) + "\n")


if __name__ == "__main__":
    main()
