#!/usr/bin/env python3
"""Prepare Herm's persistent runtime before the gateway starts.

This migration has two deliberately separate jobs:

* reconcile the small set of operator-managed runtime settings without
  replacing the rest of the persistent user config;
* once per migration ID, replay all or an explicit subset of already-registered
  Discord threads owned by David.

The replay is fail-closed: the registry, routing table, platform, owner, and
one-to-one thread mapping must all agree before any session is changed.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml


MIGRATION_ID = "operator-replay-20260816-v7"
REPLAY_REASON = "operator_replay"


def configure_timezone(name: str) -> None:
    """Use the same local clock as the gateway's naïve session timestamps."""
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError as error:
        raise RuntimeError(f"unknown timezone: {name}") from error
    os.environ["TZ"] = name
    if not hasattr(time, "tzset"):
        raise RuntimeError("this runtime cannot set the process timezone")
    time.tzset()


def _regular_file(path: Path, *, required: bool = True) -> bool:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        if required:
            raise RuntimeError(f"required file is missing: {path}")
        return False
    if not stat.S_ISREG(mode):
        raise RuntimeError(f"refusing non-regular file: {path}")
    return True


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        _regular_file(path)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def configure_runtime_config(
    config_path: Path, memory_char_limit: int, user_char_limit: int
) -> bool:
    """Reconcile bounded operator settings without losing user configuration."""
    if not 2_200 <= memory_char_limit <= 100_000:
        raise RuntimeError("memory character limit is outside the safe range")
    if not 1_375 <= user_char_limit <= 100_000:
        raise RuntimeError("user character limit is outside the safe range")
    _regular_file(config_path)
    with config_path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    if not isinstance(config, dict):
        raise RuntimeError(f"config root must be a mapping: {config_path}")
    browser = config.get("browser")
    if browser is None:
        browser = {}
        config["browser"] = browser
    if not isinstance(browser, dict):
        raise RuntimeError("config browser section must be a mapping")
    memory = config.get("memory")
    if memory is None:
        memory = {}
        config["memory"] = memory
    if not isinstance(memory, dict):
        raise RuntimeError("config memory section must be a mapping")

    changed = False
    managed = (
        (browser, "backend", "off"),
        (memory, "memory_char_limit", memory_char_limit),
        (memory, "user_char_limit", user_char_limit),
    )
    for section, key, wanted in managed:
        if section.get(key) != wanted:
            section[key] = wanted
            changed = True
    if not changed:
        return False

    fd, temporary = tempfile.mkstemp(prefix=".config.yaml.", dir=config_path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            yaml.safe_dump(config, handle, sort_keys=False, default_flow_style=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, config_path)
        directory_fd = os.open(config_path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    return True


def _thread_ids(path: Path) -> list[str]:
    _regular_file(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise RuntimeError("Discord thread registry must be a non-empty list")
    thread_ids = [str(value).strip() for value in raw]
    if any(not value.isdigit() for value in thread_ids):
        raise RuntimeError("Discord thread registry contains an invalid thread ID")
    if len(set(thread_ids)) != len(thread_ids):
        raise RuntimeError("Discord thread registry contains duplicate thread IDs")
    return thread_ids


def _selected_thread_ids(registry: list[str], requested: list[str]) -> list[str]:
    if not requested:
        return registry
    selected = [str(value).strip() for value in requested]
    if any(not value.isdigit() for value in selected):
        raise RuntimeError("requested replay contains an invalid thread ID")
    if len(set(selected)) != len(selected):
        raise RuntimeError("requested replay contains duplicate thread IDs")
    unknown = sorted(set(selected) - set(registry))
    if unknown:
        raise RuntimeError(f"requested replay contains unregistered thread IDs: {unknown}")
    return selected


def mark_registered_threads(
    home: Path,
    expected_user_id: str,
    marker: Path,
    requested_thread_ids: list[str],
) -> int:
    """Atomically mark a validated David-owned thread set for one replay."""
    registry = _thread_ids(home / "discord_threads.json")
    thread_ids = _selected_thread_ids(registry, requested_thread_ids)
    if _regular_file(marker, required=False):
        recorded = json.loads(marker.read_text(encoding="utf-8"))
        if (
            recorded.get("migration") != MIGRATION_ID
            or recorded.get("thread_ids") != thread_ids
            or recorded.get("user_id") != expected_user_id
        ):
            raise RuntimeError(f"unexpected replay marker content: {marker}")
        print(f"Replay migration already complete for {len(recorded['thread_ids'])} thread(s)")
        return 0

    os.environ["HERMES_HOME"] = str(home)

    from gateway.config import GatewayConfig, Platform
    from gateway.session import SessionStore

    sessions_dir = home / "sessions"
    config = GatewayConfig(sessions_dir=sessions_dir)
    store = SessionStore(sessions_dir=sessions_dir, config=config)

    with store._lock:  # The gateway is stopped; hold the store's persistence lock.
        store._ensure_loaded_locked()
        by_thread: dict[str, list[Any]] = {thread_id: [] for thread_id in thread_ids}
        for entry in store._entries.values():
            origin = entry.origin
            if origin is None or origin.platform != Platform.DISCORD:
                continue
            thread_id = str(origin.thread_id or "")
            if thread_id in by_thread:
                by_thread[thread_id].append(entry)

        problems: list[str] = []
        selected: list[Any] = []
        for thread_id in thread_ids:
            matches = by_thread[thread_id]
            if len(matches) != 1:
                problems.append(f"thread {thread_id} has {len(matches)} routing entries")
                continue
            entry = matches[0]
            origin = entry.origin
            if str(origin.user_id or "") != expected_user_id:
                problems.append(f"thread {thread_id} is not owned by the expected user")
                continue
            if ":discord:thread:" not in entry.session_key:
                problems.append(f"thread {thread_id} is not routed as a Discord thread")
                continue
            selected.append(entry)

        if problems or len(selected) != len(thread_ids):
            detail = "; ".join(problems) or "selected thread count mismatch"
            raise RuntimeError(f"replay validation failed: {detail}")

        marked_at = datetime.now()
        for entry in selected:
            # This migration is the explicit operator recovery. It supersedes
            # a stale /stop or crash marker, but only for the exact validated
            # David-owned thread set above.
            entry.suspended = False
            entry.resume_pending = True
            entry.resume_reason = REPLAY_REASON
            entry.last_resume_marked_at = marked_at
            entry.active_turn_token = None
            entry.active_turn_started_at = None
        store._save()

    _atomic_json(
        marker,
        {
            "migration": MIGRATION_ID,
            "marked_at": marked_at.isoformat(),
            "thread_ids": thread_ids,
            "session_keys": [entry.session_key for entry in selected],
            "user_id": expected_user_id,
        },
    )
    print(f"Marked {len(selected)} validated Discord thread(s) for operator replay")
    return len(selected)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--home", type=Path, default=Path("/opt/data"))
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--timezone", required=True)
    parser.add_argument("--memory-char-limit", type=int, required=True)
    parser.add_argument("--user-char-limit", type=int, required=True)
    parser.add_argument("--replay-thread-id", action="append", default=[])
    args = parser.parse_args()

    home = args.home.resolve(strict=True)
    if not home.is_dir():
        raise RuntimeError(f"Hermes home is not a directory: {home}")
    if not args.user_id.isdigit():
        raise RuntimeError("expected Discord user ID must be numeric")
    configure_timezone(args.timezone)

    changed = configure_runtime_config(
        home / "config.yaml", args.memory_char_limit, args.user_char_limit
    )
    print("Reconciled managed runtime config" if changed else "Managed runtime config already current")
    mark_registered_threads(
        home,
        args.user_id,
        home / "migrations" / f"{MIGRATION_ID}.json",
        args.replay_thread_id,
    )


if __name__ == "__main__":
    main()
