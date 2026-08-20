import importlib.util
import pathlib
import unittest

PATH = pathlib.Path(__file__).with_name("claude_quota_exporter.py")
SPEC = importlib.util.spec_from_file_location("exporter", PATH)
exporter = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(exporter)


class ClaudeQuotaTest(unittest.TestCase):
    def test_parses_bounded_usage_and_reset(self):
        samples = exporter.parse_usage({"five_hour": {"utilization": 23.5, "resets_at": "2026-08-20T12:00:00Z"}, "seven_day": {"utilization": 150}})
        self.assertIn(("used_percent", "five_hour", 23.5), samples)
        self.assertIn(("remaining_percent", "five_hour", 76.5), samples)
        self.assertIn(("used_percent", "seven_day", 100.0), samples)
        self.assertTrue(any(metric == "reset_timestamp_seconds" for metric, _, _ in samples))

    def test_missing_and_invalid_fields_are_absent(self):
        self.assertEqual(exporter.parse_usage({"five_hour": {"resets_at": "bad"}, "seven_day": None}), [])

    def test_prometheus_output(self):
        text = exporter.prometheus([("used_percent", "a@example.com", "five_hour", 12.0)])
        self.assertIn('# TYPE cliproxy_claude_quota_used_percent gauge', text)
        self.assertIn('cliproxy_claude_quota_used_percent{account="a@example.com",window="five_hour"} 12', text)


if __name__ == "__main__": unittest.main()
