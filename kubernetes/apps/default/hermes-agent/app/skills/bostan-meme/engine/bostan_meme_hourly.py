#!/usr/bin/env python3
"""Cron entrypoint for the adaptive Bostan engine."""

from __future__ import annotations

import os
import signal
import subprocess
from datetime import datetime
from pathlib import Path


HERMES_HOME = Path(os.environ.get("HERMES_HOME", "/opt/data/profiles/friends-david"))
ENGINE = HERMES_HOME / "workspace" / "meme-engine"
ERROR_LOG = ENGINE / "cron-errors.log"
AUTOMATIC_ENABLED = os.environ.get("BOSTAN_AUTOMATIC_ENABLED", "false").lower() in {
    "1",
    "true",
    "yes",
}


def record_failure(detail: str) -> None:
    """Keep a short local diagnostic without sending scheduler prose to Discord."""
    ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
    line = " ".join(detail.strip().split())[-1200:]
    with ERROR_LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"{datetime.now().isoformat(timespec='seconds')} {line}\n")
    lines = ERROR_LOG.read_text(encoding="utf-8").splitlines()[-100:]
    ERROR_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if not AUTOMATIC_ENABLED:
        print("[SILENT]")
        return
    python = ENGINE / ".venv" / "bin" / "python"
    child = subprocess.Popen(
        [str(python), str(ENGINE / "cron_hourly.py")],
        cwd=ENGINE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    def stop_silently(signum: int, _frame: object) -> None:
        try:
            child.terminate()
            child.wait(timeout=5)
        except Exception:
            child.kill()
        record_failure(f"terminated by signal {signum}")
        print("[SILENT]", flush=True)
        os._exit(0)

    signal.signal(signal.SIGTERM, stop_silently)
    signal.signal(signal.SIGINT, stop_silently)
    try:
        stdout, stderr = child.communicate(timeout=600)
    except subprocess.TimeoutExpired:
        child.kill()
        stdout, stderr = child.communicate()
        record_failure(f"generation timed out; {stderr or stdout}")
        print("[SILENT]")
        return
    if child.returncode != 0:
        record_failure(f"exit {child.returncode}; {stderr or stdout}")
        print("[SILENT]")
        return
    output = stdout.strip()
    if not output.startswith("https://"):
        record_failure(f"unexpected output; {output or stderr}")
        print("[SILENT]")
        return
    print(output)


if __name__ == "__main__":
    main()
