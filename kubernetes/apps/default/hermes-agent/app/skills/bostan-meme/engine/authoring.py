"""Runtime authorship contract and novelty checks for Bostan posters."""

from __future__ import annotations

import hashlib
import json
import random
import re
from pathlib import Path
from typing import Any

from premises import ANGLES, FAMILIES


TOKEN = re.compile(r"[A-Z0-9]+")
ITEM_SHAPES = {"dialogue", "wealth_recipe", "ranked", "timeline", "checklist", "daily_list", "agenda", "ledger"}
BUREAUCRACY_WORDS = {
    "APPOINTED", "APPROVAL", "BRIEFING", "COMMITTEE", "DIRECTOR", "FEE",
    "FEES", "INSPECTION", "MANAGER", "MINISTER", "MINISTRY", "MUNICIPAL",
    "PERMIT", "POLICY", "REPORTS",
}
BUREAUCRACY_SETTINGS = {"BOARD", "COUNCIL", "ELECTION", "GOVERNMENT", "MEETING", "OFFICE"}


def words(value: str) -> set[str]:
    return set(TOKEN.findall(value.upper()))


def similarity(left: str, right: str) -> float:
    left_words = words(left)
    right_words = words(right)
    if not left_words or not right_words:
        return 0.0
    return len(left_words & right_words) / len(left_words | right_words)


def spec_text(spec: dict[str, Any]) -> str:
    values = [str(spec.get("top", "")), str(spec.get("key", "")), str(spec.get("quote", ""))]
    for lead, punch in spec.get("items", []):
        values.extend([str(lead), str(punch)])
    values.extend(str(value) for value in spec.get("left_items", []))
    values.extend(str(value) for value in spec.get("right_items", []))
    return " ".join(values)


def select_guidance(seed: str, recent_keys: list[str] | None = None) -> dict[str, Any]:
    """Choose one family-local title, world, and tension deterministically."""
    rng = random.Random(int(hashlib.sha256(seed.encode()).hexdigest(), 16))
    recent = set((recent_keys or [])[-40:])
    options: list[dict[str, Any]] = []
    for family_name, family in FAMILIES.items():
        for title_index, title in enumerate(family["titles"]):
            world_index = title_index
            tension_index = rng.randrange(len(family["tensions"]))
            angle_index = rng.randrange(len(ANGLES))
            key = f"{family_name}:{title_index}:{world_index}:{tension_index}:{angle_index}"
            if key not in recent:
                options.append(
                    {
                        "key": key,
                        "family": family_name,
                        "shape": family_name,
                        "top": title[0],
                        "title_key": title[1],
                        "world": family["worlds"][world_index],
                        "tension": family["tensions"][tension_index],
                        "angle": ANGLES[angle_index],
                        "layouts": family["layouts"],
                    }
                )
    return rng.choice(options or [
        {
            "key": "dialogue:0:0:0",
            "family": "dialogue",
            "shape": "dialogue",
            "top": FAMILIES["dialogue"]["titles"][0][0],
            "title_key": FAMILIES["dialogue"]["titles"][0][1],
            "world": FAMILIES["dialogue"]["worlds"][0],
            "tension": FAMILIES["dialogue"]["tensions"][0],
            "angle": ANGLES[0],
            "layouts": FAMILIES["dialogue"]["layouts"],
        }
    ])


