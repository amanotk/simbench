"""Adversarial tests for runner/results_helpers.py extraction boundaries."""

import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from contextlib import redirect_stdout

import sys
import os

# Ensure runner module is in path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.chdir(str(Path(__file__).resolve().parents[1]))

from runner import results_helpers as rh


class TestResultsHelpers_Adversarial(unittest.TestCase):
    """Attack vectors for results_helpers.py extraction increment (Phase 2.1)."""

    def test_format_kilotokens_handles_zero(self):
        """ADVERSARIAL: Zero token count boundary."""
        result = rh._format_kilotokens(0)
        self.assertEqual(result, "0.0k")

    def test_format_kilotokens_handles_large_values(self):
        """ADVERSARIAL: Large token counts that could overflow int32 boundaries."""
        result = rh._format_kilotokens(5000000000)
        self.assertEqual(result, "5000000.0k")

    def test_format_kilotokens_handles_float_precision(self):
        """ADVERSARIAL: Float precision edge cases."""
        result = rh._format_kilotokens(1501)
        self.assertEqual(result, "1.5k")

        result = rh._format_kilotokens(1500)
        self.assertEqual(result, "1.5k")

        result = rh._format_kilotokens(1499)
        self.assertEqual(result, "1.5k")

    def test_format_summary_metric_token_keys(self):
        """ADVERSARIAL: Various token-related key patterns."""
        test_cases = [
            ("input_tokens", 1000, "1.0k"),
            ("output_tokens", 500, "0.5k"),
            ("cache_read_input_tokens", 2000, "2.0k"),
            ("agent_input_tokens", 1500, "1.5k"),
            ("total_token_count", 3000, "3.0k"),
            (
                "non_token_value",
                1000,
                1000,
            ),  # BUGFIX: 'token' substring should NOT trigger format
            ("tokens", "not_a_number", "not_a_number"),
        ]
        for key, value, expected in test_cases:
            with self.subTest(key=key, value=value):
                result = rh._format_summary_metric(key, value)
                self.assertEqual(result, expected)

    def test_format_summary_metric_non_numeric_safe(self):
        """ADVERSARIAL: Non-numeric values don't crash."""
        result = rh._format_summary_metric("agent_input_tokens", "string_value")
        self.assertEqual(result, "string_value")

        result = rh._format_summary_metric("agent_input_tokens", None)
        self.assertIsNone(result)

        result = rh._format_summary_metric("agent_input_tokens", [1, 2, 3])
        self.assertEqual(result, [1, 2, 3])

    def test_print_result_summary_handles_empty_metrics(self):
        """ADVERSARIAL: Empty metrics dict should not print metrics section."""
        out = StringIO()
        with redirect_stdout(out):
            rh._print_result_summary(
                "s/t",
                Path("/tmp/run"),
                {
                    "status": "passed",
                    "score": 1.0,
                    "metrics": {},
                },
            )

        text = out.getvalue()
        self.assertIn("- status: passed", text)
        self.assertIn("- score: 1.0", text)
        # BUG: metrics section is omitted when empty (lines 54-58 check 'if metrics')
        self.assertNotIn("- metrics:", text)

    def test_print_result_summary_handles_missing_optional_fields(self):
        """ADVERSARIAL: Missing optional fields should not cause KeyError."""
        out = StringIO()
        with redirect_stdout(out):
            rh._print_result_summary(
                "s/t",
                Path("/tmp/run"),
                {
                    "status": "passed",
                    "score": 1.0,
                },
            )

        text = out.getvalue()
        self.assertIn("- status: passed", text)
        self.assertIn("- score: 1.0", text)

    def test_print_result_summary_handles_none_values_in_result(self):
        """ADVERSARIAL: None values in result dict should be handled gracefully."""
        out = StringIO()
        with redirect_stdout(out):
            rh._print_result_summary(
                "s/t",
                Path("/tmp/run"),
                {
                    "status": None,
                    "score": None,
                    "run_id": None,
                    "started_at": None,
                    "task": None,
                    "agent": None,
                    "model": None,
                    "agent_exit_code": None,
                    "eval_exit_code": None,
                    "metrics": None,
                },
            )

        text = out.getvalue()
        self.assertIn("- status:", text)
        self.assertIn("- score:", text)

    def test_print_result_summary_handles_empty_strings(self):
        """ADVERSARIAL: Empty strings in result should be filtered."""
        out = StringIO()
        with redirect_stdout(out):
            rh._print_result_summary(
                "s/t",
                Path("/tmp/run"),
                {
                    "status": "",
                    "score": 1.0,
                    "run_id": "",
                    "started_at": "",
                    "task": "",
                    "agent": "",
                    "model": "",
                },
            )

        text = out.getvalue()
        self.assertNotIn("- run_id:", text)
        self.assertNotIn("- started_at:", text)
        self.assertNotIn("- task:", text)
        self.assertNotIn("- agent:", text)
        self.assertNotIn("- model:", text)

    def test_print_result_summary_handles_agent_toml_missing_file(self):
        """ADVERSARIAL: Missing agent.toml file should not crash."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            out = StringIO()
            with redirect_stdout(out):
                rh._print_result_summary(
                    "s/t",
                    run_dir,
                    {
                        "status": "passed",
                        "score": 1.0,
                    },
                )

    def test_print_result_summary_handles_agent_toml_invalid_toml(self):
        """ADVERSARIAL: Invalid TOML file should be handled gracefully."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            agent_toml = run_dir / "agent.toml"
            agent_toml.write_text("invalid toml{{{")
            out = StringIO()
            with redirect_stdout(out):
                rh._print_result_summary(
                    "s/t",
                    run_dir,
                    {
                        "status": "passed",
                        "score": 1.0,
                    },
                )

    def test_print_result_summary_handles_agent_toml_non_dict(self):
        """ADVERSARIAL: agent.toml returning non-dict should be handled."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            agent_toml = run_dir / "agent.toml"
            agent_toml.write_text('[[array]]\nkey = "value"')
            out = StringIO()
            with redirect_stdout(out):
                rh._print_result_summary(
                    "s/t",
                    run_dir,
                    {
                        "status": "passed",
                        "score": 1.0,
                    },
                )

    def test_print_result_summary_handles_model_options_nested_structures(self):
        """ADVERSARIAL: Complex nested model_options should serialize correctly."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            agent_toml = run_dir / "agent.toml"
            agent_toml.write_text("""
version = 1
name = "test"
model = "test/model"

[model_options]
nested = { a = 1, b = [1, 2, 3] }
flag = true
value = 123.456
""")
            out = StringIO()
            with redirect_stdout(out):
                rh._print_result_summary(
                    "s/t",
                    run_dir,
                    {
                        "status": "passed",
                        "score": 1.0,
                    },
                )

            text = out.getvalue()
            self.assertIn('name: "test"', text)
            self.assertIn('model: "test/model"', text)

    def test_print_result_summary_unicode_and_special_chars(self):
        """ADVERSARIAL: Unicode and special characters in values."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            agent_toml = run_dir / "agent.toml"
            agent_toml.write_text("""
