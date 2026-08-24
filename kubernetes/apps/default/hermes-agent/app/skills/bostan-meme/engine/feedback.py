#!/usr/bin/env python3
"""Durable delivery and feedback ledger for Bostan posters."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent
DELIVERIES = ROOT / "deliveries.jsonl"
FEEDBACK = ROOT / "feedback.jsonl"
LOCK = ROOT / ".ledger.lock"


def _now() -> str:
    return datetime.now(ZoneInfo("Europe/Bucharest")).isoformat(timespec="seconds")


def _append(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    LOCK.touch(exist_ok=True)
    with LOCK.open("r+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _read(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    records = []
    for line in lines:
        try:
            item = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(item, dict):
            records.append(item)
    return records


def record_delivery(
    *,
    url: str,
    spec: dict[str, Any],
    render: dict[str, Any],
    guidance_key: str | None,
    replaces_url: str | None = None,
) -> dict[str, Any]:
    if not url.startswith("https://"):
        raise ValueError("delivery URL must use HTTPS")
    event = {
        "timestamp": _now(),
        "url": url,
        "spec": spec,
        "render": render,
        "guidance_key": guidance_key,
        "replaces_url": replaces_url,
    }
    _append(DELIVERIES, event)
    return event


def find_delivery(url: str) -> dict[str, Any] | None:
    for item in reversed(_read(DELIVERIES)):
        if item.get("url") == url:
            return item
    return None


def feedback_for_url(url: str) -> list[dict[str, Any]]:
    return [item for item in _read(FEEDBACK) if item.get("url") == url]


def record_feedback(*, url: str, text: str, disposition: str) -> dict[str, Any]:
    delivery = find_delivery(url)
    if delivery is None:
        raise ValueError("no delivered Bostan poster matches that URL")
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("feedback cannot be empty")
    if disposition not in {"positive", "critique", "replace"}:
        raise ValueError("invalid feedback disposition")
    event = {
        "timestamp": _now(),
        "url": url,
        "disposition": disposition,
        "text": cleaned,
    }
    _append(FEEDBACK, event)
    return event


def context(url: str) -> dict[str, Any]:
    delivery = find_delivery(url)
    if delivery is None:
        raise ValueError("no delivered Bostan poster matches that URL")
    return {"delivery": delivery, "feedback": feedback_for_url(url)}


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    lookup = commands.add_parser("context")
    lookup.add_argument("--url", required=True)
    record = commands.add_parser("record")
    record.add_argument("--url", required=True)
    record.add_argument("--text-file", type=Path, required=True)
    record.add_argument(
        "--disposition",
        choices=["positive", "critique", "replace"],
        default="critique",
    )
    arguments = parser.parse_args()
    if arguments.command == "context":
        print(json.dumps(context(arguments.url), ensure_ascii=False))
        return
    event = record_feedback(
        url=arguments.url,
        text=arguments.text_file.read_text(encoding="utf-8"),
        disposition=arguments.disposition,
    )
    print(json.dumps(event, ensure_ascii=False))


if __name__ == "__main__":
    main()