def author_prompt(
    guidance: dict[str, Any],
    recent_specs: list[dict[str, Any]] | None = None,
    *,
    correction: dict[str, Any] | None = None,
) -> str:
    """Build the prompt Herm uses to reason about fresh copy at execution time."""
    recent = [
        {
            "title": f"{item.get('top', '')} {item.get('key', '')}".strip(),
            "topic": item.get("topic", ""),
            "shape": item.get("shape", ""),
            "layout": item.get("layout", ""),
            "text": spec_text(item),
        }
        for item in (recent_specs or [])[-12:]
    ]
    contract = {
        "id": "short-kebab-case",
        "topic": "2-5 plain words, at most 30 characters; this is visible copy",
        "shape": guidance["shape"],
        "layout": f"one of {guidance['layouts']}",
        "top": "headline line one",
        "key": "headline line two",
        "items": (
            "exactly eight [lead, punch] pairs"
            if guidance["shape"] == "timeline"
            else "exactly five [lead, punch] pairs for item-based shapes"
        ),
        "quote": "quote shapes only",
        "left_title": "comparison shapes only",
        "left_items": ["exactly four comparison rows, each at most 28 characters"],
        "right_title": "comparison shapes only",
        "right_items": ["exactly four comparison rows, each at most 28 characters"],
    }
    lines = [
            "Author six complete candidate Bostan posters, then return only the strongest JSON object.",
            "The saved references supply rhythm and composition, not reusable lore or captions.",
            "Every candidate needs one recognizable comic situation. Every row must refer to an action, object, role, or consequence that belongs to the exact scene named by the headline.",
            "The headline must read as a natural human sentence even when its claim is absurd. Never invent phrases such as 'municipal afternoon' that need interpretation before they can be funny.",
            "Use one conceptual leap only: begin with an ordinary scene, introduce one absurd rule, then make the five rows progress through setup, escalation, consequence, climax, and payoff.",
            "Do not default to managers, permits, committees, inspections, policy, fees, briefings, municipal jargon, or fake corporate authority. Use those only when the supplied situation explicitly calls for bureaucracy.",
            "For daily_list only, a bilingual count parenthetical such as FIVE (CINCO) is allowed. It is a small surface gag, not permission for unrelated items.",
            "Make the logic absurd but causal: the strange action should be a warped response to the headline's situation. Reject random-noun combinations, strained grammar, and rows that could be moved under an unrelated title unchanged.",
            "Before returning the winner, silently test all five rows against the headline. If a row has no concrete semantic connection, rewrite it.",
            "Do not use rare fish unless the chosen situation specifically requires one, and never build a recurring fish universe.",
            "Prefer the supplied title, but invent a better new title when it is more original and still fits the same joke shape.",
            "Use short visible copy. No explanation, hashtags, attribution, moral, or generic motivational footer.",
            "For dialogue, wealth_recipe, ranked, checklist, daily_list, agenda, and ledger, write exactly five item pairs. For timeline, write exactly eight.",
            "For comparison, write exactly four concise items on each side. For quote, write one 45-190 character quote.",
            "Every comparison item must be at most 28 characters, including spaces.",
            f"Joke shape: {guidance['shape']}",
            f"Suggested title: {guidance['top']} / {guidance['title_key']}",
            f"Coherent world: {guidance['world']}",
            f"Narrative tension: {guidance['tension']}",
            f"Comic angle: {guidance['angle']}",
            f"Allowed layouts: {json.dumps(guidance['layouts'])}",
            f"Recent posters to avoid resembling: {json.dumps(recent, ensure_ascii=False)}",
    ]
    if correction:
        delivery = correction.get("delivery") or {}
        lines.extend(
            [
                "This is a correction of a previously delivered poster.",
                f"Previous exact spec: {json.dumps(delivery.get('spec') or {}, ensure_ascii=False)}",
                f"Earlier feedback on it: {json.dumps(correction.get('feedback') or [], ensure_ascii=False)}",
                f"Current feedback to fix: {json.dumps(correction.get('current_feedback') or '', ensure_ascii=False)}",
                "Preserve elements the feedback did not criticize. Correct the stated visual or copy problem, and return a new id.",
            ]
        )
    lines.append(f"Output contract: {json.dumps(contract)}")
    return "\n".join(lines)


def validate_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Validate model-authored copy before it can reach the renderer."""
    required = ["id", "topic", "shape", "layout", "top", "key"]
    for field in required:
        if not isinstance(spec.get(field), str) or not spec[field].strip():
            raise ValueError(f"missing or invalid {field}")
    if spec["shape"] not in FAMILIES:
        raise ValueError("unknown shape")
    if spec["layout"] not in FAMILIES[spec["shape"]]["layouts"]:
        raise ValueError("layout is incompatible with shape")
    if len(spec["topic"]) > 30 or not 2 <= len(spec["topic"].split()) <= 5:
        raise ValueError("topic must be 2-5 plain words and at most 30 characters")
    if len(spec["top"]) > 42 or len(spec["key"]) > 42:
        raise ValueError("headline is too long")
    visible_words = words(spec_text(spec))
    if (
        len(visible_words & BUREAUCRACY_WORDS) >= 3
        and not visible_words & BUREAUCRACY_SETTINGS
    ):
        raise ValueError("generic bureaucracy is carrying an unrelated premise")
    if spec["shape"] in ITEM_SHAPES:
        items = spec.get("items")
        expected = 8 if spec["shape"] == "timeline" else 5
        if not isinstance(items, list) or len(items) != expected:
            raise ValueError(f"{spec['shape']} requires {expected} items")
        for item in items:
            if not isinstance(item, list) or len(item) != 2:
                raise ValueError("each item must be a two-string pair")
            if not all(isinstance(value, str) and value.strip() for value in item):
                raise ValueError("item values must be nonempty strings")
            if max(len(item[0]), len(item[1])) > 34:
                raise ValueError("item copy is too long")
    elif spec["shape"] == "quote":
        quote = spec.get("quote")
        if not isinstance(quote, str) or not 45 <= len(quote) <= 190:
            raise ValueError("quote must contain 45 to 190 characters")
    elif spec["shape"] == "comparison":
        for side in ("left", "right"):
            title = spec.get(f"{side}_title")
            items = spec.get(f"{side}_items")
            if not isinstance(title, str) or not title.strip() or len(title) > 32:
                raise ValueError(f"invalid {side} title")
            if not isinstance(items, list) or len(items) != 4:
                raise ValueError(f"{side} comparison requires four items")
            if not all(isinstance(value, str) and 1 <= len(value) <= 28 for value in items):
                raise ValueError(f"invalid {side} comparison item")
    return spec


def novelty_score(spec: dict[str, Any], recent_specs: list[dict[str, Any]]) -> float:
    """Reject near-copies and score the remaining candidate from zero to one."""
    validate_spec(spec)
    title = f"{spec['top']} {spec['key']}"
    body = spec_text(spec)
    worst = 0.0
    for recent in recent_specs[-24:]:
        title_match = similarity(title, f"{recent.get('top', '')} {recent.get('key', '')}")
        body_match = similarity(body, spec_text(recent))
        if title_match >= 0.62 or body_match >= 0.48:
            raise ValueError("candidate is too similar to recent output")
        worst = max(worst, title_match * 0.45 + body_match * 0.55)
    return round(1.0 - worst, 4)


def load_recent(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []
    return payload if isinstance(payload, list) else []