version = 1
name = "テストAgent"
model = "model/日本語"
""")
            out = StringIO()
            with redirect_stdout(out):
                rh._print_result_summary(
                    "s/t",
                    run_dir,
                    {
                        "status": "passed",
                        "score": 1.0,
                    },
                )

    def test_print_result_summary_metrics_ordering(self):
        """ADVERSARIAL: Metrics should be sorted by key."""
        out = StringIO()
        with redirect_stdout(out):
            rh._print_result_summary(
                "s/t",
                Path("/tmp/run"),
                {
                    "status": "passed",
                    "score": 1.0,
                    "metrics": {
                        "zebra": 1,
                        "alpha": 2,
                        "beta": 3,
                        "gamma": 4,
                    },
                },
            )

        text = out.getvalue()
        lines = text.splitlines()
        metrics_start = None
        for i, line in enumerate(lines):
            if line == "- metrics:":
                metrics_start = i
                break

        self.assertIsNotNone(metrics_start, "metrics section not found")
        metric_lines = lines[metrics_start + 1 : metrics_start + 5]
        self.assertTrue(any("alpha" in l for l in metric_lines))
        self.assertTrue(any("zebra" in l for l in metric_lines))

    def test_append_metric_creates_metrics_dict(self):
        """ADVERSARIAL: Metrics dict should be created if missing."""
        result = {"status": "passed"}
        rh._append_metric(result, "agent_input_tokens", 1000.0)

        self.assertIn("metrics", result)
        self.assertEqual(result["metrics"]["agent_input_tokens"], 1000.0)

    def test_append_metric_rounds_to_six_decimals(self):
        """ADVERSARIAL: Values should be rounded to 6 decimal places."""
        result = {}
        rh._append_metric(result, "test_value", 1.123456789)

        self.assertEqual(result["metrics"]["test_value"], 1.123457)

    def test_append_metric_ignores_none(self):
        """ADVERSARIAL: None values should be ignored."""
        result = {"metrics": {}}
        rh._append_metric(result, "test_value", None)

        self.assertEqual(result["metrics"], {})

    def test_set_metric_value_creates_metrics_dict(self):
        """ADVERSARIAL: Metrics dict should be created if missing."""
        result = {"status": "passed"}
        rh._set_metric_value(result, "test_value", "raw_value")

        self.assertIn("metrics", result)
        self.assertEqual(result["metrics"]["test_value"], "raw_value")

    def test_set_metric_value_overwrites_existing(self):
        """ADVERSARIAL: Existing metric values should be overwritten."""
        result = {"metrics": {"test_value": 100}}
        rh._set_metric_value(result, "test_value", 200)

        self.assertEqual(result["metrics"]["test_value"], 200)

    def test_json_line_objects_handles_mixed_content(self):
        """ADVERSARIAL: Mixed JSON and non-JSON lines."""
        text = """not a json line
{"type": "a", "value": 1}
another line
    {"type": "b", "value": 2}
{valid: json}
{"type": "c", "value": 3}
"""

        objs = rh._json_line_objects(text)

        self.assertEqual(len(objs), 3)
        self.assertEqual(objs[0]["type"], "a")
        self.assertEqual(objs[1]["type"], "b")
        self.assertEqual(objs[2]["type"], "c")

    def test_json_line_objects_handles_unicode_in_json(self):
        """ADVERSARIAL: Unicode in JSON values."""
        text = '{"name": "テスト", "emoji": "🎉"}\n'

        objs = rh._json_line_objects(text)

        self.assertEqual(len(objs), 1)
        self.assertEqual(objs[0]["name"], "テスト")
        self.assertEqual(objs[0]["emoji"], "🎉")

    def test_json_line_objects_handles_empty_input(self):
        """ADVERSARIAL: Empty string or whitespace."""
        self.assertEqual(rh._json_line_objects(""), [])
        self.assertEqual(rh._json_line_objects("   \n\n  "), [])
        self.assertEqual(rh._json_line_objects("{}"), [{}])

    def test_merge_metrics_overwrites_existing(self):
        """ADVERSARIAL: Metrics from merge should overwrite existing."""
        result = {"metrics": {"a": 1, "b": 2}}
        rh._merge_metrics(result, {"b": 99, "c": 3})

        self.assertEqual(result["metrics"]["a"], 1)
        self.assertEqual(result["metrics"]["b"], 99)
        self.assertEqual(result["metrics"]["c"], 3)

    def test_merge_metrics_empty_input(self):
        """ADVERSARIAL: Empty metrics merge should be safe."""
        result = {"status": "passed"}
        rh._merge_metrics(result, {})

        self.assertEqual(result, {"status": "passed"})

    def test_write_failure_result_basic(self):
        """ADVERSARIAL: Basic failure result structure."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            result = rh._write_failure_result(
                run_dir,
                error="test_error",
                message="test message",
                run_id="rid-123",
                started_at="2025-01-01T00:00:00Z",
                task_ref="s/t",
            )

            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["score"], 0.0)
            self.assertEqual(result["error"], "test_error")
            self.assertEqual(result["message"], "test message")

            result_path = run_dir / "result.json"
            self.assertTrue(result_path.exists())

            written = json.loads(result_path.read_text())
            self.assertEqual(written["status"], "failed")

    def test_write_failure_result_all_optional_fields(self):
        """ADVERSARIAL: All optional fields should be written when provided."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            metrics = {"agent_input_tokens": 1000}
            result = rh._write_failure_result(
                run_dir,
                error="test_error",
                message="test message",
                run_id="rid-123",
                started_at="2025-01-01T00:00:00Z",
                task_ref="s/t",
                agent_name="opencode",
                model="openai/gpt-5",
                agent_exit_code=7,
                eval_exit_code=3,
                metrics=metrics,
            )

            self.assertEqual(result["agent"], "opencode")
            self.assertEqual(result["model"], "openai/gpt-5")
            self.assertEqual(result["agent_exit_code"], 7)
            self.assertEqual(result["eval_exit_code"], 3)
            self.assertEqual(result["metrics"], metrics)

    def test_write_failure_result_no_optional_fields(self):
        """ADVERSARIAL: No optional fields should be omitted."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            result = rh._write_failure_result(
                run_dir,
                error="test_error",
                message="test message",
                run_id="rid-123",
                started_at="2025-01-01T00:00:00Z",
                task_ref="s/t",
                agent_name=None,
                model=None,
                agent_exit_code=None,
                eval_exit_code=None,
                metrics=None,
            )

            self.assertNotIn("agent", result)
            self.assertNotIn("model", result)
            self.assertNotIn("agent_exit_code", result)
            self.assertNotIn("eval_exit_code", result)
            self.assertNotIn("metrics", result)

    def test_run_started_at_returns_utc_iso8601(self):
        """ADVERSARIAL: Timestamp should be UTC ISO8601 format."""
        ts = rh._run_started_at()
        import re

        pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
        self.assertRegex(ts, pattern)

    def test_annotate_result_metadata_basic(self):
        """ADVERSARIAL: Basic metadata annotation."""
        result = {}
        rh._annotate_result_metadata(
            result,
            run_id="rid-123",
            started_at="2025-01-01T00:00:00Z",
            task_ref="s/t",
        )

        self.assertEqual(result["run_id"], "rid-123")
        self.assertEqual(result["started_at"], "2025-01-01T00:00:00Z")
        self.assertEqual(result["task"], "s/t")

    def test_annotate_result_metadata_all_fields(self):
        """ADVERSARIAL: All metadata fields should be added."""
        result = {}
        rh._annotate_result_metadata(
            result,
            run_id="rid-123",
            started_at="2025-01-01T00:00:00Z",
            task_ref="s/t",
            agent_name="opencode",
            model="openai/gpt-5",
            agent_exit_code=0,
            eval_exit_code=0,
        )

        self.assertEqual(result["agent"], "opencode")
        self.assertEqual(result["model"], "openai/gpt-5")
        self.assertEqual(result["agent_exit_code"], 0)
        self.assertEqual(result["eval_exit_code"], 0)

    def test_annotate_result_metadata_none_values_omitted(self):
        """ADVERSARIAL: None values should be omitted."""
        result = {}
        rh._annotate_result_metadata(
            result,
            run_id="rid-123",
            started_at="2025-01-01T00:00:00Z",
            task_ref="s/t",
            agent_name=None,
            model=None,
            agent_exit_code=None,
            eval_exit_code=None,
        )

        self.assertNotIn("agent", result)
        self.assertNotIn("model", result)
        self.assertNotIn("agent_exit_code", result)
        self.assertNotIn("eval_exit_code", result)


if __name__ == "__main__":
    unittest.main()
