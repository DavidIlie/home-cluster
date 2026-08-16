from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path(__file__).with_name("prepare-runtime.py")
SPEC = importlib.util.spec_from_file_location("prepare_runtime", SCRIPT)
assert SPEC and SPEC.loader
prepare_runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prepare_runtime)


class PrepareRuntimeTests(unittest.TestCase):
    def test_managed_config_is_preserving_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(
                yaml.safe_dump(
                    {
                        "_config_version": 1,
                        "custom": {"keep": True},
                        "browser": {"backend": "browser-use"},
                        "memory": {"memory_enabled": True, "user_char_limit": 1375},
                    }
                ),
                encoding="utf-8",
            )

            self.assertTrue(
                prepare_runtime.configure_runtime_config(path, 24_000, 16_000)
            )
            configured = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(configured["custom"], {"keep": True})
            self.assertEqual(configured["browser"]["backend"], "off")
            self.assertEqual(configured["memory"]["memory_char_limit"], 24_000)
            self.assertEqual(configured["memory"]["user_char_limit"], 16_000)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertFalse(
                prepare_runtime.configure_runtime_config(path, 24_000, 16_000)
            )

    def test_runtime_config_rejects_unsafe_shapes_and_limits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text("browser: invalid\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "browser section"):
                prepare_runtime.configure_runtime_config(path, 24_000, 16_000)
            path.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "safe range"):
                prepare_runtime.configure_runtime_config(path, 1, 16_000)

    def test_targeted_replay_must_be_registered_unique_and_numeric(self) -> None:
        registry = ["111", "222", "333"]
        self.assertEqual(
            prepare_runtime._selected_thread_ids(registry, []), registry
        )
        self.assertEqual(
            prepare_runtime._selected_thread_ids(registry, ["333", "111"]),
            ["333", "111"],
        )
        for invalid in (["999"], ["111", "111"], ["not-a-thread"]):
            with self.assertRaises(RuntimeError):
                prepare_runtime._selected_thread_ids(registry, invalid)

    def test_atomic_marker_is_regular_private_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "marker.json"
            value = {"migration": "test", "thread_ids": ["111"]}
            prepare_runtime._atomic_json(path, value)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), value)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            path.unlink()
            path.symlink_to(Path(directory) / "outside")
            with self.assertRaisesRegex(RuntimeError, "non-regular"):
                prepare_runtime._atomic_json(path, value)

    def test_skip_replay_ignores_an_existing_replay_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            (home / "config.yaml").write_text("_config_version: 1\n", encoding="utf-8")
            marker = home / "migrations" / f"{prepare_runtime.MIGRATION_ID}.json"
            marker.parent.mkdir()
            marker.write_text('{"migration":"old","thread_ids":["111"]}\n', encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--home",
                    str(home),
                    "--user-id",
                    "243009043260637184",
                    "--timezone",
                    "Europe/Madrid",
                    "--memory-char-limit",
                    "24000",
                    "--user-char-limit",
                    "16000",
                    "--skip-replay",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("Operator replay explicitly disabled", completed.stdout)
            self.assertEqual(
                json.loads(marker.read_text(encoding="utf-8"))["migration"], "old"
            )


if __name__ == "__main__":
    unittest.main()
