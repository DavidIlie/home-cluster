#!/usr/bin/env python3
"""Generate one poster, upload it through the bounded broker, print its URL."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests

from author_prompt import accept_spec, load_history
from authoring import author_prompt, novelty_score, select_guidance, validate_spec
from feedback import record_delivery, record_feedback, rejected_specs


HERMES_HOME = Path(os.environ.get("HERMES_HOME", "/opt/data/profiles/friends-david"))
ROOT = HERMES_HOME / "workspace" / "meme-engine"
PYTHON = ROOT / ".venv" / "bin" / "python"
UPLOAD_URL = "http://hermes.default.svc.cluster.local:8080/seedyn/upload"
MODEL_URL = "http://cliproxy.default.svc.cluster.local:8317/v1/responses"
MODEL = os.environ.get("BOSTAN_AUTHOR_MODEL", "gpt-5.6-sol")
REASONING = os.environ.get("BOSTAN_AUTHOR_REASONING", "medium")
AUDIT_SCORES = (
    "title_fit",
    "instant_clarity",
    "standalone_rows",
    "comic_specificity",
    "source_grammar",
)
HERMES_REDACTED_MEDIA_PREFIXES = ("sk-", "sk_", "syt_", "SG.")


def profile_secret(name: str) -> str:
    env_file = HERMES_HOME / ".env"
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        key, separator, value = raw_line.partition("=")
        if separator and key.strip() == name:
            token = value.strip().strip("\"'")
            if token:
                return token
    raise RuntimeError(f"{name} is unavailable")


def run(*arguments: str, timeout: int) -> str:
    result = subprocess.run(
        [str(PYTHON), *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "unknown failure").strip()
        raise RuntimeError(f"{Path(arguments[0]).name} failed: {detail[-1200:]}")
    return result.stdout.strip()


def extract_output_text(payload: dict) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    chunks = []
    for output in payload.get("output") or []:
        if not isinstance(output, dict):
            continue
        for content in output.get("content") or []:
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str):
                chunks.append(text)
    return "\n".join(chunks).strip()


def parse_spec(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise ValueError("author model returned no JSON object")
        payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("author model returned a non-object")
    return payload


def audit_accepts(verdict: dict, expected_checks: int) -> bool:
    scores = verdict.get("scores")
    row_checks = verdict.get("row_checks")
    return bool(
        verdict.get("accept") is True
        and isinstance(scores, dict)
        and all(isinstance(scores.get(name), int) and scores[name] >= 4 for name in AUDIT_SCORES)
        and isinstance(row_checks, list)
        and len(row_checks) == expected_checks
        and all(
            isinstance(row, dict)
            and row.get("fits_title") is True
            and row.get("understandable") is True
            and row.get("funny") is True
            for row in row_checks
        )
    )


def request_spec(prompt: str, recent_specs: list[dict]) -> dict:
    failure = ""
    for _attempt in range(5):
        effective_prompt = prompt
        if failure:
            effective_prompt += f"\nThe prior candidate failed validation: {failure}. Return a corrected JSON object."
        response = requests.post(
            MODEL_URL,
            headers={"Authorization": f"Bearer {profile_secret('CLIPROXY_API_KEY')}"},
            json={
                "model": MODEL,
                "input": effective_prompt,
                "reasoning": {"effort": REASONING},
                "service_tier": "priority",
            },
            timeout=300,
        )
        response.raise_for_status()
        try:
            spec = parse_spec(extract_output_text(response.json()))
            validate_spec(spec)
            novelty_score(spec, recent_specs)
            review = requests.post(
                MODEL_URL,
                headers={"Authorization": f"Bearer {profile_secret('CLIPROXY_API_KEY')}"},
                json={
                    "model": MODEL,
                    "input": (
                        "Act as the final editor for this absurd poster. Return only one JSON object "
                        "with the same schema and layout. You may replace the premise completely when it is "
                        "strained, pseudo-profound, or based on an invented phrase. "
                        "Match the source format: a plain category headline and terse entries that each answer "
                        "that headline independently. Except for timeline, rows must not form a story, rely on "
                        "previous rows, or use pronouns whose referent lives in another row. "
                        "Every item must be grammatically natural, instantly understandable, and concretely tied "
                        "to the exact category named by the headline. Prefer blunt bad advice, literal mistakes, "
                        "socially wrong answers, or one oddly specific category error over a fantasy system. "
                        "For quote, keep one plain setup and one clean reversal. Reject poetic personification, "
                        "extended metaphors, and conclusions that need interpretation. "
                        "For item-based layouts, keep every lead and punch at or below 34 characters, including spaces. "
                        "Reject generic bureaucracy, management, permits, committees, fees, inspections, policy, "
                        "and briefings unless the headline's ordinary setting specifically requires them. "
                        "A row that could move under an unrelated headline without changing must be rewritten. "
                        "A row that is only defensible after an explanation must be rewritten. "
                        "The topic is visible copy: keep it to 2-5 plain words and at most 30 characters. "
                        "For comparison layouts, keep every side item at or below 28 characters. "
                        "Keep all visible strings short.\n"
                        f"Candidate: {json.dumps(spec, ensure_ascii=False)}"
                    ),
                    "reasoning": {"effort": REASONING},
                    "service_tier": "priority",
                },
                timeout=300,
            )
            review.raise_for_status()
            reviewed = parse_spec(extract_output_text(review.json()))
            validate_spec(reviewed)
            novelty_score(reviewed, recent_specs)
            audit = requests.post(
                MODEL_URL,
                headers={"Authorization": f"Bearer {profile_secret('CLIPROXY_API_KEY')}"},
                json={
                    "model": MODEL,
                    "input": (
                        "Audit this poster as a strict comedy editor. Return only JSON with keys "
                        "accept (boolean), reason (short string), scores (object), and row_checks (array). "
                        "Scores must include title_fit, instant_clarity, standalone_rows, comic_specificity, "
                        "and source_grammar, each an integer from 1 to 5. For every visible item, row_checks must "
                        "contain an object with fits_title, understandable, and funny booleans. Accept only if "
                        "every score is at least 4 and every boolean is true. Test each list row by reading the "
                        "headline followed by that row alone. Except for timeline, reject story chains, repeated "
                        "setup, cross-row pronouns, and five-step explanations of one pun. The saved-reference "
                        "grammar is a normal advice, category, ranking, comparison, or routine headline with "
                        "short independent entries. Absurdity may be rude, literal, impossible, or oddly specific, "
                        "but it must be immediately intelligible. Reject invented concepts, forced wordplay, "
                        "poetic conclusions, arbitrary noun combinations, and anything that becomes coherent "
                        "only after explanation. A technically traceable plot is not enough.\n"
                        f"Poster: {json.dumps(reviewed, ensure_ascii=False)}"
                    ),
                    "reasoning": {"effort": REASONING},
                    "service_tier": "priority",
                },
                timeout=300,
            )
            audit.raise_for_status()
            verdict = parse_spec(extract_output_text(audit.json()))
            expected_checks = (
                1
                if reviewed["shape"] == "quote"
                else 8
                if reviewed["shape"] == "comparison"
                else len(reviewed.get("items") or [])
            )
            if not audit_accepts(verdict, expected_checks):
                raise ValueError(f"semantic audit rejected candidate: {verdict.get('reason', 'low score')}")
            return reviewed
        except (ValueError, json.JSONDecodeError) as error:
            failure = str(error)
    raise RuntimeError(f"author model failed validation after five attempts: {failure}")


def survives_hermes_redaction(url: str) -> bool:
    """Reject public slugs that resemble credentials in Hermes stdout."""
    filename = Path(urlparse(url).path).name
    return not filename.startswith(HERMES_REDACTED_MEDIA_PREFIXES)


def upload(image: Path) -> str:
    for _attempt in range(5):
        with image.open("rb") as payload:
            response = requests.post(
                UPLOAD_URL,
                headers={"Authorization": f"Bearer {profile_secret('SEEDYN_BROKER_TOKEN')}"},
                files={"file": (image.name, payload, "image/png")},
                data={"kind": "image"},
                timeout=120,
                allow_redirects=False,
            )
        response.raise_for_status()
        url = str(response.json().get("url") or "").strip()
        if not url.startswith("https://"):
            raise RuntimeError("Seedyn returned no HTTPS media URL")
        verify = requests.get(url, timeout=60, allow_redirects=False)
        verify.raise_for_status()
        if not str(verify.headers.get("content-type") or "").startswith("image/"):
            raise RuntimeError("uploaded media URL did not return an image")
        if survives_hermes_redaction(url):
            return url
    raise RuntimeError("Seedyn returned only media URLs that Hermes would redact")


def correction_guidance(correction: dict) -> dict:
    previous = (correction.get("delivery") or {}).get("spec") or {}
    shape = str(previous.get("shape") or "daily_list")
    layout = str(previous.get("layout") or "right_cutout")
    return {
        "key": f"correction:{shape}:{layout}",
        "family": shape,
        "shape": shape,
        "top": str(previous.get("top") or "CORRECTED POSTER"),
        "title_key": str(previous.get("key") or "SAME PREMISE"),
        "world": f"the same exact situation as the previous {shape} poster",
        "tension": "fix the stated problem while preserving every uncriticized decision",
        "angle": "preserve the original joke angle unless the feedback explicitly rejects it",
        "layouts": [layout],
    }


def novelty_history(history: list[dict], correction: dict | None) -> list[dict]:
    if not correction:
        return history
    target = (correction.get("delivery") or {}).get("spec")
    return [item for item in history if item != target]


def correction_person(correction: dict | None) -> str | None:
    if not correction:
        return None
    person = ((correction.get("delivery") or {}).get("render") or {}).get("person")
    return str(person) if isinstance(person, str) and person.strip() else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--guidance-key")
    parser.add_argument("--person")
    parser.add_argument("--feedback-url")
    parser.add_argument("--feedback-file", type=Path)
    arguments = parser.parse_args()
    run("prepare_assets.py", timeout=3000)
    history = load_history()
    seed = datetime.now(ZoneInfo("Europe/Bucharest")).isoformat(timespec="minutes")
    correction = None
    feedback_text = ""
    if arguments.feedback_url:
        if not arguments.feedback_file:
            raise RuntimeError("--feedback-file is required with --feedback-url")
        feedback_text = arguments.feedback_file.read_text(encoding="utf-8").strip()
        from feedback import context as feedback_context

        correction = feedback_context(arguments.feedback_url)
        correction["current_feedback"] = feedback_text
    guidance = (
        correction_guidance(correction)
        if correction
        else select_guidance(seed, history["guidance_keys"])
    )
    guidance_key = arguments.guidance_key or guidance["key"]
    recent_specs = novelty_history(history["specs"], correction)
    rejected = rejected_specs()
    if arguments.spec:
        spec = json.loads(arguments.spec.read_text(encoding="utf-8"))
        validate_spec(spec)
        novelty_score(spec, recent_specs)
    else:
        prompt = author_prompt(
            guidance,
            recent_specs,
            rejected_specs=rejected,
            correction=correction,
        )
        spec = request_spec(prompt, recent_specs)
    spec_path = ROOT / ".runtime-spec.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    render_arguments = [
        "meme_engine.py",
        "--seed",
        seed.replace(":", "-"),
        "--spec",
        str(spec_path),
    ]
    selected_person = arguments.person or correction_person(correction)
    if selected_person:
        render_arguments.extend(["--person", selected_person])
    rendered = json.loads(run(*render_arguments, timeout=180))
    image = Path(rendered["png"])
    if not image.is_file() or image.stat().st_size == 0:
        raise RuntimeError("renderer did not produce a PNG")

    url = upload(image)
    replaced_spec = (correction.get("delivery") or {}).get("spec") if correction else None
    accept_spec(spec, guidance_key, exclude_spec=replaced_spec)
    if arguments.feedback_url:
        record_feedback(url=arguments.feedback_url, text=feedback_text, disposition="replace")
    record_delivery(
        url=url,
        spec=spec,
        render=rendered,
        guidance_key=guidance_key,
        replaces_url=arguments.feedback_url,
    )
    print(url)


if __name__ == "__main__":
    main()
