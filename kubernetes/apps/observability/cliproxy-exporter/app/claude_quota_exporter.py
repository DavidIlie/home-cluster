#!/usr/bin/env python3
"""Export Claude OAuth quota without exposing credentials or guessing from tokens."""

import json
import math
import os
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CLIPROXY = os.getenv("CLIPROXY_URL", "http://cliproxy.default.svc.cluster.local:8317")
KEY_FILE = os.getenv("MANAGEMENT_KEY_FILE", "/etc/cliproxy/management-key")
WINDOWS = ("five_hour", "seven_day", "seven_day_opus", "seven_day_sonnet")


def parse_reset(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def parse_usage(payload):
    """Return only finite, bounded upstream utilization and valid reset fields."""
    samples = []
    if not isinstance(payload, dict):
        return samples
    for window in WINDOWS:
        value = payload.get(window)
        if not isinstance(value, dict):
            continue
        utilization = value.get("utilization")
        if isinstance(utilization, (int, float)) and math.isfinite(utilization):
            used = min(100.0, max(0.0, float(utilization)))
            samples.extend((("used_percent", window, used), ("remaining_percent", window, 100.0 - used)))
        reset = parse_reset(value.get("resets_at"))
        if reset is not None:
            samples.append(("reset_timestamp_seconds", window, reset))
    return samples


def request_json(url, key, data=None):
    headers = {"Authorization": f"Bearer {key}"}
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers), timeout=20) as response:
        return json.load(response)


def collect():
    with open(KEY_FILE, encoding="utf-8") as handle:
        key = handle.read().strip()
    auths = request_json(f"{CLIPROXY}/v0/management/auth-files", key).get("files", [])
    output = []
    for auth in auths:
        if str(auth.get("provider", auth.get("type", ""))).lower() != "claude":
            continue
        index = auth.get("auth_index")
        if not index:
            continue
        response = request_json(f"{CLIPROXY}/v0/management/api-call", key, {
            "auth_index": index, "method": "GET", "url": "https://api.anthropic.com/api/oauth/usage",
            "header": {"Authorization": "Bearer $TOKEN$", "anthropic-beta": "oauth-2025-04-20"},
        })
        if response.get("status_code") != 200:
            continue
        try:
            payload = json.loads(response.get("body", ""))
        except (TypeError, json.JSONDecodeError):
            continue
        account = str(auth.get("email") or auth.get("label") or index)
        for metric, window, value in parse_usage(payload):
            output.append((metric, account, window, value))
    return output


def prometheus(samples):
    lines = [
        "# HELP cliproxy_claude_quota_used_percent Claude OAuth quota utilization reported by Anthropic.",
        "# TYPE cliproxy_claude_quota_used_percent gauge",
        "# HELP cliproxy_claude_quota_remaining_percent Complement of Anthropic's bounded utilization percentage.",
        "# TYPE cliproxy_claude_quota_remaining_percent gauge",
        "# HELP cliproxy_claude_quota_reset_timestamp_seconds Claude OAuth quota reset time reported by Anthropic.",
        "# TYPE cliproxy_claude_quota_reset_timestamp_seconds gauge",
    ]
    for metric, account, window, value in samples:
        labels = json.dumps(account)[1:-1], json.dumps(window)[1:-1]
        lines.append(f'cliproxy_claude_quota_{metric}{{account="{labels[0]}",window="{labels[1]}"}} {value:g}')
    return "\n".join(lines) + "\n"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            body, status = b"ok\n", 200
        elif self.path == "/metrics":
            try:
                body, status = prometheus(collect()).encode(), 200
            except Exception:
                body, status = b"collection failed\n", 503
        else:
            body, status = b"not found\n", 404
        self.send_response(status); self.send_header("Content-Type", "text/plain; version=0.0.4"); self.end_headers(); self.wfile.write(body)
    def log_message(self, *_args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
