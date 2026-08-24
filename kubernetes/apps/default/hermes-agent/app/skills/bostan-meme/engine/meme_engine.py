#!/usr/bin/env python3
"""Render source-faithful absurd mindset posters from an authored joke corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from authoring import validate_spec
from corpus import POSTERS


ROOT = Path(__file__).resolve().parent
PEOPLE = ROOT / "assets" / "transparent"
OUT = ROOT / "output"
STATE = ROOT / "state.json"
FONT = ROOT / "fonts" / "BebasNeue-Regular.ttf"
WHITE = "#eeeae1"
BRIGHT = ["#f4d21f", "#39c86e", "#ef4055", "#24a9e0", "#c978ea", "#ff8b24"]
MUTED = ["#a35d59", "#c0933f", "#607841", "#9b672c", "#79765a"]
LAYOUTS = [
    "hostile_dialogue",
    "comparison_board",
    "single_quote",
    "timetable",
    "right_cutout",
    "closeup_ranked",
    "giant_keyword",
    "split_ledger",
    "protocol_card",
    "left_editorial",
]
EXCLUDED_PEOPLE = {"bill-gates.png", "thread-formal.png", "thread-garage.png"}


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT), size)


def fit(value: str, max_width: int, start: int, minimum: int = 24) -> ImageFont.FreeTypeFont:
    for size in range(start, minimum - 1, -2):
        candidate = font(size)
        if candidate.getlength(value) <= max_width:
            return candidate
    return font(minimum)


def load_state() -> dict[str, list]:
    default = {"posters": [], "topics": [], "shapes": [], "people": [], "layouts": []}
    try:
        payload = json.loads(STATE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default
    if not isinstance(payload, dict):
        return default
    aliases = {
        "posters": ("posters", "frames", "content", "recent_posters"),
        "topics": ("topics", "motifs"),
        "shapes": ("shapes",),
        "people": ("people", "recent_people"),
        "layouts": ("layouts", "recent_styles"),
    }
    migrated: dict[str, list] = {}
    for key, candidates in aliases.items():
        value = []
        for candidate in candidates:
            if isinstance(payload.get(candidate), list):
                value = payload[candidate]
                break
        migrated[key] = value
    return migrated


def choose(rng: random.Random, values: list, recent: list, window: int):
    available = [value for value in values if value not in recent[-window:]]
    return rng.choice(available or values)


def valid_people() -> list[Path]:
    files = []
    for path in sorted(PEOPLE.glob("*.png")):
        if path.name in EXCLUDED_PEOPLE:
            continue
        if path.stat().st_size == 0:
            continue
        try:
            with Image.open(path) as candidate:
                candidate.verify()
        except (OSError, ValueError):
            continue
        files.append(path)
    return files


def person_layer(path: Path, size: tuple[int, int], grayscale: bool = False) -> Image.Image:
    cutout = Image.open(path).convert("RGBA")
    cutout.thumbnail(size, Image.Resampling.LANCZOS)
    if grayscale:
        rgb = ImageEnhance.Contrast(cutout.convert("RGB").convert("L")).enhance(1.55).convert("RGB")
        cutout = Image.merge("RGBA", (*rgb.split(), cutout.getchannel("A")))
    return cutout


def person_cover(
    path: Path,
    size: tuple[int, int],
    *,
    grayscale: bool = False,
    vertical_anchor: float = 0.08,
) -> Image.Image:
    """Crop a portrait into a deliberate photo area instead of shrinking it."""
    cutout = Image.open(path).convert("RGBA")
    scale = max(size[0] / cutout.width, size[1] / cutout.height)
    resized = cutout.resize(
        (max(size[0], round(cutout.width * scale)), max(size[1], round(cutout.height * scale))),
        Image.Resampling.LANCZOS,
    )
    left = max(0, (resized.width - size[0]) // 2)
    available_y = max(0, resized.height - size[1])
    top = min(available_y, max(0, round(available_y * vertical_anchor)))
    cropped = resized.crop((left, top, left + size[0], top + size[1]))
    if grayscale:
        rgb = ImageEnhance.Contrast(cropped.convert("RGB").convert("L")).enhance(1.55).convert("RGB")
        cropped = Image.merge("RGBA", (*rgb.split(), cropped.getchannel("A")))
    return cropped


def paste_faded(
    image: Image.Image,
    cutout: Image.Image,
    position: tuple[int, int],
    *,
    fade_left: bool = False,
    fade_bottom: bool = True,
) -> None:
    alpha = cutout.getchannel("A")
    mask = Image.new("L", cutout.size, 255)
    mask_draw = ImageDraw.Draw(mask)
    if fade_left:
        edge = min(170, cutout.width)
        for x in range(edge):
            mask_draw.line((x, 0, x, cutout.height), fill=int(255 * x / edge))
    if fade_bottom:
        edge = min(170, cutout.height)
        for y in range(cutout.height - edge, cutout.height):
            mask_draw.line((0, y, cutout.width, y), fill=int(255 * (cutout.height - y) / edge))
    mask = mask.filter(ImageFilter.GaussianBlur(18))
    cutout.putalpha(Image.composite(alpha, mask, mask))
    image.paste(cutout, position, cutout)


def darken(image: Image.Image, box: tuple[int, int, int, int], opacity: int = 150) -> None:
    """Put a restrained black scrim behind copy that crosses a portrait."""
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rounded_rectangle(box, radius=18, fill=(0, 0, 0, opacity))
    image.paste(Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB"))


def next_text_x(
    draw: ImageDraw.ImageDraw,
    x: int,
    value: str,
    text_font: ImageFont.FreeTypeFont,
    *,
    stroke: int = 0,
    gap: int = 12,
) -> int:
    """Return a stroke-aware x position for adjacent text."""
    bounds = draw.textbbox((x, 0), value, font=text_font, stroke_width=stroke)
    return bounds[2] + gap


def put(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    value: str,
    text_font: ImageFont.FreeTypeFont,
    color: str = WHITE,
    stroke: int = 0,
) -> None:
    draw.text(position, value, font=text_font, fill=color, stroke_width=stroke, stroke_fill="#000")


def wrapped_lines(value: str, text_font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Wrap copy on word boundaries for quote-shaped posters."""
    lines: list[str] = []
    current: list[str] = []
    for word in value.split():
        candidate = " ".join([*current, word])
        if current and text_font.getlength(candidate) > max_width:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def draw_item(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    lead: str,
    punch: str,
    index: int,
    color: str,
    *,
    marker: str = "number",
    size: int = 56,
    underline: bool = False,
) -> None:
    lead_font = fit(lead, 500, size)
    punch_font = fit(punch, 560, size)
    mark = f"{index}." if marker == "number" else ("•" if marker == "bullet" else "—")
    put(draw, (x, y), mark, lead_font)
    put(draw, (x + 62, y), lead, lead_font, WHITE, 2)
    put(draw, (x + 62, y + 55), punch, punch_font, color, 2)
    if underline:
        width = draw.textlength(punch, font=punch_font)
        draw.rectangle((x + 62, y + 111, x + 62 + width, y + 116), fill=color)


