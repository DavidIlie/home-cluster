#!/usr/bin/env python3
"""Cron entrypoint for the adaptive Bostan engine."""

from __future__ import annotations

import os
from pathlib import Path


HERMES_HOME = Path(os.environ.get("HERMES_HOME", "/opt/data/profiles/friends-david"))
ENGINE = HERMES_HOME / "workspace" / "meme-engine"


def main() -> None:
    python = ENGINE / ".venv" / "bin" / "python"
    os.execv(str(python), [str(python), str(ENGINE / "cron_hourly.py")])


if __name__ == "__main__":
    main()
