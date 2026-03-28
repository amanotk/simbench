import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from tests.test_runner_helpers import bench


class TestBenchCheckCommand(unittest.TestCase):
    def test_check_passes_for_minimal_valid_task(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            task_dir = bench_root / "s" / "t"
            (task_dir / "workspace" / "tests").mkdir(parents=True)
            (task_dir / "eval").mkdir(parents=True)

            (task_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
            (task_dir / "task.toml").write_text(
                """
id = "t"
suite = "s"
language = "python"
time_limit_sec = 10
eval_cmd = "/eval/run.sh"
""".lstrip(),
                encoding="utf-8",
            )
            run_sh = task_dir / "eval" / "run.sh"
            run_sh.write_text(
                "#!/usr/bin/env bash\npython3 - <<'PY'\nopen('result.json','w').write('{}\\n')\nPY\n",
                encoding="utf-8",
            )
            os.chmod(run_sh, 0o755)

            with mock.patch.object(bench, "BENCH_ROOT", bench_root):
                out = StringIO()
                err = StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    rc = bench.main(["check", "s/t"])

            self.assertEqual(rc, 0)
            self.assertIn("[s/t] PASS", out.getvalue())

    def test_check_can_load_task_from_test_task_root(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            test_task_root = td_path / "test-tasks"
            task_dir = test_task_root / "smoke" / "py"
            (task_dir / "workspace" / "tests").mkdir(parents=True)
            (task_dir / "eval").mkdir(parents=True)

            (task_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
            (task_dir / "task.toml").write_text(
                """
id = "py"
suite = "smoke"
language = "python"
time_limit_sec = 10
eval_cmd = "/eval/run.sh"
""".lstrip(),
                encoding="utf-8",
            )
            run_sh = task_dir / "eval" / "run.sh"
            run_sh.write_text(
                "#!/usr/bin/env bash\npython3 - <<'PY'\nopen('result.json','w').write('{}\\n')\nPY\n",
                encoding="utf-8",
            )
            os.chmod(run_sh, 0o755)

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "TEST_TASK_ROOT", test_task_root),
            ):
                out = StringIO()
                err = StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    rc = bench.main(["check", "test:smoke/py"])

            self.assertEqual(rc, 0)
            self.assertIn("[smoke/py] PASS", out.getvalue())

    def test_check_rejects_ambiguous_task_reference(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            test_task_root = td_path / "test-tasks"

            for root in (bench_root, test_task_root):
                task_dir = root / "smoke" / "py"
                (task_dir / "workspace" / "tests").mkdir(parents=True)
                (task_dir / "eval").mkdir(parents=True)
                (task_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
                (task_dir / "task.toml").write_text(
                    """
id = "py"
suite = "smoke"
language = "python"
time_limit_sec = 10
eval_cmd = "/eval/run.sh"
""".lstrip(),
                    encoding="utf-8",
                )
                run_sh = task_dir / "eval" / "run.sh"
                run_sh.write_text(
                    "#!/usr/bin/env bash\npython3 - <<'PY'\nopen('result.json','w').write('{}\\n')\nPY\n",
                    encoding="utf-8",
                )
                os.chmod(run_sh, 0o755)

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "TEST_TASK_ROOT", test_task_root),
            ):
                out = StringIO()
                err = StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    rc = bench.main(["check", "smoke/py"])

            self.assertEqual(rc, 1)
            self.assertIn("ambiguous", out.getvalue())
            self.assertIn(
                "Use bench:<suite>/<task_id> or test:<suite>/<task_id>", out.getvalue()
            )

    def test_list_excludes_test_tasks_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            test_task_root = td_path / "test-tasks"

            benchmark_task = bench_root / "demo" / "py"
            benchmark_task.mkdir(parents=True)
            (benchmark_task / "spec.md").write_text("# benchmark\n", encoding="utf-8")
            (benchmark_task / "task.toml").write_text("id='py'\n", encoding="utf-8")

            smoke_task = test_task_root / "smoke" / "py"
            smoke_task.mkdir(parents=True)
            (smoke_task / "spec.md").write_text("# smoke\n", encoding="utf-8")
            (smoke_task / "task.toml").write_text("id='py'\n", encoding="utf-8")

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "TEST_TASK_ROOT", test_task_root),
            ):
                out = StringIO()
                err = StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    rc = bench.main(["list"])

            self.assertEqual(rc, 0)
            self.assertIn("demo/py", out.getvalue())
            self.assertNotIn("smoke/py", out.getvalue())

    def test_check_fails_for_missing_required_fields(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            task_dir = bench_root / "s" / "t"
            (task_dir / "workspace").mkdir(parents=True)
            (task_dir / "eval").mkdir(parents=True)

            (task_dir / "spec.md").write_text(
                "spec without heading\n", encoding="utf-8"
            )
            (task_dir / "task.toml").write_text(
                """
id = "wrong"
suite = "wrong"
language = "rust"
time_limit_sec = 0
eval_cmd = "/eval/run.sh"
""".lstrip(),
                encoding="utf-8",
            )

            with mock.patch.object(bench, "BENCH_ROOT", bench_root):
                out = StringIO()
                err = StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    rc = bench.main(["check", "s/t"])

            self.assertEqual(rc, 1)
            stdout_text = out.getvalue()
            self.assertIn("[s/t] FAIL", stdout_text)
            self.assertIn("task.toml id must match directory name", stdout_text)
            self.assertIn("task.toml suite must match directory name", stdout_text)
            self.assertIn("task.toml language must be one of", stdout_text)
            self.assertIn("time_limit_sec must be a positive integer", stdout_text)
            self.assertIn("eval/run.sh but eval/run.sh is missing", stdout_text)

    def test_check_reports_workspace_not_directory(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            task_dir = bench_root / "s" / "t"
            task_dir.mkdir(parents=True)
            (task_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
            (task_dir / "task.toml").write_text(
                """
id = "t"
suite = "s"
language = "python"
time_limit_sec = 10
eval_cmd = "/eval/run.sh"
""".lstrip(),
                encoding="utf-8",
            )
            (task_dir / "workspace").write_text("not a dir\n", encoding="utf-8")
            (task_dir / "eval").mkdir()

            with mock.patch.object(bench, "BENCH_ROOT", bench_root):
                out = StringIO()
                err = StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    rc = bench.main(["check", "s/t"])

            self.assertEqual(rc, 1)
            self.assertIn("[s/t] FAIL", out.getvalue())
            self.assertIn("workspace/ must be a directory", out.getvalue())

    def test_check_fails_when_opted_in_shared_dirs_missing(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            task_dir = bench_root / "s" / "t"
            (task_dir / "workspace").mkdir(parents=True)
            (task_dir / "eval").mkdir(parents=True)

            (task_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
            (task_dir / "task.toml").write_text(
                """
id = "t"
suite = "s"
language = "python"
time_limit_sec = 10
eval_cmd = "/eval/run.sh"
use_shared_workspace = true
use_shared_eval = true
""".lstrip(),
                encoding="utf-8",
            )

            with mock.patch.object(bench, "BENCH_ROOT", bench_root):
                out = StringIO()
                err = StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    rc = bench.main(["check", "s/t"])

            self.assertEqual(rc, 1)
            stdout_text = out.getvalue()
            self.assertIn("use_shared_workspace=true", stdout_text)
            self.assertIn("use_shared_eval=true", stdout_text)
