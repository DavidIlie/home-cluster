#!/usr/bin/env python3
"""Prepare transparent portraits atomically from the source asset folder."""

from __future__ import annotations

import json
import os
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "assets" / "people"
DESTINATION = ROOT / "assets" / "transparent"
SUPPORTED = {".jpg", ".jpeg", ".png", ".webp"}

# Keep the 168 MiB segmentation model on the persistent workspace.  Without
# this, rembg stores it under the container root and downloads it again after
# every rollout that introduces a new portrait.
os.environ.setdefault("REMBG_HOME", str(ROOT / ".rembg"))

from rembg import new_session, remove  # noqa: E402


def is_valid(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        with Image.open(path) as image:
            image.verify()
    except (OSError, ValueError):
        return False
    return True


def main() -> None:
    DESTINATION.mkdir(parents=True, exist_ok=True)
    sources = [
        path
        for path in sorted(SOURCE.iterdir())
        if path.is_file() and path.suffix.lower() in SUPPORTED
    ]
    if not sources:
        raise SystemExit(f"No portrait sources found in {SOURCE}")

    pending = []
    for source in sources:
        destination = DESTINATION / f"{source.stem}.png"
        if is_valid(destination) and destination.stat().st_mtime_ns >= source.stat().st_mtime_ns:
            continue
        destination.unlink(missing_ok=True)
        pending.append((source, destination))

    prepared = 0
    failures: list[str] = []
    if pending:
        session = new_session("u2net_human_seg")
        for source, destination in pending:
            temporary = destination.with_name(f".{destination.name}.tmp")
            temporary.unlink(missing_ok=True)
            try:
                with Image.open(source) as image:
                    portrait = remove(image.convert("RGBA"), session=session)
                if not isinstance(portrait, Image.Image) or portrait.getbbox() is None:
                    raise ValueError("background removal produced an empty image")
                portrait.save(temporary, format="PNG", optimize=True)
                if not is_valid(temporary):
                    raise ValueError("background removal produced an invalid PNG")
                os.replace(temporary, destination)
                prepared += 1
            except Exception as exc:
                temporary.unlink(missing_ok=True)
                failures.append(f"{source.name}: {type(exc).__name__}: {exc}")

    valid = [path for path in DESTINATION.glob("*.png") if is_valid(path)]
    if not valid:
        raise SystemExit("No usable transparent portraits were prepared")

    print(json.dumps({"prepared": prepared, "available": len(valid), "failures": failures}))


if __name__ == "__main__":
    main()
