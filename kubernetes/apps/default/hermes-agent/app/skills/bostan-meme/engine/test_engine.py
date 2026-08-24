#!/usr/bin/env python3
"""Focused tests for authored poster selection, geometry, and diversity."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

from PIL import Image

import meme_engine
from authoring import author_prompt, novelty_score, select_guidance, validate_spec
import feedback
import author_prompt as author_history
from cron_hourly import correction_guidance, correction_person, novelty_history
from corpus import POSTERS
from premises import ANGLES, FAMILIES, guided_capacity, title_count


ROOT = Path(__file__).resolve().parent
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
PYTHON = VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable)
CANVAS = (0, 0, 1080, 1350)


def overlap_area(left: tuple[int, int, int, int], right: tuple[int, int, int, int]) -> int:
    width = max(0, min(left[2], right[2]) - max(left[0], right[0]))
    height = max(0, min(left[3], right[3]) - max(left[1], right[1]))
    return width * height


@contextmanager
def record_text_boxes():
    placements: list[tuple[str, tuple[int, int, int, int]]] = []
    original_put = meme_engine.put

    def recording_put(draw, position, value, text_font, color=meme_engine.WHITE, stroke=0):
        placements.append((value, draw.textbbox(position, value, font=text_font, stroke_width=stroke)))
        return original_put(draw, position, value, text_font, color, stroke)

    meme_engine.put = recording_put
    try:
        yield placements
    finally:
        meme_engine.put = original_put


def assert_clean_geometry(placements: list[tuple[str, tuple[int, int, int, int]]]) -> None:
    for value, box in placements:
        assert box[0] >= CANVAS[0], (value, box)
        assert box[1] >= CANVAS[1], (value, box)
        assert box[2] <= CANVAS[2], (value, box)
        assert box[3] <= CANVAS[3], (value, box)
    for index, (left_value, left_box) in enumerate(placements):
        for right_value, right_box in placements[index + 1 :]:
            assert overlap_area(left_box, right_box) == 0, (
                left_value,
                left_box,
                right_value,
                right_box,
            )


def test_catalog() -> None:
    assert title_count() == 100
    assert guided_capacity() == 10_000
    assert len({str(item["id"]) for item in POSTERS}) == len(POSTERS)
    assert len({str(item["topic"]) for item in POSTERS}) == len(POSTERS)
    assert {str(item["layout"]) for item in POSTERS} == set(meme_engine.LAYOUTS)
    assert any("(CINCO)" in str(item["top"]) for item in POSTERS)
    for item in POSTERS:
        assert str(item["top"]).strip()
        assert str(item["key"]).strip()
        assert str(item["shape"]).strip()
        assert str(item["layout"]) in meme_engine.LAYOUTS


def test_runtime_authoring(target: Path) -> None:
    guidance = select_guidance("runtime-authoring-test")
    family = FAMILIES[guidance["family"]]
    title_index = family["titles"].index((guidance["top"], guidance["title_key"]))
    assert guidance["world"] == family["worlds"][title_index]
    assert guidance["angle"] in ANGLES
    prompt = author_prompt(guidance, [])
    assert "Author six complete candidate" in prompt
    assert "not permission for unrelated items" in prompt
    assert "could be moved under an unrelated title" in prompt
    assert "comparison item must be at most 28 characters" in prompt
    assert "10,000" not in prompt
    spec = {
        "id": "fire-drill-shareholder",
        "topic": "fire drill power struggle",
        "shape": "dialogue",
        "layout": "hostile_dialogue",
        "top": "THINGS TO WHISPER",
        "key": "DURING THE FIRE DRILL",
        "items": [
            ["ASK", "WHO OWNS THE ALARM"],
            ["CONFIRM", "THE STAIRS ARE BILLABLE"],
            ["MENTION", "SMOKE REPORTS TO FINANCE"],
            ["REQUEST", "A WINDOW WITH VOTING RIGHTS"],
            ["LEAVE WITH", "THE ASSEMBLY POINT"],
        ],
    }
    validate_spec(spec)
    assert novelty_score(spec, []) == 1.0
    try:
        novelty_score(spec, [spec])
    except ValueError as error:
        assert "too similar" in str(error)
    else:
        raise AssertionError("duplicate runtime spec was accepted")
    output = target / "runtime-spec.png"
    result = meme_engine.render(
        "runtime-spec",
        output,
        spec=spec,
        person_name=meme_engine.valid_people()[0].name,
        update_state=False,
    )
    assert result["poster"] == spec["id"]
    assert output.stat().st_size > 35_000
    correction = {
        "delivery": {"spec": spec, "render": {"person": "friend-studio.png"}},
        "feedback": [],
        "current_feedback": "Make the portrait larger and stop the headline overlap.",
    }
    correction_prompt = author_prompt(guidance, [spec], correction=correction)
    assert "Previous exact spec" in correction_prompt
    assert "portrait larger" in correction_prompt
    correction_shape = correction_guidance(correction)
    assert correction_shape["shape"] == spec["shape"]
    assert correction_shape["layouts"] == [spec["layout"]]
    assert correction_shape["top"] == spec["top"]
    assert novelty_history([spec, POSTERS[0]], correction) == [POSTERS[0]]
    assert novelty_history([spec], None) == [spec]
    assert correction_person(correction) == "friend-studio.png"
    assert correction_person(None) is None
    invalid_topic = dict(spec)
    invalid_topic["topic"] = "raising money to buy a municipal afternoon"
    try:
        validate_spec(invalid_topic)
    except ValueError as error:
        assert "topic must be" in str(error)
    else:
        raise AssertionError("oversized visible topic was accepted")
    bureaucratic = dict(spec)
    bureaucratic["top"] = "THE CAR PARK"
    bureaucratic["key"] = "APPOINTED YOU"
    bureaucratic["items"] = [
        ["BARRIER", "OPENS FOR INSPECTION"],
        ["TICKET", "READS ACTING MANAGER"],
        ["BAY 12", "AWAITS APPROVAL"],
        ["TROLLEY", "REPORTS FOR BRIEFING"],
        ["EXIT", "REQUESTS A POLICY"],
    ]
    try:
        validate_spec(bureaucratic)
    except ValueError as error:
        assert "generic bureaucracy" in str(error)
    else:
        raise AssertionError("bureaucracy pasted onto an unrelated setting was accepted")


def test_delivery_feedback_ledger(target: Path) -> None:
    original_deliveries = feedback.DELIVERIES
    original_feedback = feedback.FEEDBACK
    original_lock = feedback.LOCK
    try:
        feedback.DELIVERIES = target / "deliveries.jsonl"
        feedback.FEEDBACK = target / "feedback.jsonl"
        feedback.LOCK = target / ".ledger.lock"
        spec = json.loads(json.dumps(POSTERS[0]))
        feedback.record_delivery(
            url="https://i.gurt.ing/example.png",
            spec=spec,
            render={"png": "/tmp/example.png"},
            guidance_key="dialogue:0:0:0",
        )
        feedback.record_feedback(
            url="https://i.gurt.ing/example.png",
            text="The portrait is too small.",
            disposition="critique",
        )
        recovered = feedback.context("https://i.gurt.ing/example.png")
        assert recovered["delivery"]["spec"] == json.loads(json.dumps(spec))
        assert recovered["feedback"][0]["text"] == "The portrait is too small."
    finally:
        feedback.DELIVERIES = original_deliveries
        feedback.FEEDBACK = original_feedback
        feedback.LOCK = original_lock


def test_correction_history(target: Path) -> None:
    original_history = author_history.HISTORY
    try:
        author_history.HISTORY = target / "author-history.json"
        spec = json.loads(json.dumps(POSTERS[0]))
        author_history.accept_spec(spec, "initial")
        author_history.accept_spec(spec, "correction", exclude_spec=spec)
        assert len(author_history.load_history()["specs"]) == 2
    finally:
        author_history.HISTORY = original_history


def test_blueprints(target: Path) -> int:
    people = [path.name for path in meme_engine.valid_people()]
    representatives = [people[0], people[len(people) // 2], people[-1]]
    rendered = 0
    for poster_index, blueprint in enumerate(POSTERS):
        for person_name in representatives:
            output = target / f"poster-{poster_index}-{person_name}"
            with record_text_boxes() as placements:
                metadata = meme_engine.render(
                    f"catalog-{poster_index}-{person_name}",
                    output,
                    poster_index=poster_index,
                    person_name=person_name,
                    update_state=False,
                )
            assert_clean_geometry(placements)
            with Image.open(output) as image:
                assert image.size == (1080, 1350)
                assert image.mode == "RGB"
            assert metadata["layout"] == blueprint["layout"]
            assert metadata["poster"] == blueprint["id"]
            if metadata["layout"] == "left_editorial":
                assert all(value != "FIELD DIRECTOR" for value, _box in placements)
            assert output.stat().st_size > 35_000
            rendered += 1
    return rendered


def main() -> None:
    test_catalog()
    outputs = []
    with tempfile.TemporaryDirectory(prefix="bostan-engine-") as directory:
        target = Path(directory)
        for index in range(len(POSTERS)):
            output = target / f"rotation-{index}.png"
            result = subprocess.run(
                [str(PYTHON), "meme_engine.py", "--seed", f"rotation-{index}", "--output", str(output)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=120,
                check=True,
            )
            metadata = json.loads(result.stdout)
            with Image.open(output) as image:
                assert image.size == (1080, 1350)
                assert image.mode == "RGB"
            assert output.stat().st_size > 35_000
            outputs.append(metadata)
    assert len({item["poster"] for item in outputs}) == len(POSTERS)
    assert len({item["topic"] for item in outputs}) == len(POSTERS)
    assert len({item["layout"] for item in outputs}) >= 8
    with tempfile.TemporaryDirectory(prefix="bostan-blueprints-") as directory:
        target = Path(directory)
        blueprint_count = test_blueprints(target)
        test_runtime_authoring(target)
        test_delivery_feedback_ledger(target)
        test_correction_history(target)
    print(
        json.dumps(
            {
                "rotation_rendered": len(outputs),
                "blueprint_rendered": blueprint_count,
                "titles": title_count(),
                "guided_capacity": guided_capacity(),
                "layouts": sorted({item["layout"] for item in outputs}),
            }
        )
    )


if __name__ == "__main__":
    main()
