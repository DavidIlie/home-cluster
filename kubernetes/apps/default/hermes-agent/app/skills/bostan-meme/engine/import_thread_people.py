#!/usr/bin/env python3
"""Import the explicitly supplied thread portraits into the people pool."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parent
DESTINATION = ROOT / "assets" / "people"
TRANSPARENT = ROOT / "assets" / "transparent"


@dataclass(frozen=True)
class Portrait:
    source: str
    destination: str
    category: str
    framing: str
    crop: tuple[int, int, int, int] | None = None


# These labels describe only what the uploader established. Do not infer names
# for the people in the friend photos.
PORTRAITS = (
    Portrait(
        "1541209922392428604-1541209920462917643-IMG_5903.png",
        "david-car.png",
        "david",
        "head-and-shoulders",
        (0, 280, 1206, 2340),
    ),
    Portrait(
        "1541209922392428604-1541209920916033627-IMG_5897.jpg",
        "david-event.jpg",
        "david",
        "half-body",
        (430, 80, 1000, 1086),
    ),
    Portrait(
        "1541209922392428604-1541209921830387762-687997F6-F9FE-46C4-8B7A-2977CECC225F.jpg",
        "friend-city.jpg",
        "friend",
        "half-body",
        (500, 800, 1660, 3840),
    ),
    Portrait(
        "1541210250592653423-1541210248528924732-IMG_4388.jpg",
        "friend-closeup.jpg",
        "friend",
        "closeup",
    ),
    Portrait(
        "1541210385515028520-1541210385225351198-IMG_3436.jpg",
        "friend-jacket.jpg",
        "friend",
        "half-body",
    ),
    Portrait(
        "1541209922392428604-1541209919984771092-IMG_6045.jpg",
        "friend-studio.jpg",
        "friend",
        "half-body",
    ),
    Portrait(
        "1541210321719664710-1541210320314310782-IMG_3922.png",
        "thread-suit.png",
        "reference",
        "half-body",
        (240, 143, 820, 748),
    ),
    Portrait(
        "1541210250592653423-1541210250491858974-IMG_3985.png",
        "thread-garage.png",
        "reference",
        "full-body",
        (220, 240, 1206, 1830),
    ),
    Portrait(
        "1541210250592653423-1541210249325838406-IMG_4104.png",
        "thread-formal.png",
        "reference",
        "head-and-shoulders",
        (0, 580, 1206, 1487),
    ),
)

LEGACY_DESTINATIONS = {
    "david-conference.jpg",
    "friend-curly-city.jpg",
    "friend-curly-room.jpg",
    "friend-room.jpg",
    "public-studio-portrait.jpg",
    "thread-diner.jpg",
}


def valid_image(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            image.verify()
    except (OSError, ValueError):
        return False
    return path.stat().st_size > 0


def write_portrait(
    source: Path,
    destination: Path,
    crop: tuple[int, int, int, int] | None,
) -> None:
    temporary = destination.with_name(f".{destination.name}.tmp")
    temporary.unlink(missing_ok=True)
    if crop is None:
        shutil.copyfile(source, temporary)
    else:
        with Image.open(source) as opened:
            image = ImageOps.exif_transpose(opened)
            left, top, right, bottom = crop
            if left < 0 or top < 0 or right > image.width or bottom > image.height:
                raise ValueError(
                    f"crop {crop} exceeds {image.width}x{image.height} "
                    f"source {source.name}"
                )
            if left >= right or top >= bottom:
                raise ValueError(f"empty crop {crop} for {source.name}")
            image = image.crop(crop)
            if destination.suffix.lower() in {".jpg", ".jpeg"}:
                image.convert("RGB").save(temporary, format="JPEG", quality=95, optimize=True)
            else:
                image.save(temporary, format="PNG", optimize=True)
    if not valid_image(temporary):
        temporary.unlink(missing_ok=True)
        raise ValueError(f"invalid imported portrait from {source.name}")
    os.replace(temporary, destination)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=ROOT / "references" / "thread")
    args = parser.parse_args()
    DESTINATION.mkdir(parents=True, exist_ok=True)
    imported = []
    missing = []
    for portrait in PORTRAITS:
        source = args.source_dir / portrait.source
        if not source.is_file() or not valid_image(source):
            missing.append(portrait.source)
            continue
        destination = DESTINATION / portrait.destination
        write_portrait(source, destination, portrait.crop)
        imported.append(
            {
                "name": portrait.destination,
                "category": portrait.category,
                "framing": portrait.framing,
                "cropped": portrait.crop is not None,
            }
        )
    if not missing:
        for name in LEGACY_DESTINATIONS:
            (DESTINATION / name).unlink(missing_ok=True)
            (TRANSPARENT / f"{Path(name).stem}.png").unlink(missing_ok=True)
    print(json.dumps({"imported": imported, "missing": missing}, sort_keys=True))
    if missing:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
