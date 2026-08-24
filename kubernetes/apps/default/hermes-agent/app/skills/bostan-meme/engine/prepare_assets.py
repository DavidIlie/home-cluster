#!/usr/bin/env python3
"""Prepare transparent portraits atomically from the source asset folder."""

from __future__ import annotations

import json
import os
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "assets" / "people"
DESTINATION = ROOT / "assets" / "transparent"
SUPPORTED = {".jpg", ".jpeg", ".png", ".webp"}
LARGEST_SUBJECT_ONLY = {"steve-jobs"}

# Keep the 168 MiB segmentation model on the persistent workspace.  Without
# this, rembg stores it under the container root and downloads it again after
# every rollout that introduces a new portrait.
os.environ.setdefault("REMBG_HOME", str(ROOT / ".rembg"))

from rembg import new_session, remove  # noqa: E402


def keep_largest_subject(portrait: Image.Image) -> Image.Image:
    """Discard disconnected baked-in captions and watermarks around a person."""
    import numpy as np
    from scipy import ndimage

    alpha = np.asarray(portrait.getchannel("A"))
    labels, count = ndimage.label(alpha > 16)
    if count < 2:
        return portrait
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    subject = labels == int(sizes.argmax())
    cleaned = np.where(subject, alpha, 0).astype("uint8")
    portrait.putalpha(Image.fromarray(cleaned, mode="L"))
    return portrait


def clip_steve_jobs_reference(portrait: Image.Image) -> Image.Image:
    """Keep the portrait while excluding the reference poster's baked-in copy."""
    width, height = portrait.size
    guard = Image.new("L", portrait.size, 0)
    ImageDraw.Draw(guard).polygon(
        [
            (round(width * 0.49), 0),
            (width, 0),
            (width, round(height * 0.90)),
            (round(width * 0.66), round(height * 0.90)),
            (round(width * 0.62), round(height * 0.70)),
            (round(width * 0.57), round(height * 0.50)),
            (round(width * 0.52), round(height * 0.25)),
        ],
        fill=255,
    )
    import numpy as np

    alpha = np.asarray(portrait.getchannel("A"))
    guarded = np.minimum(alpha, np.asarray(guard)).astype("uint8")
    portrait.putalpha(Image.fromarray(guarded, mode="L"))
    return portrait


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
                if source.stem in LARGEST_SUBJECT_ONLY:
                    portrait = keep_largest_subject(portrait)
                if source.stem == "steve-jobs":
                    portrait = clip_steve_jobs_reference(portrait)
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