def render(
    seed: str,
    output: Path,
    *,
    poster_index: int | None = None,
    spec: dict[str, object] | None = None,
    layout_name: str | None = None,
    person_name: str | None = None,
    update_state: bool = True,
) -> dict[str, object]:
    rng = random.Random(int(hashlib.sha256(seed.encode()).hexdigest(), 16))
    history = load_state()
    selected_poster = poster_index
    if spec is not None:
        blueprint = validate_spec(dict(spec))
        selected_poster = -1
    elif selected_poster is None:
        candidates = [
            index
            for index, candidate in enumerate(POSTERS)
            if index not in history["posters"][-(len(POSTERS) - 1) :]
            and str(candidate["layout"]) not in history["layouts"][-5:]
            and str(candidate["shape"]) not in history["shapes"][-3:]
        ]
        if not candidates:
            candidates = [
                index
                for index in range(len(POSTERS))
                if index not in history["posters"][-(len(POSTERS) - 1) :]
            ]
        selected_poster = rng.choice(candidates or list(range(len(POSTERS))))
        blueprint = POSTERS[selected_poster]
    else:
        blueprint = POSTERS[selected_poster]
    default_layout = str(blueprint["layout"])
    layout = layout_name or default_layout
    if layout not in LAYOUTS:
        raise ValueError(f"Unknown layout: {layout}")

    people = valid_people()
    if not people:
        raise RuntimeError(f"No valid transparent portraits in {PEOPLE}")
    selected_person = person_name or choose(
        rng,
        [path.name for path in people],
        history["people"],
        min(10, len(people) - 1),
    )
    person_path = PEOPLE / selected_person
    if person_path not in people:
        raise ValueError(f"Unknown portrait: {selected_person}")
    top = str(blueprint["top"])
    key = str(blueprint["key"])
    items = list(blueprint.get("items", []))
    topic = str(blueprint["topic"])

    if update_state:
        if selected_poster >= 0:
            history["posters"] = (history["posters"] + [selected_poster])[-32:]
        history["topics"] = (history["topics"] + [topic])[-32:]
        history["shapes"] = (history["shapes"] + [str(blueprint["shape"])])[-16:]
        history["layouts"] = (history["layouts"] + [layout])[-18:]
        history["people"] = (history["people"] + [selected_person])[-24:]
        STATE.write_text(json.dumps(history, indent=2), encoding="utf-8")

    width, height = 1080, 1350
    image = Image.new("RGB", (width, height), "#050505")
    draw = ImageDraw.Draw(image)
    offset = rng.randrange(len(BRIGHT))
    colors = [BRIGHT[(offset + index) % len(BRIGHT)] for index in range(max(2, len(items)))]
    accent = colors[0]
    footer_x = 65
    footer_y = 1295

    if layout == "hostile_dialogue":
        cutout = person_layer(person_path, (560, 1030))
        image.paste(cutout, (width - cutout.width + 30, height - cutout.height), cutout)
        darken(image, (30, 20, 1045, 265), 185)
        darken(image, (30, 285, 760, 1270), 125)
        draw = ImageDraw.Draw(image)
        put(draw, (55, 45), top, fit(top, 970, 86))
        put(draw, (55, 125), key, fit(key, 970, 91), accent)
        y = 310
        for index, (lead, punch) in enumerate(items, 1):
            put(draw, (65, y), "—", font(42), WHITE)
            put(draw, (120, y), str(lead), fit(str(lead), 560, 43), "#aaa")
            put(draw, (120, y + 48), str(punch), fit(str(punch), 600, 57), colors[index - 1], 2)
            y += 175

    elif layout == "comparison_board":
        cutout = person_cover(person_path, (450, 1100), grayscale=True, vertical_anchor=0.02)
        image.paste(cutout, (630, 250), cutout)
        darken(image, (25, 20, 1055, 245), 175)
        darken(image, (25, 255, 660, 1325), 105)
        draw = ImageDraw.Draw(image)
        put(draw, (50, 40), top, fit(top, 980, 79))
        put(draw, (50, 112), key, fit(key, 980, 70), accent)
        left_title = str(blueprint["left_title"])
        right_title = str(blueprint["right_title"])
        left_items = list(blueprint["left_items"])
        right_items = list(blueprint["right_items"])
        put(draw, (55, 285), left_title, fit(left_title, 540, 48), colors[0])
        draw.line((55, 342, 580, 342), fill=colors[0], width=4)
        y = 375
        for value in left_items:
            put(draw, (65, y), "•", font(46), WHITE)
            put(draw, (115, y), str(value), fit(str(value), 470, 48), WHITE, 1)
            y += 105
        second_y = 815
        put(draw, (55, second_y), right_title, fit(right_title, 540, 48), colors[1])
        draw.line((55, second_y + 57, 580, second_y + 57), fill=colors[1], width=4)
        y = second_y + 90
        for value in right_items:
            put(draw, (65, y), "•", font(46), WHITE)
            put(draw, (115, y), str(value), fit(str(value), 470, 48), WHITE, 1)
            y += 95

    elif layout == "single_quote":
        cutout = person_layer(person_path, (500, 1050), grayscale=True)
        image.paste(cutout, (-20, height - cutout.height), cutout)
        darken(image, (420, 60, 1040, 865), 190)
        draw = ImageDraw.Draw(image)
        put(draw, (460, 95), top, fit(top, 530, 58), "#aaa")
        put(draw, (460, 160), key, fit(key, 530, 67), accent)
        draw.line((460, 245, 995, 245), fill=accent, width=5)
        quote_font = font(57)
        quote_lines = wrapped_lines(str(blueprint["quote"]), quote_font, 510)
        y = 290
        for line in quote_lines:
            put(draw, (460, y), line, quote_font, WHITE, 2)
            y += 72
        footer_x = 460

    elif layout == "timetable":
        cutout = person_cover(person_path, (390, 330), vertical_anchor=0.02)
        image.paste(cutout, (650, 20), cutout)
        draw = ImageDraw.Draw(image)
        put(draw, (50, 55), top, fit(top, 570, 67))
        put(draw, (50, 125), key, fit(key, 570, 72), accent)
        draw.line((50, 365, 1030, 365), fill=accent, width=5)
        y = 395
        row_height = min(108, 825 // max(1, len(items)))
        for index, (lead, punch) in enumerate(items):
            put(draw, (55, y), str(lead), fit(str(lead), 180, 47), "#aaa")
            put(draw, (260, y), str(punch), fit(str(punch), 730, 51), colors[index], 2)
            draw.line((55, y + row_height - 17, 1025, y + row_height - 17), fill="#2f2f2f", width=2)
            y += row_height

    elif layout == "cinematic_rows":
        cutout = person_cover(person_path, (500, 1270), grayscale=True)
        image.paste(cutout, (580, 0), cutout)
        darken(image, (25, 25, 560, 1245), 105)
        draw = ImageDraw.Draw(image)
        draw.line((570, 35, 570, 1245), fill=accent, width=5)
        put(draw, (55, 55), top, fit(top, 485, 78))
        put(draw, (55, 128), key, fit(key, 485, 88), accent)
        y = 300
        for index, (lead, punch) in enumerate(items, 1):
            put(draw, (55, y), f"0{index}", font(34), colors[index - 1])
            put(draw, (125, y - 4), lead, fit(lead, 400, 46), WHITE, 2)
            put(draw, (125, y + 47), punch, fit(punch, 400, 54), colors[index - 1], 2)
            draw.line((55, y + 125, 540, y + 125), fill="#343434", width=2)
            y += 174

    elif layout == "routine":
        cutout = person_layer(person_path, (570, 500))
        paste_faded(image, cutout, ((width - cutout.width) // 2, 0))
        darken(image, (45, 475, 1035, 1245), 112)
        draw = ImageDraw.Draw(image)
        draw.line((70, 480, 1010, 480), fill="#8e2ba2", width=6)
        put(draw, (70, 500), top, fit(top, 940, 82))
        put(draw, (70, 580), key, fit(key, 940, 82), "#9d35ae")
        draw.line((70, 675, 1010, 675), fill="#8e2ba2", width=6)
        y = 700
        for index, (lead, punch) in enumerate(items, 1):
            row_font = fit(f"{lead} : {punch}", 900, 49)
            put(draw, (80, y), lead, row_font)
            separator_x = 80 + int(draw.textlength(lead, font=row_font)) + 22
            punch_x = separator_x + int(draw.textlength(":", font=row_font)) + 32
            put(draw, (separator_x, y), ":", row_font)
            put(draw, (punch_x, y), punch, row_font, colors[(index - 1) % len(colors)], 2)
            draw.line((70, y + 70, 1010, y + 70), fill="#34343a", width=2)
            y += 85

    elif layout == "closeup_ranked":
        cutout = person_layer(person_path, (730, 1240), grayscale=True)
        paste_faded(image, cutout, (width - cutout.width + 80, 150), fade_left=True)
        darken(image, (35, 260, 735, 1245), 145)
        draw = ImageDraw.Draw(image)
        put(draw, (65, 48), top, fit(top, 950, 92))
        put(draw, (65, 135), key, fit(key, 950, 92), accent)
        y = 290
        for index, (lead, punch) in enumerate(items, 1):
            if str(lead).isdigit():
                put(draw, (65, y), f"{index}.", font(53), WHITE)
                put(draw, (128, y), str(punch), fit(str(punch), 540, 56), colors[index - 1], 2)
            else:
                draw_item(draw, 65, y, lead, punch, index, colors[(index - 1) % len(colors)], size=53)
            y += 190

    elif layout == "giant_keyword":
        cutout = person_layer(person_path, (650, 1050), grayscale=True)
        paste_faded(image, cutout, (500, 260), fade_left=True)
        darken(image, (35, 345, 735, 1260), 145)
        draw = ImageDraw.Draw(image)
        put(draw, (70, 35), top, fit(top, 930, 100))
        key_font = fit(key, 860, 155)
        put(draw, (70, 125), key, key_font, accent)
        draw.rectangle((70, 285, 70 + draw.textlength(key, font=key_font), 294), fill=accent)
        y = 380
        for index, (lead, punch) in enumerate(items, 1):
            draw_item(
                draw,
                65,
                y,
                lead,
                punch,
                index,
                colors[(index - 1) % len(colors)],
                marker=rng.choice(["bullet", "dash"]),
                size=57,
                underline=rng.random() < 0.5,
            )
            y += 185

    elif layout == "circle_manifesto":
        cutout = person_layer(person_path, (520, 620))
        paste_faded(image, cutout, (width - cutout.width + 20, height - cutout.height + 20), fade_left=True)
        darken(image, (35, 255, 825, 960), 125)
        darken(image, (35, 1090, 785, 1215), 150)
        draw = ImageDraw.Draw(image)
        put(draw, (55, 55), top, fit(top, 970, 80))
        put(draw, (55, 128), key, fit(key, 970, 80), accent)
        draw.rectangle((55, 220, 1025, 225), fill=accent)
        y = 285
        for index, (lead, punch) in enumerate(items, 1):
            row_font = fit(f"{lead} {punch}", 760, 55)
            put(draw, (65, y), "—", row_font)
            put(draw, (120, y), f"{lead} ", row_font, WHITE, 2)
            x = next_text_x(draw, 120, f"{lead} ", row_font, stroke=2)
            put(draw, (x, y), punch, row_font, colors[(index - 1) % len(colors)], 2)
            y += 130
        put(draw, (65, 1130), "YOUR NETWORK IS YOUR NET WORTH", fit("YOUR NETWORK IS YOUR NET WORTH", 700, 55), "#c978ea")

    elif layout == "split_ledger":
        cutout = person_cover(person_path, (410, 270), grayscale=True, vertical_anchor=0.02)
        image.paste(cutout, (630, 20), cutout)
        draw = ImageDraw.Draw(image)
        put(draw, (55, 55), top, fit(top, 540, 86))
        put(draw, (55, 137), key, fit(key, 540, 96), accent)
        draw.rounded_rectangle((620, 15, 1045, 300), radius=14, outline="#333", width=3)
        draw.line((540, 325, 540, 1230), fill="#383838", width=4)
        for index, (lead, punch) in enumerate(items):
            column = index % 2
            row = index // 2
            x = 55 + column * 510
            y = 390 + row * 260
            put(draw, (x, y), f"0{index + 1}", font(38), colors[index])
            put(draw, (x, y + 52), lead, fit(lead, 440, 60), WHITE, 2)
            put(draw, (x, y + 112), punch, fit(punch, 440, 66), colors[index], 2)
            draw.line((x, y + 202, x + 430, y + 202), fill="#2e2e2e", width=3)

    elif layout == "protocol_card":
        cutout = person_cover(person_path, (320, 275), vertical_anchor=0.03)
        image.paste(cutout, (700, 40), cutout)
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((685, 25, 1035, 330), radius=14, outline="#383838", width=3)
        put(draw, (58, 52), "CONFIDENTIAL / 06", font(34), "#777")
        put(draw, (58, 115), top, fit(top, 590, 78))
        put(draw, (58, 188), key, fit(key, 590, 86), accent)
        y = 370
        for index, (lead, punch) in enumerate(items, 1):
            draw.rounded_rectangle((55, y, 1025, y + 145), radius=8, outline="#333", width=3)
            put(draw, (82, y + 22), f"{index:02}", font(41), colors[index - 1])
            put(draw, (175, y + 17), lead, fit(lead, 370, 53))
            put(draw, (175, y + 71), punch, fit(punch, 790, 60), colors[index - 1], 2)
            y += 166

    elif layout == "quote_wall":
        cutout = person_layer(person_path, (700, 1160), grayscale=True)
        paste_faded(image, cutout, (width - cutout.width + 80, 210), fade_left=True)
        darken(image, (35, 300, 1035, 1115), 145)
        darken(image, (35, 1115, 760, 1230), 135)
        draw = ImageDraw.Draw(image)
        put(draw, (65, 50), top, fit(top, 940, 80), "#aaa")
        put(draw, (65, 125), key, fit(key, 900, 118), accent)
        y = 335
        for index, (lead, punch) in enumerate(items, 1):
            phrase = f"{lead} {punch}"
            phrase_font = fit(phrase, 880, 62)
            put(draw, (65, y), phrase, phrase_font, colors[(index - 1) % len(colors)], 2)
            y += 154
        put(draw, (65, 1145), "READ THAT AGAIN.", font(48), WHITE)

    elif layout == "left_editorial":
        cutout = person_cover(person_path, (440, 1055), grayscale=True, vertical_anchor=0.03)
        image.paste(cutout, (15, 250), cutout)
        darken(image, (25, 25, 455, 270), 145)
        darken(image, (475, 25, 1050, 1245), 120)
        draw = ImageDraw.Draw(image)
        draw.line((470, 35, 470, 1245), fill=accent, width=5)
        put(draw, (515, 55), top, fit(top, 500, 74))
        put(draw, (515, 122), key, fit(key, 500, 84), accent)
        y = 285
        for index, (lead, punch) in enumerate(items, 1):
            put(draw, (515, y), f"0{index}", font(34), colors[index - 1])
            put(draw, (585, y - 3), lead, fit(lead, 420, 49), WHITE, 2)
            put(draw, (585, y + 49), punch, fit(punch, 420, 55), colors[index - 1], 2)
            draw.line((515, y + 125, 1025, y + 125), fill="#333", width=2)
            y += 166
        footer_x = 515

    elif layout == "bottom_portrait":
        draw = ImageDraw.Draw(image)
        put(draw, (55, 45), top, fit(top, 970, 82))
        put(draw, (55, 118), key, fit(key, 970, 92), accent)
        draw.line((55, 225, 1025, 225), fill=accent, width=5)
        y = 255
        for index, (lead, punch) in enumerate(items, 1):
            row_font = fit(f"{lead} {punch}", 850, 48)
            put(draw, (55, y), f"{index}.", row_font, colors[index - 1])
            put(draw, (125, y), f"{lead} ", row_font, WHITE, 2)
            punch_x = next_text_x(draw, 125, f"{lead} ", row_font, stroke=2, gap=10)
            put(draw, (punch_x, y), punch, row_font, colors[index - 1], 2)
            draw.line((55, y + 68, 1025, y + 68), fill="#303030", width=2)
            y += 100
        cutout = person_cover(person_path, (970, 535), vertical_anchor=0.0)
        image.paste(cutout, (55, height - cutout.height), cutout)
        draw = ImageDraw.Draw(image)
        footer_y = 780

    elif layout == "portrait_header_grid":
        cutout = person_cover(person_path, (970, 390), vertical_anchor=0.0)
        image.paste(cutout, (55, 0), cutout)
        darken(image, (30, 390, 1050, 625), 185)
        draw = ImageDraw.Draw(image)
        put(draw, (55, 415), top, fit(top, 970, 78))
        put(draw, (55, 485), key, fit(key, 970, 92), accent)
        for index, (lead, punch) in enumerate(items):
            column = index % 2
            row = index // 2
            x = 55 + column * 510
            y = 665 + row * 180
            put(draw, (x, y), f"0{index + 1}", font(32), colors[index])
            put(draw, (x + 65, y - 3), lead, fit(lead, 410, 44), WHITE, 2)
            put(draw, (x + 65, y + 45), punch, fit(punch, 410, 50), colors[index], 2)
            draw.line((x, y + 125, x + 445, y + 125), fill="#303030", width=2)

    else:
        cutout = person_layer(person_path, (590, 1100))
        paste_faded(image, cutout, (width - cutout.width + 35, height - cutout.height + 35), fade_left=True)
        darken(image, (35, 270, 735, 1235), 145)
        draw = ImageDraw.Draw(image)
        put(draw, (70, 45), top, fit(top, 930, 91))
        put(draw, (70, 125), key, fit(key, 900, 108), accent)
        y = 300
        for index, (lead, punch) in enumerate(items, 1):
            if str(lead).isdigit():
                put(draw, (65, y), f"{index}.", font(54), WHITE)
                put(draw, (135, y), str(punch), fit(str(punch), 560, 56), colors[index - 1], 2)
            else:
                draw_item(draw, 65, y, lead, punch, index, colors[(index - 1) % len(colors)], marker="dash", size=54)
            y += 185

    put(draw, (footer_x, footer_y), "@BOSTANMINDSET", font(28), accent)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, optimize=True)
    return {
        "png": str(output.resolve()),
        "person": selected_person,
        "layout": layout,
        "poster": str(blueprint["id"]),
        "topic": topic,
        "shape": str(blueprint["shape"]),
        "template": f"{top} {key}",
        "bytes": output.stat().st_size,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seed",
        default=datetime.now(ZoneInfo("Europe/Bucharest")).strftime("%Y-%m-%d-%H"),
    )
    parser.add_argument("--output")
    parser.add_argument("--spec")
    parser.add_argument("--person")
    arguments = parser.parse_args()
    output = Path(arguments.output) if arguments.output else OUT / f"meme-{arguments.seed}.png"
    spec = None
    if arguments.spec:
        spec = json.loads(Path(arguments.spec).read_text(encoding="utf-8"))
    print(json.dumps(render(arguments.seed, output, spec=spec, person_name=arguments.person)))


if __name__ == "__main__":
    main()
