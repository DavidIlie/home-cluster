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
from zoneinfo import ZoneInfo

import requests

from author_prompt import accept_spec, load_history
from authoring import author_prompt, novelty_score, select_guidance, validate_spec
from feedback import record_delivery, record_feedback


HERMES_HOME = Path(os.environ.get("HERMES_HOME", "/opt/data/profiles/friends-david"))
ROOT = HERMES_HOME / "workspace" / "meme-engine"
PYTHON = ROOT / ".venv" / "bin" / "python"
UPLOAD_URL = "http://hermes.default.svc.cluster.local:8080/seedyn/upload"
MODEL_URL = "http://cliproxy.default.svc.cluster.local:8317/v1/responses"
MODEL = os.environ.get("BOSTAN_AUTHOR_MODEL", "gpt-5.6-sol")


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


def request_spec(prompt: str, recent_specs: list[dict]) -> dict:
    failure = ""
    for _attempt in range(3):
        effective_prompt = prompt
        if failure:
            effective_prompt += f"\nThe prior candidate failed validation: {failure}. Return a corrected JSON object."
        response = requests.post(
            MODEL_URL,
            headers={"Authorization": f"Bearer {profile_secret('CLIPROXY_API_KEY')}"},
            json={
                "model": MODEL,
                "input": effective_prompt,
                "reasoning": {"effort": "low"},
                "service_tier": "priority",
            },
            timeout=300,
        )
        response.raise_for_status()
        try:
            spec = parse_spec(extract_output_text(response.json()))
            validate_spec(spec)
            novelty_score(spec, recent_specs)
            return spec
        except (ValueError, json.JSONDecodeError) as error:
            failure = str(error)
    raise RuntimeError(f"author model failed validation after three attempts: {failure}")


def upload(image: Path) -> str:
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
    return url


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
    guidance = select_guidance(seed, history["guidance_keys"])
    guidance_key = arguments.guidance_key or guidance["key"]
    correction = None
    feedback_text = ""
    if arguments.feedback_url:
        if not arguments.feedback_file:
            raise RuntimeError("--feedback-file is required with --feedback-url")
        feedback_text = arguments.feedback_file.read_text(encoding="utf-8").strip()
        from feedback import context as feedback_context

        correction = feedback_context(arguments.feedback_url)
        correction["current_feedback"] = feedback_text
    if arguments.spec:
        spec = json.loads(arguments.spec.read_text(encoding="utf-8"))
        validate_spec(spec)
        novelty_score(spec, history["specs"])
    else:
        prompt = author_prompt(guidance, history["specs"], correction=correction)
        spec = request_spec(prompt, history["specs"])
    spec_path = ROOT / ".runtime-spec.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    render_arguments = [
        "meme_engine.py",
        "--seed",
        seed.replace(":", "-"),
        "--spec",
        str(spec_path),
    ]
    if arguments.person:
        render_arguments.extend(["--person", arguments.person])
    rendered = json.loads(run(*render_arguments, timeout=180))
    image = Path(rendered["png"])
    if not image.is_file() or image.stat().st_size == 0:
        raise RuntimeError("renderer did not produce a PNG")

    url = upload(image)
    accept_spec(spec, guidance_key)
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
