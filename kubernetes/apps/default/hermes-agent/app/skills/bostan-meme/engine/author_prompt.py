#!/usr/bin/env python3
"""Prepare and validate runtime-authored poster specs for Herm."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from authoring import author_prompt, novelty_score, select_guidance, validate_spec
from feedback import context as feedback_context, rejected_specs


ROOT = Path(__file__).resolve().parent
HISTORY = ROOT / "author-history.json"


def load_history() -> dict[str, list]:
    try:
        payload = json.loads(HISTORY.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"guidance_keys": [], "specs": []}
    if not isinstance(payload, dict):
        return {"guidance_keys": [], "specs": []}
    return {
        "guidance_keys": list(payload.get("guidance_keys", [])),
        "specs": list(payload.get("specs", [])),
    }


def save_history(history: dict[str, list]) -> None:
    temporary = HISTORY.with_suffix(".tmp")
    temporary.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(HISTORY)


def accept_spec(spec: dict, guidance_key: str, *, exclude_spec: dict | None = None) -> float:
    history = load_history()
    validate_spec(spec)
    comparison = [item for item in history["specs"] if item != exclude_spec]
    score = novelty_score(spec, comparison)
    history["guidance_keys"] = (history["guidance_keys"] + [guidance_key])[-100:]
    history["specs"] = (history["specs"] + [spec])[-40:]
    save_history(history)
    return score


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prompt_parser = subparsers.add_parser("prompt")
    prompt_parser.add_argument(
        "--seed",
        default=datetime.now(ZoneInfo("Europe/Bucharest")).isoformat(timespec="minutes"),
    )
    prompt_parser.add_argument("--feedback-url")
    prompt_parser.add_argument("--feedback-file", type=Path)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("spec", type=Path)
    accept_parser = subparsers.add_parser("accept")
    accept_parser.add_argument("spec", type=Path)
    accept_parser.add_argument("--guidance-key", required=True)
    arguments = parser.parse_args()
    history = load_history()

    if arguments.command == "prompt":
        guidance = select_guidance(arguments.seed, history["guidance_keys"])
        correction = None
        if arguments.feedback_url:
            correction = feedback_context(arguments.feedback_url)
            if arguments.feedback_file:
                correction["current_feedback"] = arguments.feedback_file.read_text(encoding="utf-8").strip()
        print(json.dumps({
            "guidance_key": guidance["key"],
            "prompt": author_prompt(
                guidance,
                history["specs"],
                rejected_specs=rejected_specs(),
                correction=correction,
            ),
        }))
        return

    spec = json.loads(arguments.spec.read_text(encoding="utf-8"))
    validate_spec(spec)
    score = novelty_score(spec, history["specs"])
    if arguments.command == "validate":
        print(json.dumps({"valid": True, "novelty": score}))
        return

    score = accept_spec(spec, arguments.guidance_key)
    print(json.dumps({"accepted": True, "novelty": score, "recent": len(load_history()["specs"])}))


if __name__ == "__main__":
    main()
