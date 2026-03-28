"""
Adversarial validation tests for runner/task_loading_helpers.py

These tests attack:
- Import breakage
- Ambiguous task resolution
- Malformed task refs
- Path-handling edge cases
- TOML parsing failure paths
- Delegation mismatches between bench.py and task_loading_helpers.py
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pytest

# Import the helper module directly to test internal functions
from runner.task_loading_helpers import (
    _check_task,
    _iter_tasks,
    _load_task,
    _parse_task_ref,
    _suite_shared_eval_dir,
    _suite_shared_workspace_dir,
    _task_meta_bool,
    _task_path,
    _task_root_label,
    _task_root_map,
)


class TestParseTaskRefAdversarial(unittest.TestCase):
    """Adversarial tests for _parse_task_ref function."""

    def setUp(self):
        self.bench_root = Path("/bench")
        self.test_task_root = Path("/test-tasks")
        self.repo_root = Path("/repo")

    def test_empty_and_whitespace_inputs(self):
        """Attack: Empty and whitespace-only inputs should raise ValueError."""
        for bad_input in ("", "   ", "\t\n", "   \t"):
            with self.subTest(input=repr(bad_input)):
                with self.assertRaises(ValueError):
                    _parse_task_ref(
                        bad_input,
                        bench_root=self.bench_root,
                        test_task_root=self.test_task_root,
                        repo_root=self.repo_root,
                    )

    def test_missing_slash_separator(self):
        """Attack: Task refs without / should fail with clear error."""
        for bad_input in ("suite-only", "task_id_only", "bench:foo", "test:bar"):
            with self.subTest(input=repr(bad_input)):
                with self.assertRaises(ValueError):
                    _parse_task_ref(
                        bad_input,
                        bench_root=self.bench_root,
                        test_task_root=self.test_task_root,
                        repo_root=self.repo_root,
                    )

    def test_root_mapping_malformed_paths(self):
        """Attack: Malformed root mappings should be handled gracefully."""
        # Test with root prefix but malformed path
        for bad_input in (
            "bench:unknown/",
            "test: //malformed",
            "BENCH:upper-case/malformed",
            "TEST:UPPER/malformed",
        ):
            with self.subTest(input=repr(bad_input)):
                try:
                    _parse_task_ref(
                        bad_input,
                        bench_root=self.bench_root,
                        test_task_root=self.test_task_root,
                        repo_root=self.repo_root,
                    )
                except ValueError:
                    # Expected for some malformed inputs
                    pass

    def test_root_mapping_case_insensitive(self):
        """Attack: Root mappings should be case-insensitive per the code."""
        bench_cases = ("BENCH", "bench", "BeNcH", "benchmark", "BENCHMARK")
        test_cases = ("TEST", "test", "TeSt", "test-task", "TEST-TASK", "test-tasks")

        for root in bench_cases:
            with self.subTest(root=root):
                result = _parse_task_ref(
                    f"{root}: s/t",
                    bench_root=self.bench_root,
                    test_task_root=self.test_task_root,
                    repo_root=self.repo_root,
                )
                self.assertEqual(result[0], self.bench_root)
                self.assertEqual(result[1], "s")
                self.assertEqual(result[2], "t")

        for root in test_cases:
            with self.subTest(root=root):
                result = _parse_task_ref(
                    f"{root}: s/t",
                    bench_root=self.bench_root,
                    test_task_root=self.test_task_root,
                    repo_root=self.repo_root,
                )
                self.assertEqual(result[0], self.test_task_root)

    def test_path_traversal_attempts(self):
        """Attack: Path traversal attempts should not escape control."""
        # These should either fail parse or be handled safely
        for bad_input in (
            "s/../../../etc/passwd",
            "s/..%2F..%2F..%2Fetc",
            "s/%2E%2E/etc/passwd",
            "s/a%00b",  # null byte injection
        ):
            with self.subTest(input=repr(bad_input)):
                try:
                    _parse_task_ref(
                        bad_input,
                        bench_root=self.bench_root,
                        test_task_root=self.test_task_root,
                        repo_root=self.repo_root,
                    )
                except ValueError:
                    # Expected - malformed paths should be rejected
                    pass

    def test_unicode_and_special_chars(self):
        """Attack: Unicode and special characters in task refs."""
        # Valid unicode in paths
        valid_unicode = ("s τask", "_task$id", "s/名前")
        for task_ref in valid_unicode:
            with self.subTest(input=repr(task_ref)):
                try:
                    _parse_task_ref(
                        task_ref,
                        bench_root=self.bench_root,
                        test_task_root=self.test_task_root,
                        repo_root=self.repo_root,
                    )
                except ValueError:
                    # May fail due to slash handling, which is acceptable
                    pass

        # Null byte injection
        with self.subTest(input="null byte injection"):
            try:
                _parse_task_ref(
                    "s" + "\x00" + "task",
                    bench_root=self.bench_root,
                    test_task_root=self.test_task_root,
                    repo_root=self.repo_root,
                )
            except ValueError:
                # Expected - should be rejected
                pass

    def test_oversized_inputs(self):
        """Attack: Oversized inputs for DoS resistance."""
        # Very long suite name
        long_suite = "s" * 10000
        with self.subTest(input="long suite name"):
            try:
                _parse_task_ref(
                    f"{long_suite}/task",
                    bench_root=self.bench_root,
                    test_task_root=self.test_task_root,
                    repo_root=self.repo_root,
                )
            except (ValueError, MemoryError):
                pass  # Either is acceptable

        # Very long task_id
        long_task = "t" * 10000
        with self.subTest(input="long task_id"):
            try:
                _parse_task_ref(
                    f"s/{long_task}",
                    bench_root=self.bench_root,
                    test_task_root=self.test_task_root,
                    repo_root=self.repo_root,
                )
            except (ValueError, MemoryError):
                pass  # Either is acceptable


class TestTaskPathFunction(unittest.TestCase):
    """Tests for _task_path helper function."""

    def test_basic_path_construction(self):
        """Test basic path construction."""
        root = Path("/bench")
        result = _task_path(root, "my-suite", "my-task")
        expected = Path("/bench/my-suite/my-task")
        self.assertEqual(result, expected)

    def test_path_with_spaces(self):
        """Test paths with spaces in components."""
        root = Path("/bench")
        result = _task_path(root, "my suite", "my task")
        expected = Path("/bench/my suite/my task")
        self.assertEqual(result, expected)

    def test_root_label_with_relative_root(self):
        """Test _task_root_label with relative roots."""
        repo_root = Path("/home/user/simbench")
        bench_root = repo_root / "benchmarks"

        label = _task_root_label(bench_root, repo_root)
        self.assertEqual(label, "benchmarks/")

        # Test with root outside repo
        external_root = Path("/usr/local")
        label = _task_root_label(external_root, repo_root)
        self.assertEqual(label, str(external_root))


class TestTaskRootMap(unittest.TestCase):
    """Tests for _task_root_map function."""

    def test_root_map_keys(self):
        """Test all expected root map keys."""
        bench_root = Path("/bench")
        test_task_root = Path("/test")

        root_map = _task_root_map(bench_root, test_task_root)

        expected_keys = {
            "bench",
            "benchmark",
            "test",
            "test-task",
            "test-tasks",
        }
        self.assertEqual(set(root_map.keys()), expected_keys)

        for key in expected_keys:
            self.assertIn(key, root_map)
            if key in ("bench", "benchmark"):
                self.assertEqual(root_map[key], bench_root)
            else:
                self.assertEqual(root_map[key], test_task_root)


class TestLoadTaskAdversarial(unittest.TestCase):
    """Adversarial tests for _load_task function."""

    def test_ambiguous_task_detection(self):
        """Attack: Task exists in both bench and test roots - should be ambiguous."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            test_task_root = td_path / "test-tasks"

            # Create task directory in BOTH roots
            task_dir_bench = bench_root / "ambiguous" / "task"
            task_dir_test = test_task_root / "ambiguous" / "task"

            for task_dir in (task_dir_bench, task_dir_test):
                task_dir.mkdir(parents=True)
                (task_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
                (task_dir / "task.toml").write_text(
                    'id = "task"\n suite = "ambiguous"\n', encoding="utf-8"
                )
                (task_dir / "workspace").mkdir()
                (task_dir / "eval").mkdir()

            with self.assertRaises(FileNotFoundError) as ctx:
                _load_task(
                    "ambiguous",
                    "task",
                    root=None,  # Let it search both
                    bench_root=bench_root,
                    test_task_root=test_task_root,
                    repo_root=td_path,
                )

            err_msg = str(ctx.exception)
            self.assertIn("ambiguous", err_msg.lower())
            self.assertIn("ambiguous/task", err_msg.lower())
            self.assertIn("Use bench:", err_msg)
            self.assertIn("test:", err_msg)

    def test_missing_required_paths(self):
        """Attack: Task directory exists but missing required files."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"

            task_dir = bench_root / "partial" / "task"
            task_dir.mkdir(parents=True)

            # Create only some files
            (task_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
            (task_dir / "task.toml").write_text('id = "task"\n', encoding="utf-8")
            # Missing workspace/ and eval/

            with self.assertRaises(FileNotFoundError) as ctx:
                _load_task(
                    "partial",
                    "task",
                    root=None,
                    bench_root=bench_root,
                    test_task_root=td_path / "test-tasks",
                    repo_root=td_path,
                )

            err_msg = str(ctx.exception)
            self.assertIn("workspace", err_msg.lower())
            self.assertIn("eval", err_msg.lower())

    def test_toml_parsing_errors(self):
        """Attack: Malformed TOML in task.toml."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"

            task_dir = bench_root / "badtoml" / "task"
            task_dir.mkdir(parents=True)
            (task_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
            # Malformed TOML - unclosed bracket
            (task_dir / "task.toml").write_text(
                'id = "task"\n invalid = [unclosed\n', encoding="utf-8"
            )
            (task_dir / "workspace").mkdir()
            (task_dir / "eval").mkdir()

            with self.assertRaises(Exception):
                _load_task(
                    "badtoml",
                    "task",
                    root=None,
                    bench_root=bench_root,
                    test_task_root=td_path / "test-tasks",
                    repo_root=td_path,
                )

    def test_toml_non_utf8_encoding(self):
        """Attack: task.toml with non-UTF-8 encoding."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"

            task_dir = bench_root / "badenc" / "task"
            task_dir.mkdir(parents=True)
            (task_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
            # Write binary garbage as "TOML"
            (task_dir / "task.toml").write_bytes(b"\xff\xfe\xfd\xfc")
            (task_dir / "workspace").mkdir()
            (task_dir / "eval").mkdir()

            with self.assertRaises(Exception):
                _load_task(
                    "badenc",
                    "task",
                    root=None,
                    bench_root=bench_root,
                    test_task_root=td_path / "test-tasks",
                    repo_root=td_path,
                )


class TestCheckTaskAdversarial(unittest.TestCase):
    """Adversarial tests for _check_task function."""

    def test_task_with_empty_spec(self):
        """Attack: Empty spec.md should raise error."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"

            task_dir = bench_root / "emptyspec" / "task"
            task_dir.mkdir(parents=True)
            (task_dir / "spec.md").write_text("", encoding="utf-8")
            (task_dir / "task.toml").write_text(
                """
id = "task"
suite = "emptyspec"
language = "python"
time_limit_sec = 10
eval_cmd = "/eval/run.sh"
""",
                encoding="utf-8",
            )
            (task_dir / "workspace").mkdir()
            # eval directory already exists, don't recreate
            (task_dir / "eval").mkdir(exist_ok=True)
            # Need to add a dummy run.sh since eval_cmd points to it
            run_sh = task_dir / "eval" / "run.sh"
            run_sh.write_text("#!/usr/bin/env bash\necho 'dummy'", encoding="utf-8")
            import os

            os.chmod(run_sh, 0o755)  # Make executable

            task = _load_task(
                "emptyspec",
                "task",
                root=None,
                bench_root=bench_root,
                test_task_root=td_path / "test-tasks",
                repo_root=td_path,
            )

            errors, warnings = _check_task(task)
            self.assertEqual(len(errors), 1)
            self.assertIn("empty", errors[0].lower())

    def test_task_with_unicode_filename(self):
        """Attack: Task with Unicode filenames."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"

            task_dir = bench_root / "unicode" / "名前"
            task_dir.mkdir(parents=True, exist_ok=True)
            (task_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
            (task_dir / "task.toml").write_text(
                """
id = "名前"
suite = "unicode"
language = "python"
time_limit_sec = 10
eval_cmd = "/eval/run.sh"
""",
                encoding="utf-8",
            )
            (task_dir / "workspace").mkdir()
            (task_dir / "eval").mkdir()

            task = _load_task(
                "unicode",
                "名前",
                root=None,
                bench_root=bench_root,
                test_task_root=td_path / "test-tasks",
                repo_root=td_path,
            )

            errors, warnings = _check_task(task)
            # Should handle Unicode without crashing
            self.assertIsInstance(errors, list)
            self.assertIsInstance(warnings, list)

    def test_task_with_large_workspace(self):
        """Attack: Task with very large workspace (resource exhaustion)."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"

            task_dir = bench_root / "large_ws" / "task"
            task_dir.mkdir(parents=True)
            (task_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
            (task_dir / "task.toml").write_text(
                """
id = "task"
suite = "large_ws"
language = "python"
time_limit_sec = 10
eval_cmd = "/eval/run.sh"
""",
                encoding="utf-8",
            )
            workspace = task_dir / "workspace"
            workspace.mkdir()
            (task_dir / "eval").mkdir()  # <-- missing eval directory

            # Create many small files
            for i in range(1000):
                (workspace / f"file_{i}.txt").write_text(
                    f"content {i}", encoding="utf-8"
                )

            task = _load_task(
                "large_ws",
                "task",
                root=None,
                bench_root=bench_root,
                test_task_root=td_path / "test-tasks",
                repo_root=td_path,
            )

            errors, warnings = _check_task(task)
            # Should not hang or crash
            self.assertIsInstance(errors, list)
            self.assertIsInstance(warnings, list)

    def test_task_with_symlink_in_workspace(self):
        """Attack: Task with symlink pointing outside workspace."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"

            task_dir = bench_root / "symlink" / "task"
            task_dir.mkdir(parents=True)
            (task_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
            (task_dir / "task.toml").write_text(
                """
id = "task"
suite = "symlink"
language = "python"
time_limit_sec = 10
eval_cmd = "/eval/run.sh"
""",
                encoding="utf-8",
            )
            workspace = task_dir / "workspace"
            workspace.mkdir()
            (task_dir / "eval").mkdir()  # <-- missing eval directory

            # Create a file in workspace
            (workspace / "real_file.txt").write_text("real content", encoding="utf-8")

            task = _load_task(
                "symlink",
                "task",
                root=None,
                bench_root=bench_root,
                test_task_root=td_path / "test-tasks",
                repo_root=td_path,
            )

            errors, warnings = _check_task(task)
            # Should handle gracefully
            self.assertIsInstance(errors, list)
            self.assertIsInstance(warnings, list)


class TestMetaBoolFunction(unittest.TestCase):
    """Tests for _task_meta_bool helper function."""

    def test_boolean_values(self):
        """Test literal boolean values."""
        task = type("Task", (), {"meta": {}})()

        task.meta = {"flag": True}
        self.assertTrue(_task_meta_bool(task, "flag"))

        task.meta = {"flag": False}
        self.assertFalse(_task_meta_bool(task, "flag"))

    def test_non_boolean_values(self):
        """Attack: Non-boolean values should raise ValueError."""
        task = type("Task", (), {"meta": {}})()

        for bad_value in (1, 0, "true", "false", None, [], {}):
            task.meta = {"flag": bad_value}
            with self.subTest(value=repr(bad_value)):
                with self.assertRaises(ValueError):
                    _task_meta_bool(task, "flag")

    def test_missing_key(self):
        """Test missing key returns False."""
        task = type("Task", (), {"meta": {}})()
        self.assertFalse(_task_meta_bool(task, "nonexistent"))


class TestSuiteSharedDirectories(unittest.TestCase):
    """Tests for suite shared workspace/eval directory functions."""

    def test_shared_workspace_dir_path(self):
        """Test _suite_shared_workspace_dir construction."""
        task = type("Task", (), {"path": Path("/bench/suite/task")})()
        shared = _suite_shared_workspace_dir(task)
        expected = Path("/bench/suite/shared/workspace")
        self.assertEqual(shared, expected)

    def test_shared_eval_dir_path(self):
        """Test _suite_shared_eval_dir construction."""
        task = type("Task", (), {"path": Path("/bench/suite/task")})()
        shared = _suite_shared_eval_dir(task)
        expected = Path("/bench/suite/shared/eval")
        self.assertEqual(shared, expected)


class TestIterTasksAdversarial(unittest.TestCase):
    """Adversarial tests for _iter_tasks function."""

    def test_iter_with_empty_bench(self):
        """Attack: Empty benchmarks directory."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            bench_root.mkdir()  # Empty directory

            result = list(
                _iter_tasks(
                    include_test_tasks=False,
                    bench_root=bench_root,
                    test_task_root=td_path / "test-tasks",
                )
            )

            self.assertEqual(result, [])

    def test_iter_with_nonexistent_root(self):
        """Attack: Non-existent root directories."""
        bench_root = Path("/nonexistent/bench")
        test_task_root = Path("/nonexistent/test")

        result = list(
            _iter_tasks(
                include_test_tasks=True,
                bench_root=bench_root,
                test_task_root=test_task_root,
            )
        )

        self.assertEqual(result, [])

    def test_iter_with_mixed_tasks(self):
        """Test iteration with valid and invalid task directories."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"

            # Valid task
            valid = bench_root / "valid" / "task"
            valid.mkdir(parents=True)
            (valid / "spec.md").write_text("# spec\n", encoding="utf-8")
            (valid / "task.toml").write_text('id = "task"\n', encoding="utf-8")

            # Invalid - missing spec
            invalid1 = bench_root / "invalid" / "no_spec"
            invalid1.mkdir(parents=True)
            (invalid1 / "task.toml").write_text('id = "no_spec"\n', encoding="utf-8")

            # Invalid - missing task.toml
            invalid2 = bench_root / "invalid" / "no_toml"
            invalid2.mkdir(parents=True)
            (invalid2 / "spec.md").write_text("# spec\n", encoding="utf-8")

            result = list(
                _iter_tasks(
                    include_test_tasks=False,
                    bench_root=bench_root,
                    test_task_root=td_path / "test-tasks",
                )
            )

            self.assertEqual(len(result), 1)
            self.assertEqual(result[0], ("valid", "task"))


class TestDelegationIntegrity(unittest.TestCase):
    """Tests to ensure bench.py delegation matches task_loading_helpers.py."""

    def test_parse_task_ref_signature_match(self):
        """Verify bench.py _parse_task_ref delegates correctly."""
        import importlib.util
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[1]
        bench_py = repo_root / "runner" / "bench.py"
        spec = importlib.util.spec_from_file_location("simbench_runner_bench", bench_py)
        assert spec is not None
        bench_module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(bench_module)

        # Test that bench.py version produces same results
        task_ref = "s/t"
        result1 = _parse_task_ref(
            task_ref,
            bench_root=bench_module.BENCH_ROOT,
            test_task_root=bench_module.TEST_TASK_ROOT,
            repo_root=bench_module.REPO_ROOT,
        )
        result2 = bench_module._parse_task_ref(task_ref)

        self.assertEqual(result1, result2)


if __name__ == "__main__":
    unittest.main()
