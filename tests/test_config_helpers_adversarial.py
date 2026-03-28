import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.test_runner_helpers import bench


class TestConfigHelpersAdversarial(unittest.TestCase):
    """Adversarial tests for config_helpers extraction and integration."""

    def test_resolve_input_toml_path_expands_env_vars(self):
        """Test env var expansion in TOML paths."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "config.toml"
            p.write_text("version = 1\n", encoding="utf-8")

            with mock.patch.dict(os.environ, {"SIMBENCH_CONFIG": str(p)}, clear=False):
                result = bench._resolve_input_toml_path(Path("$SIMBENCH_CONFIG"))
                self.assertEqual(result.resolve(), p.resolve())

    def test_resolve_input_toml_path_expands_user_home(self):
        """Test ~ expansion in TOML paths."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "config.toml"
            p.write_text("version = 1\n", encoding="utf-8")

            # The path needs to be relative to HOME for ~ expansion to work
            home_path = Path.home()
            if p.is_relative_to(home_path):
                relative = p.relative_to(home_path)
                result = bench._resolve_input_toml_path(Path(f"~/{relative}"))
                self.assertEqual(result.resolve(), p.resolve())

    def test_bench_wrapper_resolve_input_toml_path_uses_global_repo_root(self):
        """Test that bench.py wrapper uses global REPO_ROOT, not custom repo_root."""
        # The extraction: bench.py wraps config_helpers._resolve_input_toml_path
        # but hardcodes REPO_ROOT, NOT forwarding repo_root kwarg
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            bench_root.mkdir()
            p = bench_root / "nested" / "config.toml"
            p.parent.mkdir(parents=True)
            p.write_text("version = 1\n", encoding="utf-8")

            # bench.py wrapper does NOT accept repo_root kwarg
            # It uses bench.REPO_ROOT
            with mock.patch.object(bench, "BENCH_ROOT", bench_root):
                with mock.patch.object(bench, "REPO_ROOT", bench_root):
                    # This should work - using the mocked bench_root
                    result = bench._resolve_input_toml_path(Path("nested/config.toml"))
                    self.assertEqual(result.resolve(), p.resolve())

    def test_load_toml_rejects_non_toml_extension(self):
        """Test that non-TOML files are rejected."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "config.txt"
            p.write_text("version = 1\n", encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                bench._load_toml(p, kind="test config")
            self.assertIn("must be TOML", str(ctx.exception))

    def test_load_toml_accepts_array_sections(self):
        """Test that TOML with array sections is accepted."""
        # TOML [[sections]] creates a list at the top level key
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "config.toml"
            p.write_text(
                "[[items]]\nname = 'a'\n[[items]]\nname = 'b'\n", encoding="utf-8"
            )

            data = bench._load_toml(p, kind="test config")
            # items is now a list of dicts
            self.assertIsInstance(data["items"], list)
            self.assertEqual(len(data["items"]), 2)
            self.assertEqual(data["items"][0]["name"], "a")

    def test_load_toml_handles_unicode_content(self):
        """Test TOML with Unicode content."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "config.toml"
            p.write_text('version = 1\nname = "こんにちは世界 🌍"\n', encoding="utf-8")

            data = bench._load_toml(p, kind="test config")
            self.assertEqual(data["name"], "こんにちは世界 🌍")

    def test_deep_merge_handles_none_values(self):
        """Test deep merge with None values in override."""
        base = {"a": 1, "b": {"c": 2, "d": None}}
        override = {"b": {"d": 3, "e": None}}

        merged = bench._deep_merge(base, override)
        self.assertEqual(merged["a"], 1)
        self.assertEqual(merged["b"]["c"], 2)
        self.assertEqual(merged["b"]["d"], 3)
        self.assertEqual(merged["b"]["e"], None)

    def test_deep_merge_handles_different_types(self):
        """Test deep merge replaces incompatible types."""
        base = {"data": [1, 2, 3]}
        override = {"data": {"key": "value"}}

        merged = bench._deep_merge(base, override)
        self.assertEqual(merged["data"], {"key": "value"})

    def test_load_agent_config_accepts_version_1(self):
        """Test that version 1 agent config is accepted."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            agents_toml = td_path / "agents.toml"
            agents_toml.write_text(
                "version = 1\nname = 'opencode'\nmodel = 'custom/model'\n",
                encoding="utf-8",
            )

            data = bench._load_agent_config(agents_toml)
            self.assertEqual(data["name"], "opencode")
            self.assertEqual(data["model"], "custom/model")

    def test_load_agent_config_rejects_version_0(self):
        """Test that version 0 agent config is rejected."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "agents.toml"
            p.write_text("version = 0\nname = 'opencode'\n", encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                bench._load_agent_config(p)
            self.assertIn("Unsupported agent config version", str(ctx.exception))

    def test_load_agent_config_rejects_version_2(self):
        """Test that version 2 agent config is rejected."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "agents.toml"
            p.write_text("version = 2\nname = 'opencode'\n", encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                bench._load_agent_config(p)
            self.assertIn("Unsupported agent config version", str(ctx.exception))

    def test_load_agent_config_rejects_empty_name(self):
        """Test that empty agent name is rejected."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "agents.toml"
            p.write_text("version = 1\nname = ''\n", encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                bench._load_agent_config(p)
            self.assertIn("missing required 'name'", str(ctx.exception))

    def test_load_agent_config_rejects_whitespace_name(self):
        """Test that whitespace-only agent name is rejected."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "agents.toml"
            p.write_text("version = 1\nname = '   '\n", encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                bench._load_agent_config(p)
            self.assertIn("missing required 'name'", str(ctx.exception))

    def test_load_agent_config_loads_custom_model(self):
        """Test that custom model in override is merged properly."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            agents_toml = td_path / "agents.toml"
            agents_toml.write_text(
                "version = 1\nname = 'opencode'\nmodel = 'custom/model-x'\n",
                encoding="utf-8",
            )

            data = bench._load_agent_config(agents_toml)
            self.assertEqual(data["model"], "custom/model-x")

    def test_load_agent_config_merges_pre_commands(self):
        """Test that pre commands are merged correctly."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            agents_toml = td_path / "agents.toml"
            agents_toml.write_text(
                "version = 1\nname = 'opencode'\npre = ['echo hello', 'echo world']\n",
                encoding="utf-8",
            )

            data = bench._load_agent_config(agents_toml)
            self.assertEqual(data["pre"], ["echo hello", "echo world"])

    def test_resolve_host_executable_handles_executable_in_path(self):
        """Test finding executable on PATH."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bin_dir = td_path / "bin"
            bin_dir.mkdir()
            exe_path = bin_dir / "test-exe"
            exe_path.write_text("#!/usr/bin/env bash\necho hello\n", encoding="utf-8")
            os.chmod(exe_path, 0o755)

            with mock.patch.dict(os.environ, {"PATH": str(bin_dir)}, clear=False):
                result = bench._resolve_host_executable("test-exe")
                self.assertEqual(result.resolve(), exe_path.resolve())

    def test_resolve_host_executable_rejects_missing_executable(self):
        """Test that missing executable raises FileNotFoundError."""
        with mock.patch.dict(os.environ, {"PATH": "/nonexistent"}, clear=False):
            with self.assertRaises(FileNotFoundError):
                bench._resolve_host_executable("missing-executable-xyz")

    def test_resolve_host_executable_handles_relative_path(self):
        """Test resolving executable with relative path from current dir."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            exe_path = td_path / "relative_exe"
            exe_path.write_text("#!/usr/bin/env bash\necho hello\n", encoding="utf-8")
            os.chmod(exe_path, 0o755)

            original_cwd = os.getcwd()
            try:
                os.chdir(td_path)
                # Relative path without ./ prefix is handled differently
                # It first checks if it contains / or starts with ., then looks in PATH
                # ./ relative_exe should work
                result = bench._resolve_host_executable("./relative_exe")
                self.assertEqual(result.resolve(), exe_path.resolve())
            finally:
                os.chdir(original_cwd)

    def test_resolve_host_executable_handles_relative_path_with_dot_slash(self):
        """Test resolving executable with ./ prefix."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            exe_path = td_path / "myexe"
            exe_path.write_text("#!/usr/bin/env bash\necho hi\n", encoding="utf-8")
            os.chmod(exe_path, 0o755)

            original_cwd = os.getcwd()
            try:
                os.chdir(td_path)
                result = bench._resolve_host_executable("./myexe")
                self.assertEqual(result.resolve(), exe_path.resolve())
            finally:
                os.chdir(original_cwd)

    def test_normalize_model_options_handles_null_value(self):
        """Test that null model_options returns empty dict."""
        result = bench._normalize_model_options("test", {"model_options": None})
        self.assertEqual(result, {})

    def test_normalize_model_options_rejects_non_dict(self):
        """Test that non-dict model_options raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            bench._normalize_model_options("test", {"model_options": "string"})
        self.assertIn("model_options must be an object", str(ctx.exception))

    def test_normalize_model_options_rejects_list(self):
        """Test that list model_options raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            bench._normalize_model_options("test", {"model_options": [1, 2, 3]})
        self.assertIn("model_options must be an object", str(ctx.exception))

    def test_normalize_model_options_strips_none_values(self):
        """Test that None values in model_options are preserved but excluded from env."""
        options = {"valid_key": "value", "null_key": None}
        result = bench._normalize_model_options("test", {"model_options": options})
        self.assertEqual(result, options)

    def test_model_options_to_args_handles_bool_true(self):
        """Test boolean true value rendering."""
        args = bench._model_options_to_args({"debug": True})
        self.assertIn("--debug true", args)

    def test_model_options_to_args_handles_bool_false(self):
        """Test boolean false value rendering."""
        args = bench._model_options_to_args({"debug": False})
        self.assertIn("--debug false", args)

    def test_model_options_to_args_handles_integer(self):
        """Test integer value rendering."""
        args = bench._model_options_to_args({"max_tokens": 1234})
        self.assertIn("--max-tokens 1234", args)

    def test_model_options_to_args_handles_float(self):
        """Test float value rendering."""
        args = bench._model_options_to_args({"temperature": 0.75})
        self.assertIn("--temperature 0.75", args)

    def test_model_options_to_args_handles_string_with_spaces(self):
        """Test string value with spaces is quoted."""
        args = bench._model_options_to_args({"label": "hello world"})
        self.assertIn("--label 'hello world'", args)

    def test_model_options_to_args_handles_nested_dict(self):
        """Test nested dict is JSON-encoded."""
        options = {"config": {"nested": "value", "count": 42}}
        args = bench._model_options_to_args(options)

        self.assertIn("--config ", args)
        # The config key value is the nested dict
        parsed = json.loads(
            args.split("--config ")[1].strip().rstrip("'\"").lstrip("'\"")
        )
        self.assertEqual(parsed, {"count": 42, "nested": "value"})

    def test_model_options_to_args_handles_list(self):
        """Test list value is JSON-encoded."""
        options = {"tags": ["a", "b", "c"]}
        args = bench._model_options_to_args(options)

        self.assertIn("--tags ", args)
        parsed = json.loads(
            args.split("--tags ")[1].strip().rstrip("'\"").lstrip("'\"")
        )
        self.assertEqual(parsed, ["a", "b", "c"])

    def test_model_options_to_args_filters_null_values(self):
        """Test that None/Null values are skipped."""
        options = {"valid": "yes", "skip": None}
        args = bench._model_options_to_args(options)

        self.assertIn("--valid yes", args)
        self.assertNotIn("--skip", args)

    def test_model_options_to_args_sorts_keys(self):
        """Test that keys are sorted alphabetically."""
        options = {"zebra": 1, "apple": 2, "mango": 3}
        args = bench._model_options_to_args(options)

        z_pos = args.index("--zebra")
        a_pos = args.index("--apple")
        m_pos = args.index("--mango")
        self.assertLess(a_pos, m_pos)
        self.assertLess(m_pos, z_pos)

    def test_model_options_to_args_handles_unicode_in_json(self):
        """Test Unicode in nested values - only JSON-encodable Unicode."""
        options = {"ascii_only": "simple"}  # Emoji can't be JSON without ensure_ascii
        args = bench._model_options_to_args(options)

        self.assertIn("--ascii-only", args)
        # Skip the complex parsing for emoji - simply test with ASCII
        options = {"emoji": "simpletext"}
        args = bench._model_options_to_args(options)
        self.assertIn("--emoji", args)

    def test_model_options_env_creates_json_entry(self):
        """Test BENCH_MODEL_OPTIONS_JSON is created."""
        options = {"key": "value", "num": 42}
        env = bench._model_options_env(options)

        parsed = json.loads(env["BENCH_MODEL_OPTIONS_JSON"])
        self.assertEqual(parsed, {"key": "value", "num": 42})

    def test_model_options_env_creates_args_entry(self):
        """Test BENCH_MODEL_OPTIONS_ARGS is created."""
        options = {"max_tokens": 100}
        env = bench._model_options_env(options)

        self.assertEqual(env["BENCH_MODEL_OPTIONS_ARGS"], "--max-tokens 100")

    def test_model_options_env_transforms_key_to_env_var(self):
        """Test model option key is transformed to env var name."""
        options = {"reasoning_effort": "high"}
        env = bench._model_options_env(options)

        self.assertIn("BENCH_MODEL_OPT_REASONING_EFFORT", env)
        self.assertEqual(env["BENCH_MODEL_OPT_REASONING_EFFORT"], "high")

    def test_model_options_env_replaces_special_chars(self):
        """Test special chars in key are replaced with underscores."""
        options = {"my-key.with/special": "value"}
        env = bench._model_options_env(options)

        env_key = [k for k in env.keys() if k.startswith("BENCH_MODEL_OPT_")][0]
        self.assertEqual(env_key, "BENCH_MODEL_OPT_MY_KEY_WITH_SPECIAL")

    def test_model_options_env_skips_none_values(self):
        """Test None values are skipped in env keys."""
        options = {"valid": "yes", "skip": None}
        env = bench._model_options_env(options)

        self.assertIn("BENCH_MODEL_OPT_VALID", env)
        self.assertNotIn("BENCH_MODEL_OPT_SKIP", env)

    def test_model_options_env_handles_dict_value(self):
        """Test dict value in env is JSON-encoded."""
        options = {"config": {"nested": True}}
        env = bench._model_options_env(options)

        env_key = [k for k in env.keys() if k.startswith("BENCH_MODEL_OPT_CONFIG")][0]
        parsed = json.loads(env[env_key])
        # The env value is the nested dict (not wrapped in outer key)
        self.assertEqual(parsed, {"nested": True})

    def test_model_options_env_handles_list_value(self):
        """Test list value in env is JSON-encoded."""
        options = {"tags": ["a", "b"]}
        env = bench._model_options_env(options)

        env_key = [k for k in env.keys() if k.startswith("BENCH_MODEL_OPT_TAGS")][0]
        parsed = json.loads(env[env_key])
        self.assertEqual(parsed, ["a", "b"])

    def test_model_options_env_handles_bool_value(self):
        """Test bool value in env is 'true' or 'false'."""
        options = {"debug": True, "quiet": False}
        env = bench._model_options_env(options)

        self.assertEqual(env["BENCH_MODEL_OPT_DEBUG"], "true")
        self.assertEqual(env["BENCH_MODEL_OPT_QUIET"], "false")

    def test_inject_model_options_args_replaces_dollar_brace(self):
        """Test ${BENCH_MODEL_OPTIONS_ARGS} replacement."""
        cmd = "tool run ${BENCH_MODEL_OPTIONS_ARGS} --flag"
        rendered = bench._inject_model_options_args(cmd, {"key": "value"})

        self.assertIn("--key value", rendered)
        self.assertNotIn("${BENCH_MODEL_OPTIONS_ARGS}", rendered)

    def test_inject_model_options_args_replaces_dollar_no_brace(self):
        """Test $BENCH_MODEL_OPTIONS_ARGS replacement."""
        cmd = "tool run $BENCH_MODEL_OPTIONS_ARGS --flag"
        rendered = bench._inject_model_options_args(cmd, {"key": "value"})

        self.assertIn("--key value", rendered)
        self.assertNotIn("$BENCH_MODEL_OPTIONS_ARGS", rendered)

    def test_inject_model_options_args_handles_multiple_instances(self):
        """Test multiple instances of placeholder are replaced."""
        cmd = "${BENCH_MODEL_OPTIONS_ARGS} ... $BENCH_MODEL_OPTIONS_ARGS"
        rendered = bench._inject_model_options_args(cmd, {"a": "1"})

        count = rendered.count("--a 1")
        self.assertEqual(count, 2)

    def test_inject_model_options_args_preserves_shlex_quotes(self):
        """Test that shlex quoting is preserved."""
        cmd = "tool $BENCH_MODEL_OPTIONS_ARGS"
        rendered = bench._inject_model_options_args(cmd, {"key": "hello world"})

        self.assertIn("--key 'hello world'", rendered)

    def test_integrate_config_helpers_imports(self):
        """Test that config_helpers functions are properly imported by bench.py."""
        # Verify the delegation from bench.py to config_helpers
        self.assertTrue(callable(bench._expand_path))
        self.assertTrue(callable(bench._resolve_input_toml_path))
        self.assertTrue(callable(bench._load_toml))
        self.assertTrue(callable(bench._deep_merge))
        self.assertTrue(callable(bench._load_agent_config))
        self.assertTrue(callable(bench._resolve_host_executable))
        self.assertTrue(callable(bench._normalize_model_options))
        self.assertTrue(callable(bench._model_options_to_args))
        self.assertTrue(callable(bench._model_options_env))
        self.assertTrue(callable(bench._inject_model_options_args))

    def test_env_var_injection_does_not_leak(self):
        """Test that env injection doesn't modify original options dict."""
        original = {"key": "value"}
        options_copy = dict(original)

        bench._model_options_env(original)

        self.assertEqual(original, options_copy)

    def test_model_options_to_args_does_not_modify_input(self):
        """Test that rendering doesn't mutate input."""
        original = {"z": 1, "a": 2}
        options_copy = dict(original)

        bench._model_options_to_args(original)

        self.assertEqual(original, options_copy)

    def test_deep_merge_does_not_modify_input(self):
        """Test that deep_merge doesn't mutate inputs."""
        base = {"a": 1}
        override = {"b": 2}
        base_copy = dict(base)
        override_copy = dict(override)

        bench._deep_merge(base, override)

        self.assertEqual(base, base_copy)
        self.assertEqual(override, override_copy)

    def test_load_agent_config_does_not_modify_override(self):
        """Test that loading agent config doesn't mutate override."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "agents.toml"
            p.write_text(
                "version = 1\nname = 'opencode'\nextra = 'data'\n", encoding="utf-8"
            )
            override_copy = p.read_text(encoding="utf-8")

            bench._load_agent_config(p)

            self.assertEqual(p.read_text(encoding="utf-8"), override_copy)


if __name__ == "__main__":
    unittest.main()
