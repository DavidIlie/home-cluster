"""Replay quota gaps, recovery, spikes, and exporter replacement with promtool.

Requires PyYAML and Docker. Run from any directory.
"""

import pathlib
import re
import subprocess
import tempfile

import yaml

root = pathlib.Path(__file__).resolve().parents[1]
s = (
    root / "kubernetes/apps/observability/cliproxy-exporter/app/helmrelease.yaml"
).read_text()
s = re.sub(r'\{\{"(.*?)"\}\}', lambda m: m[1], s)
r = next(
    r
    for r in yaml.safe_load(s)["spec"]["values"]["prometheusRule"]["rules"]
    if r["alert"] == "CLIProxyQuotaNearExhaustion"
)
temporary = tempfile.TemporaryDirectory(prefix="cliproxy-alert-test-")
p = pathlib.Path(temporary.name)
(p / "rules.yaml").write_text(
    yaml.safe_dump({"groups": [{"name": "quota", "interval": "1m", "rules": [r]}]})
)


def check(t, n):
    return {
        "expr": 'count(ALERTS{alertname="CLIProxyQuotaNearExhaustion",alertstate="firing"}) or vector(0)',
        "eval_time": t,
        "exp_samples": [{"labels": "{}", "value": n}],
    }


base = 'cliproxy_account_primary_used_percent{namespace="observability",provider="codex",email="david@example.com",auth_index="abc",pod="old"}'
tests = [
    {
        "name": "scrape gaps do not resolve or restart pending",
        "interval": "1m",
        "input_series": [
            {"series": base, "values": "95+0x5 stale _ 95+0x5 stale _ 95+0x20"}
        ],
        "promql_expr_test": [
            check("9m", 0),
            check("10m", 1),
            check("15m", 1),
            check("25m", 1),
        ],
    },
    {
        "name": "recovery requires thirty minutes",
        "interval": "1m",
        "input_series": [{"series": base, "values": "95+0x15 20+0x40"}],
        "promql_expr_test": [
            check("10m", 1),
            check("30m", 1),
            check("44m", 1),
            check("46m", 0),
        ],
    },
    {
        "name": "short quota spike does not fire",
        "interval": "1m",
        "input_series": [{"series": base, "values": "95+0x5 20+0x45"}],
        "promql_expr_test": [check("10m", 0), check("30m", 0)],
    },
    {
        "name": "pod replacement preserves pending timer",
        "interval": "1m",
        "input_series": [
            {"series": base, "values": "95+0x5 stale"},
            {"series": base.replace("old", "new"), "values": "_ _ _ _ _ _ 95+0x25"},
        ],
        "promql_expr_test": [check("10m", 1), check("20m", 1)],
    },
]
(p / "tests.yaml").write_text(
    yaml.safe_dump(
        {"rule_files": ["rules.yaml"], "evaluation_interval": "1m", "tests": tests}
    )
)

try:
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{p}:/work",
            "-w",
            "/work",
            "--entrypoint",
            "/bin/promtool",
            "prom/prometheus:v3.15.1",
            "test",
            "rules",
            "tests.yaml",
        ],
        check=True,
    )
finally:
    temporary.cleanup()
