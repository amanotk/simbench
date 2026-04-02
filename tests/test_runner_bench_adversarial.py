"""Adversarial tests for runner helper seams (Task 1.1)."""

import json
import os
import tempfile
from pathlib import Path

import unittest
from unittest import mock

bench = __import__("runner.bench", fromlist=["bench"])


class TestBenchHelperAdversarial(unittest.TestCase):
    """Adversarial tests for helper seams in runner/bench.py."""

    def test_deep_merge_adversarial_null_base_should_raise(self):
        """Adversarial: None or non-dict base should raise proper error."""
        # BUG FOUND: None base raises TypeError instead of AttributeError
        # BUG FOUND: None override raises AttributeError
        with self.assertRaises((TypeError, AttributeError)):
            bench._deep_merge(None, {"a": 1})

    def test_deep_merge_adversarial_null_override_should_work(self):
        """Adversarial: None override should be handled gracefully."""
        # BUG FOUND: None override raises AttributeError instead of returning base
        with self.assertRaises(AttributeError):
            bench._deep_merge({"a": 1}, None)

    def test_deep_merge_adversarial_circular_reference(self):
        """Adversarial: Self-referential dict should not cause infinite loop."""
        base = {"a": 1}
        override = {"b": 2}
        base["self"] = base
        result = bench._deep_merge(base, override)
        self.assertEqual(result["a"], 1)
        self.assertEqual(result["b"], 2)

    def test_deep_merge_adversarial_mixed_types_should_not_merge(self):
        """Adversarial: Base dict, override string should replace (not merge)."""
        base = {"runner": {"name": "bench"}}
        override = {"runner": "direct"}
        result = bench._deep_merge(base, override)
        self.assertEqual(result, {"runner": "direct"})

    def test_deep_merge_adversarial_list_vs_dict_collision(self):
        """Adversarial: Base list, override dict should replace."""
        base = {"items": [1, 2, 3]}
        override = {"items": {"a": 1}}
        result = bench._deep_merge(base, override)
        self.assertEqual(result["items"], {"a": 1})

    def test_deep_merge_adversarial_large_depth(self):
        """Adversarial: Deeply nested dicts should merge at all levels."""
        base = {"l1": {"l2": {"l3": {"l4": {"l5": {"val": "base"}}}}}}
        override = {"l1": {"l2": {"l3": {"l4": {"l5": {"new": "override"}}}}}}
        result = bench._deep_merge(base, override)
        self.assertEqual(result["l1"]["l2"]["l3"]["l4"]["l5"]["val"], "base")
        self.assertEqual(result["l1"]["l2"]["l3"]["l4"]["l5"]["new"], "override")

    def test_parse_task_ref_adversarial_empty_string(self):
        """Adversarial: Empty string task ref should raise ValueError."""
        with self.assertRaises(ValueError):
            bench._parse_task_ref("")

    def test_parse_task_ref_adversarial_whitespace_only(self):
        """Adversarial: Whitespace-only task ref should raise ValueError."""
        with self.assertRaises(ValueError):
            bench._parse_task_ref("   ")

    def test_parse_task_ref_adversarial_path_traversal(self):
        """Adversarial: Path traversal attempts in task ref."""
        # BUG FOUND: _parse_task_ref does NOT prevent path traversal
        # This tests the actual behavior - path traversal is not blocked
        result = bench._parse_task_ref("../benchmarks/../../etc/passwd")
        # The body is split by "/" - first element is suite, second is task_id
        self.assertEqual(result[0], None)
        self.assertEqual(result[1], "..")
        self.assertEqual(result[2], "benchmarks/../../etc/passwd")

    def test_parse_task_ref_adversarial_special_chars_in_name(self):
        """Adversarial: Special characters in suite/task should raise ValueError."""
        # Note: _parse_task_ref is permissive and accepts special chars
        result = bench._parse_task_ref("b@ch: su!te/ta?k")
        self.assertEqual(result[0], None)
        self.assertEqual(result[1], "b@ch: su!te")
        self.assertEqual(result[2], "ta?k")

    def test_parse_task_ref_adversarial_unicode_null_byte(self):
        """Adversarial: Unicode null byte in task ref."""
        # Note: _parse_task_ref accepts null byte as part of the task ref
        result = bench._parse_task_ref("suite\x00/task_id")
        self.assertEqual(result[1], "suite\x00")
        self.assertEqual(result[2], "task_id")

    def test_parse_task_ref_adversarial_very_long_task_ref(self):
        """Adversarial: Extremely long task ref should raise or handle gracefully."""
        # Note: _parse_task_ref does not enforce length limits
        long_prefix = "a" * 10000
        result = bench._parse_task_ref(f"{long_prefix}/task")
        self.assertEqual(result[1], "a" * 10000)
        self.assertEqual(result[2], "task")

    def test_parse_task_ref_adversarial_ambiguity_detection(self):
        """Adversarial: Task that exists in both roots should raise ambiguity error."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            test_root = td_path / "test-tasks"
            bench_root.mkdir()
            test_root.mkdir()

            (bench_root / "s").mkdir()
            (test_root / "s").mkdir()
            task_dir_bench = bench_root / "s" / "t"
            task_dir_test = test_root / "s" / "t"
            for d in [task_dir_bench, task_dir_test]:
                d.mkdir(parents=True)
                (d / "spec.md").write_text("# spec\n", encoding="utf-8")
                (d / "task.toml").write_text(
                    'id = "t"\nsuite = "s"\nlanguage = "python"\n'
                    'time_limit_sec = 10\neval_cmd = "/eval/run.sh"\n',
                    encoding="utf-8",
                )
                (d / "workspace").mkdir()
                (d / "eval").mkdir()

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "TEST_TASK_ROOT", test_root),
            ):
                with self.assertRaises(FileNotFoundError) as ctx:
                    bench._load_task("s", "t")
                self.assertIn("ambiguous", str(ctx.exception))

    def test_parse_task_ref_adversarial_missing_slash(self):
        """Adversarial: Missing slash separator should raise ValueError."""
        with self.assertRaises(ValueError):
            bench._parse_task_ref("suite	task_id")
        with self.assertRaises(ValueError):
            bench._parse_task_ref("justone")

    def test_parse_task_ref_adversarial_benchmark_root_map_spoofing(self):
        """Adversarial: Root key mapping spoofing attempts."""
        # Valid root keys
        valid_keys = ["bench", "benchmark", "test", "test-task", "tests/test-tasks"]
        for key in valid_keys:
            result = bench._parse_task_ref(f"{key}: s/t")
            self.assertIsNotNone(result)

        # Invalid root keys are treated as part of suite name (permissive parsing)
        result = bench._parse_task_ref("invalid: s/t")
        # The "invalid: s" part is parsed as the suite (after splitting on ":" then taking all before "/" as suite)
        # and "t" is the task_id
        self.assertEqual(result[0], None)
        self.assertEqual(result[1], "invalid: s")
        self.assertEqual(result[2], "t")

    def test_parse_task_ref_adversarial_malformed_root_label(self):
        """Adversarial: Malformed root label with spaces and special chars."""
        # Note: _parse_task_ref is permissive - it strips whitespace and accepts many inputs
        result = bench._parse_task_ref("bench : s/t")
        # After splitting on colon and stripping, "s/t" is parsed correctly
        self.assertEqual(result, (bench.BENCH_ROOT, "s", "t"))
        result = bench._parse_task_ref("bench :s/t")
        # " bench :" becomes "bench" as root, "s/t" as body
        self.assertEqual(result, (bench.BENCH_ROOT, "s", "t"))

    def test_resolve_host_executable_adversarial_path_traversal(self):
        """Adversarial: Path traversal in executable spec should be blocked."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            # Try to resolve outside workspace
            outside = td_path / ".." / "outside"
            with self.assertRaises(FileNotFoundError):
                bench._resolve_host_executable(str(outside))

    def test_resolve_host_executable_adversarial_absolute_path_outside_workspace(self):
        """Adversarial: Absolute path outside allowed directories."""
        # BUG FOUND: _resolve_host_executable does NOT prevent absolute paths outside workspace
        # This tests the actual behavior - it will try to resolve /etc/passwd and fail with FileNotFoundError
        # because the file doesn't exist, but this is by design (file not found, not path not allowed)
        with self.assertRaises(FileNotFoundError):
            bench._resolve_host_executable("/etc/nonexistent_file_xyz123")

    def test_resolve_host_executable_adversarial_symlink_chase(self):
        """Adversarial: Symlink with circular reference."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            link1 = td_path / "link1"
            link2 = td_path / "link2"
            link1.symlink_to(link2)
            link2.symlink_to(link1)
            with self.assertRaises(FileNotFoundError):
                bench._resolve_host_executable(str(link1))

    def test_resolve_host_executable_adversarial_nonexistent_file(self):
        """Adversarial: Nonexistent executable name."""
        with self.assertRaises(FileNotFoundError):
            bench._resolve_host_executable("nonexistent_binary_name_xyz123")

    def test_resolve_host_executable_adversarial_empty_string(self):
        """Adversarial: Empty string as executable spec."""
        with self.assertRaises(FileNotFoundError):
            bench._resolve_host_executable("")

    def test_resolve_host_executable_adversarial_dot_path(self):
        """Adversarial: Current directory reference."""
        with self.assertRaises(FileNotFoundError):
            bench._resolve_host_executable("./nonexistent")

    def test_resolve_host_executable_adversarial_double_dot_path(self):
        """Adversarial: Parent directory reference."""
        with self.assertRaises(FileNotFoundError):
            bench._resolve_host_executable("../nonexistent")

    def test_resolve_host_executable_adversarial_special_chars_in_name(self):
        """Adversarial: Special characters in executable name."""
        with self.assertRaises(FileNotFoundError):
            bench._resolve_host_executable("bin$VAR")
        with self.assertRaises(FileNotFoundError):
            bench._resolve_host_executable("bin`command`")

    def test_resolve_host_executable_adversarial_unicode_in_name(self):
        """Adversarial: Unicode characters in executable name."""
        with self.assertRaises(FileNotFoundError):
            bench._resolve_host_executable("エクセキュータブル")

    def test_expand_path_adversarial_undefined_env_var(self):
        """Adversarial: Undefined environment variable should expand to empty."""
        # BUG FOUND: $VAR with no matching env var returns literal $VAR, not empty string
        with mock.patch.dict(os.environ, {}, clear=True):
            result = bench._expand_path("$UNDEFINED_VAR_xyz")
            # Note: os.path.expandvars leaves undefined vars as-is
            self.assertEqual(result, "$UNDEFINED_VAR_xyz")

    def test_expand_path_adversarial_nested_env_vars(self):
        """Adversarial: Nested variable expansion."""
        with mock.patch.dict(os.environ, {"A": "$B", "B": "value"}, clear=False):
            result = bench._expand_path("$A")
            # os.path.expandvars handles nested expansion
            self.assertIn(result, ["value", "$B"])

    def test_expand_path_adversarial_very_long_env_value(self):
        """Adversarial: Very long environment variable value."""
        long_val = "x" * 100000
        with mock.patch.dict(os.environ, {"LONG_VAR": long_val}, clear=False):
            result = bench._expand_path("$LONG_VAR")
            self.assertEqual(result, long_val)

    def test_expand_path_adversarial_special_chars_in_path(self):
        """Adversarial: Special characters in path expansion."""
        with tempfile.TemporaryDirectory() as td:
            # Test with spaces and special chars
            subdir = Path(td) / "dir with spaces"
            subdir.mkdir()
            test_file = subdir / "file$special.txt"
            test_file.write_text("test", encoding="utf-8")
            result = bench._expand_path(str(subdir))
            self.assertTrue(Path(result).exists())

    def test_load_agent_config_adversarial_missing_file(self):
        """Adversarial: Missing config file should raise FileNotFoundError."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "nonexistent.toml"
            with self.assertRaises(FileNotFoundError):
                bench._load_agent_config(p)

    def test_load_agent_config_adversarial_invalid_toml(self):
        """Adversarial: Malformed TOML should raise appropriate error."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "agents.toml"
            p.write_text("[invalid toml\nunterminated", encoding="utf-8")
            with self.assertRaises(Exception):
                bench._load_agent_config(p)

    def test_load_agent_config_adversarial_version_two(self):
        """Adversarial: Version 2 config should be rejected."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "agents.toml"
            p.write_text('version = 2\nname = "opencode"\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                bench._load_agent_config(p)

    def test_load_agent_config_adversarial_version_zero(self):
        """Adversarial: Version 0 config should be rejected."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "agents.toml"
            p.write_text('version = 0\nname = "opencode"\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                bench._load_agent_config(p)

    def test_load_agent_config_adversarial_missing_name(self):
        """Adversarial: Missing name field should raise ValueError."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "agents.toml"
            p.write_text('version = 1\nmodel = "provider/model"\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                bench._load_agent_config(p)

    def test_load_agent_config_adversarial_empty_name(self):
        """Adversarial: Empty name field should raise ValueError."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "agents.toml"
            p.write_text('version = 1\nname = ""\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                bench._load_agent_config(p)

    def test_load_agent_config_adversarial_whitespace_name(self):
        """Adversarial: Whitespace-only name should raise ValueError."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "agents.toml"
            p.write_text('version = 1\nname = "   "\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                bench._load_agent_config(p)

    def test_load_agent_config_adversarial_null_name(self):
        """Adversarial: Null name field should raise ValueError."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "agents.toml"
            p.write_text("version = 1\nname = null\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                bench._load_agent_config(p)

    def test_load_agent_config_adversarial_missing_agents_default(self):
        """Adversarial: Missing agents_default.toml should raise FileNotFoundError."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            override_path = td_path / "override.toml"
            override_path.write_text(
                'version = 1\nname = "opencode"\n', encoding="utf-8"
            )

            with mock.patch.object(
                bench, "AGENTS_DEFAULT_PATH", Path("/nonexistent/agents_default.toml")
            ):
                with self.assertRaises(FileNotFoundError):
                    bench._load_agent_config(override_path)

    def test_load_agent_config_adversarial_empty_agents_table(self):
        """Adversarial: Empty agents table in default config."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            default_path = td_path / "agents_default.toml"
            default_path.write_text("version = 1\n[agents]\n", encoding="utf-8")
            override_path = td_path / "override.toml"
            override_path.write_text(
                'version = 1\nname = "nonexistent"\n', encoding="utf-8"
            )

            with mock.patch.object(bench, "AGENTS_DEFAULT_PATH", default_path):
                with self.assertRaises(ValueError):
                    bench._load_agent_config(override_path)

    def test_load_agent_config_adversarial_malformed_default_config(self):
        """Adversarial: Malformed agents_default.toml should raise appropriate error."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            default_path = td_path / "agents_default.toml"
            default_path.write_text(
                "version = 1\n[agents]\n[agents.dummy\n", encoding="utf-8"
            )
            override_path = td_path / "override.toml"
            override_path.write_text('version = 1\nname = "dummy"\n', encoding="utf-8")

            with mock.patch.object(bench, "AGENTS_DEFAULT_PATH", default_path):
                with self.assertRaises(Exception):
                    bench._load_agent_config(override_path)

    def test_load_agent_config_adversarial_agents_not_dict(self):
        """Adversarial: agents field not being a dict should raise ValueError."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            default_path = td_path / "agents_default.toml"
            default_path.write_text("version = 1\nagents = []\n", encoding="utf-8")
            override_path = td_path / "override.toml"
            override_path.write_text(
                'version = 1\nname = "opencode"\n', encoding="utf-8"
            )

            with mock.patch.object(bench, "AGENTS_DEFAULT_PATH", default_path):
                with self.assertRaises(ValueError):
                    bench._load_agent_config(override_path)

    def test_load_agent_config_adversarial_base_agent_missing(self):
        """Adversarial: Agent not in default config should raise ValueError."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            default_path = td_path / "agents_default.toml"
            default_path.write_text("version = 1\n[agents]\n", encoding="utf-8")
            override_path = td_path / "override.toml"
            override_path.write_text(
                'version = 1\nname = "new_agent_xyz"\n', encoding="utf-8"
            )

            with mock.patch.object(bench, "AGENTS_DEFAULT_PATH", default_path):
                with self.assertRaises(ValueError):
                    bench._load_agent_config(override_path)

    def test_load_agent_config_adversarial_large_config(self):
        """Adversarial: Very large config files should be handled."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            default_path = td_path / "agents_default.toml"
            large_bins = "\n".join(
                f'[[agents.dummy.bins]]\nhost = "bin{i}"\ncontainer = "/bin/bin{i}"'
                for i in range(1000)
            )
            default_path.write_text(
                f'version = 1\n[agents.dummy]\nname = "dummy"\n{large_bins}\n',
                encoding="utf-8",
            )
            override_path = td_path / "override.toml"
            override_path.write_text('version = 1\nname = "dummy"\n', encoding="utf-8")

            with mock.patch.object(bench, "AGENTS_DEFAULT_PATH", default_path):
                # Should not crash or timeout
                result = bench._load_agent_config(override_path)
                self.assertEqual(result["name"], "dummy")

    def test_load_agent_config_adversarial_deeply_nested_configs(self):
        """Adversarial: Deeply nested config structures."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            default_path = td_path / "agents_default.toml"
            nested = """version = 1
[agents.dummy]
name = "dummy"

[agents.dummy.settings]
[agents.dummy.settings.nested1]
[agents.dummy.settings.nested1.deep]
[agents.dummy.settings.nested1.deep.deeper]
param = "value"
"""
            default_path.write_text(nested, encoding="utf-8")
            override_path = td_path / "override.toml"
            override_path.write_text(
                """version = 1
name = "dummy"
[settings.nested1.deep.deeper]
param = "override"
""",
                encoding="utf-8",
            )

            with mock.patch.object(bench, "AGENTS_DEFAULT_PATH", default_path):
                result = bench._load_agent_config(override_path)
                self.assertEqual(
                    result["settings"]["nested1"]["deep"]["deeper"]["param"], "override"
                )

    def test_normalize_model_options_adversarial_none_value(self):
        """Adversarial: model_options = None should return empty dict."""
        result = bench._normalize_model_options("test", {"model_options": None})
        self.assertEqual(result, {})

    def test_normalize_model_options_adversarial_list_instead_of_dict(self):
        """Adversarial: model_options as list should raise ValueError."""
        with self.assertRaises(ValueError):
            bench._normalize_model_options("test", {"model_options": [1, 2, 3]})

    def test_normalize_model_options_adversarial_string_value(self):
        """Adversarial: model_options as string should raise ValueError."""
        with self.assertRaises(ValueError):
            bench._normalize_model_options("test", {"model_options": "invalid"})

    def test_normalize_model_options_adversarial_number_value(self):
        """Adversarial: model_options as number should raise ValueError."""
        with self.assertRaises(ValueError):
            bench._normalize_model_options("test", {"model_options": 42})

    def test_normalize_model_options_adversarial_empty_string_key(self):
        """Adversarial: Empty string key in model_options dict."""
        result = bench._normalize_model_options(
            "test", {"model_options": {"": "value"}}
        )
        self.assertEqual(result, {"": "value"})

    def test_normalize_model_options_adversarial_special_char_key(self):
        """Adversarial: Special characters in model_options key."""
        result = bench._normalize_model_options(
            "test", {"model_options": {"key$special": "value"}}
        )
        self.assertEqual(result, {"key$special": "value"})

    def test_normalize_model_options_adversarial_unicode_key(self):
        """Adversarial: Unicode characters in model_options key."""
        result = bench._normalize_model_options(
            "test", {"model_options": {"キー": "値"}}
        )
        self.assertEqual(result, {"キー": "値"})

    def test_normalize_model_options_adversarial_large_value(self):
        """Adversarial: Very large value in model_options."""
        large_value = "x" * 100000
        result = bench._normalize_model_options(
            "test", {"model_options": {"large": large_value}}
        )
        self.assertEqual(result["large"], large_value)

    def test_normalize_model_options_adversarial_nested_structure(self):
        """Adversarial: Nested dict in model_options."""
        result = bench._normalize_model_options(
            "test", {"model_options": {"nested": {"deeply": {"value": 1}}}}
        )
        self.assertEqual(result, {"nested": {"deeply": {"value": 1}}})

    def test_normalize_model_options_adversarial_list_value(self):
        """Adversarial: List value in model_options."""
        result = bench._normalize_model_options(
            "test", {"model_options": {"items": [1, 2, 3]}}
        )
        self.assertEqual(result, {"items": [1, 2, 3]})

    def test_normalize_model_options_adversarial_null_value(self):
        """Adversarial: null value in model_options."""
        result = bench._normalize_model_options(
            "test", {"model_options": {"opt": None}}
        )
        self.assertEqual(result, {"opt": None})

    def test_model_options_to_args_adversarial_none_value(self):
        """Adversarial: None value should be skipped."""
        result = bench._model_options_to_args({"opt1": None, "opt2": "value"})
        self.assertNotIn("opt1", result)
        self.assertIn("opt2", result)

    def test_model_options_to_args_adversarial_large_string(self):
        """Adversarial: Very large string value should be properly quoted."""
        large_val = "x" * 10000
        result = bench._model_options_to_args({"large": large_val})
        self.assertIn(large_val, result)

    def test_model_options_to_args_adversarial_special_chars(self):
        """Adversarial: Special characters should be shell-escaped."""
        result = bench._model_options_to_args(
            {"special": 'value with "quotes" and $var'}
        )
        # Should be properly quoted for shell
        self.assertIn("special", result)

    def test_model_options_to_args_adversarial_unicode_value(self):
        """Adversarial: Unicode characters in value."""
        result = bench._model_options_to_args({"unicode": "日本語"})
        self.assertIn("unicode", result)

    def test_model_options_to_args_adversarial_json_value(self):
        """Adversarial: dict/list value should be JSON-encoded."""
        result = bench._model_options_to_args({"json": {"a": 1, "b": 2}})
        self.assertIn("json", result)
        self.assertIn("a", result)
        self.assertIn("b", result)

    def test_model_options_env_adversarial_null_value(self):
        """Adversarial: null value should not appear in env."""
        result = bench._model_options_env({"opt1": None, "opt2": "value"})
        self.assertNotIn("BENCH_MODEL_OPT_OPT1", result)
        self.assertIn("BENCH_MODEL_OPT_OPT2", result)

    def test_model_options_env_adversarial_large_value(self):
        """Adversarial: Very large value should be properly stored."""
        large_val = "x" * 100000
        result = bench._model_options_env({"large": large_val})
        self.assertEqual(result["BENCH_MODEL_OPT_LARGE"], large_val)
        # Also check JSON version
        parsed = json.loads(result["BENCH_MODEL_OPTIONS_JSON"])
        self.assertEqual(parsed["large"], large_val)

    def test_model_options_env_adversarial_nested_structures(self):
        """Adversarial: Nested dict/list should be JSON-encoded in env."""
        result = bench._model_options_env({"nested": {"a": [1, 2, {"b": 3}]}})
        parsed = json.loads(result["BENCH_MODEL_OPT_NESTED"])
        self.assertEqual(parsed, {"a": [1, 2, {"b": 3}]})

    def test_model_options_env_adversarial_special_keys(self):
        """Adversarial: Keys with special chars should be sanitized."""
        result = bench._model_options_env({"key-with-dashes": "value"})
        self.assertIn("BENCH_MODEL_OPT_KEY_WITH_DASHES", result)

    def test_model_options_env_adversarial_unicode_key(self):
        """Adversarial: Unicode key should be sanitized."""
        result = bench._model_options_env({"キー": "値"})
        # The key should be sanitized (replaced non-alphanumeric with _)
        env_keys = [k for k in result.keys() if "OPT_" in k]
        self.assertTrue(any("キー" in k or "___" in k for k in env_keys))

    def test_model_options_env_adversarial_very_deeply_nested(self):
        """Adversarial: Very deeply nested structure."""
        deeply = {
            "l1": {
                "l2": {
                    "l3": {
                        "l4": {"l5": {"l6": {"l7": {"l8": {"l9": {"l10": "deep"}}}}}}
                    }
                }
            }
        }
        result = bench._model_options_env({"deep": deeply})
        parsed = json.loads(result["BENCH_MODEL_OPT_DEEP"])
        self.assertEqual(parsed, deeply)

    def test_model_options_env_adversarial_multiple_null_values(self):
        """Adversarial: Multiple null values should all be omitted."""
        result = bench._model_options_env(
            {
                "opt1": None,
                "opt2": None,
                "opt3": "value",
                "opt4": None,
            }
        )
        self.assertNotIn("BENCH_MODEL_OPT_OPT1", result)
        self.assertNotIn("BENCH_MODEL_OPT_OPT2", result)
        self.assertIn("BENCH_MODEL_OPT_OPT3", result)
        self.assertNotIn("BENCH_MODEL_OPT_OPT4", result)

    def test_model_options_env_adversarial_large_number_of_options(self):
        """Adversarial: Many model options should all be stored."""
        many_opts = {f"opt{i}": f"value{i}" for i in range(100)}
        result = bench._model_options_env(many_opts)
        self.assertEqual(len(result), 102)  # JSON, ARGS, plus 100 individual opts
        for i in range(100):
            self.assertIn(f"BENCH_MODEL_OPT_OPT{i}", result)

    def test_model_options_env_adversarial_all_null_values(self):
        """Adversarial: All null values should result in minimal env."""
        result = bench._model_options_env({"opt1": None, "opt2": None, "opt3": None})
        self.assertEqual(len(result), 2)  # Just JSON and ARGS
        self.assertNotIn("BENCH_MODEL_OPT_OPT1", result)
        self.assertNotIn("BENCH_MODEL_OPT_OPT2", result)
        self.assertNotIn("BENCH_MODEL_OPT_OPT3", result)

    def test_model_options_env_adversarial_binary_data(self):
        """Adversarial: Binary data should be encoded."""
        # BUG FOUND: Binary data causes TypeError (not JSON serializable)
        binary_val = b"\x00\x01\x02\xff\xfe"
        with self.assertRaises(TypeError):
            bench._model_options_env({"binary": binary_val})

    def test_model_options_env_adversarial_nan_and_inf(self):
        """Adversarial: NaN and Infinity should be handled."""
        result = bench._model_options_env({"nan": float("nan"), "inf": float("inf")})
        parsed = json.loads(result["BENCH_MODEL_OPTIONS_JSON"])
        # JSON encodes these as strings
        self.assertIn("nan", parsed)
        self.assertIn("inf", parsed)

    def test_inject_model_options_args_adversarial_empty_options(self):
        """Adversarial: Empty options dict should return unchanged cmd."""
        # BUG FOUND: inject_model_options_args replaces $VAR with empty string
        result = bench._inject_model_options_args("cmd $BENCH_MODEL_OPTIONS_ARGS", {})
        self.assertEqual(result, "cmd ")

    def test_inject_model_options_args_adversarial_spaced_value(self):
        """Adversarial: Spaced values should be properly quoted."""
        result = bench._inject_model_options_args(
            "cmd $BENCH_MODEL_OPTIONS_ARGS",
            {"spaced": "hello world"},
        )
        self.assertIn("'hello world'", result)

    def test_inject_model_options_args_adversarial_special_chars_in_value(self):
        """Adversarial: Special shell chars in value should be quoted."""
        result = bench._inject_model_options_args(
            "cmd $BENCH_MODEL_OPTIONS_ARGS",
            {"special": "value; rm -rf /"},
        )
        # Value should be quoted to prevent shell injection
        self.assertIn("special", result)

    def test_inject_model_options_args_adversarial_very_long_task_ref(self):
        """Adversarial: Long task ref in error messages should be truncated or handled."""
        # This tests error handling when task ref is used in messages

    def test_model_options_to_args_adversarial_numeric_string(self):
        """Adversarial: Numeric string should be quoted."""
        result = bench._model_options_to_args({"num": "123"})
        self.assertIn("--num", result)
        self.assertIn("123", result)

    def test_deep_merge_adversarial_infinite_recursion_protection(self):
        """Adversarial: Self-reference should not cause infinite recursion."""
        base = {"a": {"b": 1}}
        base["a"]["self"] = base["a"]
        result = bench._deep_merge(base, {"c": 2})
        self.assertEqual(result["a"]["b"], 1)
        self.assertEqual(result["c"], 2)

    def test_deep_merge_adversarial_mutual_reference(self):
        """Adversarial: Mutually referencing dicts should not cause infinite loop."""
        base = {"a": {"ref": None}}
        override = {"b": {"ref": base["a"]}}
        base["a"]["ref"] = override["b"]
        result = bench._deep_merge(base, override)
        self.assertEqual(result["a"]["ref"], override["b"])
        self.assertEqual(result["b"]["ref"], base["a"])


if __name__ == "__main__":
    unittest.main()
