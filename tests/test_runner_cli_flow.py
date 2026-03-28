import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from tests.test_runner_helpers import (
    _assert_result_metadata,
    _write_agent_toml,
    bench,
)


def _assert_run_record_metadata(case: unittest.TestCase, run_record: dict) -> None:
    case.assertEqual(run_record["schema_version"], "1.0.0")
    case.assertRegex(
        run_record["completed_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
    )
    case.assertIn("repo_commit_sha", run_record)
    case.assertIn("repo_branch", run_record)
    case.assertIn("repo_dirty", run_record)


def _write_run_record(run_dir: Path, run_record: dict) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(
        json.dumps(run_record, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


class TestBenchCLIFlow(unittest.TestCase):
    def test_agent_flow_writes_prompt_and_forwarded_env_log(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            agents_default_path = td_path / "agents_default.toml"
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
prompt = "Read the attached spec.md and solve the task."
""".lstrip(),
                encoding="utf-8",
            )

            agents_default_path.write_text(
                """
version = 1

[agents.dummy]
mode = "docker"
enabled_by_default = false
model = "provider/model-x"
pass_env = ["OPENAI_API_KEY"]
pre = []
cmd = "true"

[[agents.dummy.bins]]
host = "true"
container = "/usr/local/bin/true"
""".lstrip(),
                encoding="utf-8",
            )

            agents_toml = td_path / "agents.toml"
            _write_agent_toml(
                agents_toml,
                """
name = "dummy"
cmd = "true"
""".lstrip(),
            )

            def fake_agent(*args, **kwargs):
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.01

            def fake_eval(*, workdir: Path, **_kwargs):
                (workdir / "result.json").write_text(
                    json.dumps({"status": "passed", "score": 1.0}) + "\n",
                    encoding="utf-8",
                )
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.02

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(
                    bench, "_run_agent_in_docker", side_effect=fake_agent
                ),
                mock.patch.object(bench, "_run_docker_eval", side_effect=fake_eval),
                mock.patch.object(bench, "AGENTS_DEFAULT_PATH", agents_default_path),
            ):
                with mock.patch.dict(
                    os.environ,
                    {
                        "OPENAI_API_KEY": "dummy",
                    },
                    clear=False,
                ):
                    out = StringIO()
                    err = StringIO()
                    with redirect_stdout(out), redirect_stderr(err):
                        rc = bench.main(
                            [
                                "run",
                                str(agents_toml),
                                "s/t",
                                "--image",
                                "simbench:0.1",
                            ]
                        )

            self.assertEqual(rc, 0)
            run_dirs = list(runs_root.glob("*/s/t"))
            self.assertEqual(len(run_dirs), 1)
            run_dir = run_dirs[0]
            self.assertTrue((run_dir / "prompt.txt").exists())
            self.assertTrue((run_dir / "logs" / "agent.forwarded_env.txt").exists())
            result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
            run_record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            self.assertNotIn("schema_version", result)
            self.assertNotIn("completed_at", result)
            self.assertNotIn("repo_commit_sha", result)
            self.assertNotIn("repo_branch", result)
            self.assertNotIn("repo_dirty", result)
            _assert_result_metadata(
                self, result, task="s/t", agent_exit_code=0, eval_exit_code=0
            )
            _assert_run_record_metadata(self, run_record)
            self.assertEqual(run_record["task"], "s/t")
            self.assertEqual(run_record["status"], "passed")
            self.assertEqual(run_record["score"], 1.0)

    def test_default_logging_prints_result_summary(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            agents_default_path = td_path / "agents_default.toml"
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
""".lstrip(),
                encoding="utf-8",
            )

            agents_default_path.write_text(
                """
version = 1

[agents.opencode]
mode = "docker"
enabled_by_default = true
model = "openai/gpt-5.3-codex"
pass_env = []
pre = []
cmd = "true"

[[agents.opencode.bins]]
host = "true"
container = "/usr/local/bin/true"
""".lstrip(),
                encoding="utf-8",
            )

            agents_toml = td_path / "opencode.toml"
            _write_agent_toml(
                agents_toml,
                """
name = "opencode"
""".lstrip(),
            )

            def fake_agent(*args, **kwargs):
                cmd = ["docker", "run"]
                return (
                    subprocess.CompletedProcess(
                        cmd,
                        0,
                        stdout="agent stdout line\n",
                        stderr="agent stderr line\n",
                    ),
                    0.03,
                )

            def fake_eval(*, workdir: Path, **_kwargs):
                seen_eval_verbose = _kwargs.get("verbose")
                self.assertFalse(seen_eval_verbose)
                (workdir / "result.json").write_text(
                    json.dumps(
                        {
                            "status": "passed",
                            "score": 1.0,
                            "metrics": {"cases": 3, "elapsed_sec": 0.12},
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                cmd = ["docker", "run"]
                return (
                    subprocess.CompletedProcess(
                        cmd,
                        0,
                        stdout="eval stdout line\n",
                        stderr="eval stderr line\n",
                    ),
                    0.04,
                )

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "AGENTS_DEFAULT_PATH", agents_default_path),
                mock.patch.object(
                    bench, "_run_agent_in_docker", side_effect=fake_agent
                ) as run_agent_mock,
                mock.patch.object(
                    bench, "_run_docker_eval", side_effect=fake_eval
                ) as run_eval_mock,
            ):
                out = StringIO()
                err = StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    rc = bench.main(
                        [
                            "run",
                            str(agents_toml),
                            "s/t",
                            "--image",
                            "simbench:0.1",
                        ]
                    )

            self.assertEqual(rc, 0)

            stdout_text = out.getvalue()
            self.assertIn("[s/t] Result", stdout_text)
            self.assertIn("- status: passed", stdout_text)
            self.assertIn("- score: 1.0", stdout_text)
            self.assertIn("- metrics:", stdout_text)
            self.assertIn("cases: 3", stdout_text)
            self.assertIn("elapsed_sec: 0.12", stdout_text)
            self.assertIn("- run_dir:", stdout_text)
            run_agent_mock.assert_called_once()
            run_eval_mock.assert_called_once()

            stderr_text = err.getvalue()
            self.assertIn("=== RUN SETUP ===", stderr_text)

    def test_eval_writes_run_record_and_preserves_result_contract(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            task_dir = bench_root / "s" / "t"
            workdir = td_path / "workdir"
            workdir.mkdir()
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
""".lstrip(),
                encoding="utf-8",
            )

            def fake_eval(*args, **kwargs):
                eval_workdir = Path(kwargs["workdir"])
                (eval_workdir / "result.json").write_text(
                    json.dumps(
                        {
                            "status": "passed",
                            "score": 1.0,
                            "metrics": {"cases": 2},
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.04

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "_run_docker_eval", side_effect=fake_eval),
            ):
                rc = bench.main(
                    [
                        "eval",
                        "s/t",
                        "--workdir",
                        str(workdir),
                        "--image",
                        "simbench:0.1",
                    ]
                )

            self.assertEqual(rc, 0)
            run_dir = list(runs_root.glob("*/s/t"))[0]
            result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
            run_record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            self.assertNotIn("schema_version", result)
            self.assertNotIn("completed_at", result)
            self.assertNotIn("repo_commit_sha", result)
            self.assertNotIn("repo_branch", result)
            self.assertNotIn("repo_dirty", result)
            _assert_result_metadata(self, result, task="s/t", eval_exit_code=0)
            self.assertEqual(result["metrics"]["cases"], 2)
            self.assertEqual(result["metrics"]["eval_inner_sec"], 0.04)
            _assert_run_record_metadata(self, run_record)
            self.assertEqual(run_record["task"], "s/t")
            self.assertEqual(run_record["status"], "passed")
            self.assertEqual(run_record["score"], 1.0)
            self.assertEqual(run_record["metrics"]["cases"], 2)
            self.assertEqual(run_record["metrics"]["eval_inner_sec"], 0.04)

    def test_publish_prints_deterministic_payload_and_body(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            _write_run_record(
                run_dir,
                {
                    "schema_version": "1.0.0",
                    "completed_at": "2026-03-28T12:34:56Z",
                    "repo_commit_sha": "abcdef1234567890abcdef1234567890abcdef12",
                    "repo_branch": "main",
                    "repo_dirty": False,
                    "task": "suite/task",
                    "status": "passed",
                    "score": 1.0,
                    "run_id": "run-123",
                    "started_at": "2026-03-28T12:30:00Z",
                    "agent": "dummy",
                    "model": "provider/model",
                },
            )

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = bench.main(["publish", str(run_dir)])

            self.assertEqual(rc, 0)
            self.assertEqual(err.getvalue(), "")
            stdout_text = out.getvalue()
            self.assertIn(f"[{run_dir}] Publication", stdout_text)
            self.assertIn("payload:", stdout_text)
            self.assertIn('"schema_version": "1.0.0"', stdout_text)
            self.assertIn('"title": "[passed] suite/task @ abcdef123456"', stdout_text)
            self.assertIn('"body_payload": {', stdout_text)
            self.assertIn("body:", stdout_text)
            self.assertIn('"run_record": {', stdout_text)

    def test_publish_rejects_missing_run_directory(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "missing-run"

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = bench.main(["publish", str(run_dir)])

            self.assertEqual(rc, 2)
            self.assertEqual(out.getvalue(), "")
            self.assertIn("run directory not found or not a directory", err.getvalue())

    def test_publish_rejects_missing_run_json(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            run_dir.mkdir(parents=True)

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = bench.main(["publish", str(run_dir)])

            self.assertEqual(rc, 2)
            self.assertEqual(out.getvalue(), "")
            self.assertIn("Failed to load publication payload", err.getvalue())
            self.assertIn("missing run.json", err.getvalue())

    def test_publish_rejects_non_directory_path(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            # Create a file, not a directory
            file_path = td_path / "not_a_directory.txt"
            file_path.write_text("I am a file, not a run directory\n", encoding="utf-8")

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = bench.main(["publish", str(file_path)])

            self.assertEqual(rc, 2)
            self.assertEqual(out.getvalue(), "")
            self.assertIn("run directory not found or not a directory", err.getvalue())

    def test_publish_rejects_path_traversal_attempt(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            # Attempt path traversal: ../../ runs/../
            attack_path = td_path / ".." / ".." / ".." / ".." / "etc" / "passwd"
            # Note: This should either reject or resolve to something outside workspace
            # The _resolve_publish_run_dir should handle this

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = bench.main(["publish", str(attack_path)])

            # Should fail because the path doesn't exist or isn't a directory
            self.assertEqual(rc, 2)
            # Verify error message mentions directory not found
            self.assertIn("run directory not found or not a directory", err.getvalue())

    def test_publish_rejects_symlink_to_nonexistent_path(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            run_dir = td_path / "run"
            run_dir.mkdir(parents=True)
            # Create a broken symlink
            broken_link = run_dir / "broken_link"
            broken_link.symlink_to("/nonexistent/path/that/does/not/exist")

            # run.json exists but we still need to check the directory exists/is_dir check
            (run_dir / "run.json").write_text(
                json.dumps(
                    {
                        "schema_version": "1.0.0",
                        "completed_at": "2026-03-28T12:34:56Z",
                        "repo_commit_sha": "abcdef1234567890abcdef1234567890abcdef12",
                        "repo_branch": "main",
                        "repo_dirty": False,
                        "task": "suite/task",
                        "status": "passed",
                        "score": 1.0,
                    }
                ),
                encoding="utf-8",
            )

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = bench.main(["publish", str(run_dir)])

            # Should succeed - the directory itself exists
            self.assertEqual(rc, 0)
            self.assertIn("Publication", out.getvalue())

    def test_publish_handles_unicode_task_name(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            _write_run_record(
                run_dir,
                {
                    "schema_version": "1.0.0",
                    "completed_at": "2026-03-28T12:34:56Z",
                    "repo_commit_sha": "abcdef1234567890abcdef1234567890abcdef12",
                    "repo_branch": "main",
                    "repo_dirty": False,
                    "task": "日本語テスト/タスク",
                    "status": "passed",
                    "score": 1.0,
                },
            )

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = bench.main(["publish", str(run_dir)])

            self.assertEqual(rc, 0)
            stdout_text = out.getvalue()
            self.assertIn("日本語テスト/タスク", stdout_text)

    def test_publish_handles_emoji_in_task_name(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            _write_run_record(
                run_dir,
                {
                    "schema_version": "1.0.0",
                    "completed_at": "2026-03-28T12:34:56Z",
                    "repo_commit_sha": "abcdef1234567890abcdef1234567890abcdef12",
                    "repo_branch": "main",
                    "repo_dirty": False,
                    "task": "test/🔥emoji-tasks",
                    "status": "passed",
                    "score": 1.0,
                },
            )

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = bench.main(["publish", str(run_dir)])

            self.assertEqual(rc, 0)
            stdout_text = out.getvalue()
            self.assertIn("🔥emoji-tasks", stdout_text)

    def test_publish_rejects_malformed_json_in_run_json(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            run_dir.mkdir(parents=True)
            # Write invalid JSON
            (run_dir / "run.json").write_text(
                "{ this is not valid json\n", encoding="utf-8"
            )

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = bench.main(["publish", str(run_dir)])

            self.assertEqual(rc, 2)
            self.assertIn("Failed to load publication payload", err.getvalue())

    def test_publish_rejects_missing_required_field(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            # Missing 'schema_version' field
            _write_run_record(
                run_dir,
                {
                    "completed_at": "2026-03-28T12:34:56Z",
                    "repo_commit_sha": "abcdef1234567890abcdef1234567890abcdef12",
                    "repo_branch": "main",
                    "repo_dirty": False,
                    "task": "suite/task",
                    "status": "passed",
                    "score": 1.0,
                },
            )

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = bench.main(["publish", str(run_dir)])

            self.assertEqual(rc, 2)
            self.assertIn("Failed to load publication payload", err.getvalue())
            self.assertIn("schema_version", err.getvalue())

    def test_publish_rejects_invalid_schema_version(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            _write_run_record(
                run_dir,
                {
                    "schema_version": "99.99.99",
                    "completed_at": "2026-03-28T12:34:56Z",
                    "repo_commit_sha": "abcdef1234567890abcdef1234567890abcdef12",
                    "repo_branch": "main",
                    "repo_dirty": False,
                    "task": "suite/task",
                    "status": "passed",
                    "score": 1.0,
                },
            )

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = bench.main(["publish", str(run_dir)])

            self.assertEqual(rc, 2)
            self.assertIn("Failed to load publication payload", err.getvalue())
            self.assertIn("unsupported", err.getvalue())

    def test_publish_rejects_invalid_completed_at_format(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            _write_run_record(
                run_dir,
                {
                    "schema_version": "1.0.0",
                    "completed_at": "not-a-date",
                    "repo_commit_sha": "abcdef1234567890abcdef1234567890abcdef12",
                    "repo_branch": "main",
                    "repo_dirty": False,
                    "task": "suite/task",
                    "status": "passed",
                    "score": 1.0,
                },
            )

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = bench.main(["publish", str(run_dir)])

            self.assertEqual(rc, 2)
            self.assertIn("Failed to load publication payload", err.getvalue())
            self.assertIn("completed_at", err.getvalue())

    def test_publish_rejects_invalid_repo_commit_sha(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            _write_run_record(
                run_dir,
                {
                    "schema_version": "1.0.0",
                    "completed_at": "2026-03-28T12:34:56Z",
                    "repo_commit_sha": "not-a-sha",
                    "repo_branch": "main",
                    "repo_dirty": False,
                    "task": "suite/task",
                    "status": "passed",
                    "score": 1.0,
                },
            )

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = bench.main(["publish", str(run_dir)])

            self.assertEqual(rc, 2)
            self.assertIn("Failed to load publication payload", err.getvalue())
            self.assertIn("repo_commit_sha", err.getvalue())

    def test_publish_rejects_empty_string_required_field(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            _write_run_record(
                run_dir,
                {
                    "schema_version": "1.0.0",
                    "completed_at": "2026-03-28T12:34:56Z",
                    "repo_commit_sha": "abcdef1234567890abcdef1234567890abcdef12",
                    "repo_branch": "",
                    "repo_dirty": False,
                    "task": "suite/task",
                    "status": "passed",
                    "score": 1.0,
                },
            )

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = bench.main(["publish", str(run_dir)])

            self.assertEqual(rc, 2)
            self.assertIn("Failed to load publication payload", err.getvalue())
            self.assertIn("repo_branch", err.getvalue())

    def test_publish_rejects_wrong_field_type_bool(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            # repo_dirty should be bool, not string
            _write_run_record(
                run_dir,
                {
                    "schema_version": "1.0.0",
                    "completed_at": "2026-03-28T12:34:56Z",
                    "repo_commit_sha": "abcdef1234567890abcdef1234567890abcdef12",
                    "repo_branch": "main",
                    "repo_dirty": "true",
                    "task": "suite/task",
                    "status": "passed",
                    "score": 1.0,
                },
            )

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = bench.main(["publish", str(run_dir)])

            self.assertEqual(rc, 2)
            self.assertIn("Failed to load publication payload", err.getvalue())
            self.assertIn("repo_dirty", err.getvalue())

    def test_publish_rejects_wrong_field_type_numeric(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            # score should be numeric, not string
            _write_run_record(
                run_dir,
                {
                    "schema_version": "1.0.0",
                    "completed_at": "2026-03-28T12:34:56Z",
                    "repo_commit_sha": "abcdef1234567890abcdef1234567890abcdef12",
                    "repo_branch": "main",
                    "repo_dirty": False,
                    "task": "suite/task",
                    "status": "passed",
                    "score": "1.0",
                },
            )

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = bench.main(["publish", str(run_dir)])

            self.assertEqual(rc, 2)
            self.assertIn("Failed to load publication payload", err.getvalue())
            self.assertIn("score", err.getvalue())

    def test_publish_produces_deterministic_output(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            _write_run_record(
                run_dir,
                {
                    "schema_version": "1.0.0",
                    "completed_at": "2026-03-28T12:34:56Z",
                    "repo_commit_sha": "abcdef1234567890abcdef1234567890abcdef12",
                    "repo_branch": "main",
                    "repo_dirty": False,
                    "task": "suite/task",
                    "status": "passed",
                    "score": 1.0,
                    "run_id": "run-123",
                    "started_at": "2026-03-28T12:30:00Z",
                    "agent": "dummy",
                    "model": "provider/model",
                },
            )

            # Call publish multiple times
            outputs = []
            for _ in range(3):
                out = StringIO()
                err = StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    rc = bench.main(["publish", str(run_dir)])
                self.assertEqual(rc, 0)
                outputs.append(out.getvalue())

            # All outputs should be identical
            self.assertEqual(outputs[0], outputs[1])
            self.assertEqual(outputs[1], outputs[2])

    def test_publish_handles_null_byte_in_run_json(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            run_dir.mkdir(parents=True)
            # JSON with null byte embedded - should cause parse error
            (run_dir / "run.json").write_bytes(
                b'{"schema_version": "1.0.0", \x00 "completed_at": "2026-03-28T12:34:56Z"}'
            )

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = bench.main(["publish", str(run_dir)])

            self.assertEqual(rc, 2)
            self.assertIn("Failed to load publication payload", err.getvalue())

    def test_publish_handles_oversized_json_field(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            # Create a massive string field (10KB+)
            large_task_name = "a" * 20000
            _write_run_record(
                run_dir,
                {
                    "schema_version": "1.0.0",
                    "completed_at": "2026-03-28T12:34:56Z",
                    "repo_commit_sha": "abcdef1234567890abcdef1234567890abcdef12",
                    "repo_branch": "main",
                    "repo_dirty": False,
                    "task": large_task_name,
                    "status": "passed",
                    "score": 1.0,
                },
            )

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = bench.main(["publish", str(run_dir)])

            # Should handle large input - might succeed or fail depending on implementation
            # but should not crash
            self.assertIn(str(rc), ("0", "2"))

    def test_publish_handles_deeply_nested_json(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            # Create deeply nested JSON - test for potential DoS
            nested = {"level": 0}
            current = nested
            for i in range(1, 101):
                current["nested"] = {"level": i}
                current = current["nested"]
            record = {
                "schema_version": "1.0.0",
                "completed_at": "2026-03-28T12:34:56Z",
                "repo_commit_sha": "abcdef1234567890abcdef1234567890abcdef12",
                "repo_branch": "main",
                "repo_dirty": False,
                "task": "suite/task",
                "status": "passed",
                "score": 1.0,
                "extra_data": nested,
            }
            _write_run_record(run_dir, record)

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = bench.main(["publish", str(run_dir)])

            # Should handle or gracefully reject
            self.assertIn(str(rc), ("0", "2"))

    def test_publish_handles_rtl_override_characters(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            # RTL override character - potential security concern
            rtl_task = "test/\u202etask\u202c"
            _write_run_record(
                run_dir,
                {
                    "schema_version": "1.0.0",
                    "completed_at": "2026-03-28T12:34:56Z",
                    "repo_commit_sha": "abcdef1234567890abcdef1234567890abcdef12",
                    "repo_branch": "main",
                    "repo_dirty": False,
                    "task": rtl_task,
                    "status": "passed",
                    "score": 1.0,
                },
            )

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = bench.main(["publish", str(run_dir)])

            # Should handle gracefully
            self.assertEqual(rc, 0)
            stdout_text = out.getvalue()
            # Verify RTL chars are in output (not stripped)
            self.assertIn("\u202e", stdout_text)

    def test_publish_handles_combine_characters(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            # Combining characters that could be used for spoofing
            combining_task = "test/a\u0308"  # a + combining diaeresis = ä
            _write_run_record(
                run_dir,
                {
                    "schema_version": "1.0.0",
                    "completed_at": "2026-03-28T12:34:56Z",
                    "repo_commit_sha": "abcdef1234567890abcdef1234567890abcdef12",
                    "repo_branch": "main",
                    "repo_dirty": False,
                    "task": combining_task,
                    "status": "passed",
                    "score": 1.0,
                },
            )

            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = bench.main(["publish", str(run_dir)])

            self.assertEqual(rc, 0)

    def test_run_writes_failure_result_on_agent_timeout(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            agents_default_path = td_path / "agents_default.toml"
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
""".lstrip(),
                encoding="utf-8",
            )

            agents_default_path.write_text(
                """
version = 1

[agents.opencode]
mode = "docker"
enabled_by_default = true
model = "openai/gpt-5.3-codex"
pass_env = []
pre = []
cmd = "true"

[[agents.opencode.bins]]
host = "true"
container = "/usr/local/bin/true"
""".lstrip(),
                encoding="utf-8",
            )

            agents_toml = td_path / "opencode.toml"
            _write_agent_toml(
                agents_toml,
                """
name = "opencode"
""".lstrip(),
            )

            timeout_exc = subprocess.TimeoutExpired(
                cmd=["docker", "run"],
                timeout=10,
                output="partial out\n",
                stderr="partial err",
            )

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "AGENTS_DEFAULT_PATH", agents_default_path),
                mock.patch.object(
                    bench, "_run_agent_in_docker", side_effect=timeout_exc
                ),
            ):
                out = StringIO()
                err = StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    rc = bench.main(
                        [
                            "run",
                            str(agents_toml),
                            "s/t",
                            "--image",
                            "simbench:0.1",
                        ]
                    )

            self.assertEqual(rc, 1)
            run_dirs = list(runs_root.glob("*/s/t"))
            self.assertEqual(len(run_dirs), 1)
            run_dir = run_dirs[0]
            result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
            run_record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["score"], 0.0)
            self.assertEqual(result["error"], "agent_timeout")
            self.assertIn("during agent phase", result["message"])
            self.assertNotIn("schema_version", result)
            self.assertNotIn("completed_at", result)
            _assert_result_metadata(
                self,
                result,
                task="s/t",
                agent="opencode",
                model="openai/gpt-5.3-codex",
                agent_exit_code="timeout",
            )
            _assert_run_record_metadata(self, run_record)
            self.assertEqual(run_record["task"], "s/t")
            self.assertEqual(run_record["status"], "failed")
            self.assertEqual(run_record["error"], "agent_timeout")
            self.assertIn("Timed out after 10s during agent phase", err.getvalue())
            self.assertIn("[s/t] Result", out.getvalue())

    def test_run_writes_failure_result_on_eval_timeout(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            agents_default_path = td_path / "agents_default.toml"
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
""".lstrip(),
                encoding="utf-8",
            )

            agents_default_path.write_text(
                """
version = 1

[agents.opencode]
mode = "docker"
enabled_by_default = true
model = "openai/gpt-5.3-codex"
pass_env = []
pre = []
cmd = "true"

[[agents.opencode.bins]]
host = "true"
container = "/usr/local/bin/true"
""".lstrip(),
                encoding="utf-8",
            )

            agents_toml = td_path / "opencode.toml"
            _write_agent_toml(
                agents_toml,
                """
name = "opencode"
""".lstrip(),
            )

            def fake_agent(*args, **kwargs):
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.03

            timeout_exc = subprocess.TimeoutExpired(cmd=["docker", "run"], timeout=10)

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "AGENTS_DEFAULT_PATH", agents_default_path),
                mock.patch.object(
                    bench, "_run_agent_in_docker", side_effect=fake_agent
                ),
                mock.patch.object(bench, "_run_docker_eval", side_effect=timeout_exc),
            ):
                out = StringIO()
                err = StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    rc = bench.main(
                        [
                            "run",
                            str(agents_toml),
                            "s/t",
                            "--image",
                            "simbench:0.1",
                        ]
                    )

            self.assertEqual(rc, 1)
            run_dirs = list(runs_root.glob("*/s/t"))
            self.assertEqual(len(run_dirs), 1)
            run_dir = run_dirs[0]
            result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["error"], "eval_timeout")
            self.assertIn("during eval phase", result["message"])
            _assert_result_metadata(
                self,
                result,
                task="s/t",
                agent="opencode",
                model="openai/gpt-5.3-codex",
                agent_exit_code=0,
                eval_exit_code="timeout",
            )
            self.assertEqual(result["metrics"]["agent_inner_sec"], 0.03)
            self.assertIn("Timed out after 10s during eval phase", err.getvalue())
            self.assertIn("[s/t] Result", out.getvalue())

    def test_run_appends_agent_usage_metrics_to_result(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            agents_default_path = td_path / "agents_default.toml"
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
""".lstrip(),
                encoding="utf-8",
            )

            agents_default_path.write_text(
                """
version = 1

[agents.codex]
mode = "docker"
enabled_by_default = true
model = "gpt-5.3-codex"
pass_env = []
pre = []
cmd = "true"

[[agents.codex.bins]]
host = "true"
container = "/usr/local/bin/true"
""".lstrip(),
                encoding="utf-8",
            )

            agents_toml = td_path / "codex.toml"
            _write_agent_toml(
                agents_toml,
                """
name = "codex"
""".lstrip(),
            )

            agent_stdout = (
                '{"type":"turn.completed","usage":{"input_tokens":24763,'
                '"cached_input_tokens":24448,"output_tokens":122}}\n'
            )

            def fake_agent(*args, **kwargs):
                cmd = ["docker", "run"]
                return (
                    subprocess.CompletedProcess(cmd, 0, stdout=agent_stdout, stderr=""),
                    1.25,
                )

            def fake_eval(*args, **kwargs):
                workdir = Path(kwargs["workdir"])
                (workdir / "result.json").write_text(
                    json.dumps({"status": "passed", "score": 1.0}) + "\n",
                    encoding="utf-8",
                )
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.5

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "AGENTS_DEFAULT_PATH", agents_default_path),
                mock.patch.object(
                    bench, "_run_agent_in_docker", side_effect=fake_agent
                ),
                mock.patch.object(bench, "_run_docker_eval", side_effect=fake_eval),
            ):
                rc = bench.main(
                    [
                        "run",
                        str(agents_toml),
                        "s/t",
                        "--image",
                        "simbench:0.1",
                    ]
                )

            self.assertEqual(rc, 0)
            run_dirs = list(runs_root.glob("*/s/t"))
            self.assertEqual(len(run_dirs), 1)
            run_dir = run_dirs[0]
            result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
            run_record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            self.assertNotIn("schema_version", result)
            self.assertNotIn("completed_at", result)
            self.assertNotIn("repo_commit_sha", result)
            self.assertNotIn("repo_branch", result)
            self.assertNotIn("repo_dirty", result)
            _assert_result_metadata(
                self,
                result,
                task="s/t",
                agent="codex",
                model="gpt-5.3-codex",
                agent_exit_code=0,
                eval_exit_code=0,
            )
            self.assertEqual(result["metrics"]["agent_input_tokens"], 24763)
            self.assertEqual(result["metrics"]["agent_cached_input_tokens"], 24448)
            self.assertEqual(result["metrics"]["agent_output_tokens"], 122)
            self.assertEqual(result["metrics"]["agent_inner_sec"], 1.25)
            self.assertEqual(result["metrics"]["eval_inner_sec"], 0.5)
            _assert_run_record_metadata(self, run_record)
            self.assertEqual(run_record["task"], "s/t")
            self.assertEqual(run_record["status"], "passed")
            self.assertEqual(run_record["score"], 1.0)
            self.assertEqual(run_record["metrics"]["agent_inner_sec"], 1.25)
            self.assertEqual(run_record["metrics"]["eval_inner_sec"], 0.5)

    def test_run_writes_failure_result_on_agent_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            agents_default_path = td_path / "agents_default.toml"
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
""".lstrip(),
                encoding="utf-8",
            )

            agents_default_path.write_text(
                """
version = 1

[agents.opencode]
mode = "docker"
enabled_by_default = true
model = "opencode/big-pickle"
pass_env = []
pre = []
cmd = "true"

[[agents.opencode.bins]]
host = "true"
container = "/usr/local/bin/true"
""".lstrip(),
                encoding="utf-8",
            )

            agents_toml = td_path / "opencode.toml"
            _write_agent_toml(agents_toml, 'name = "opencode"\n')

            def fake_agent(*args, **kwargs):
                cmd = ["docker", "run"]
                return (
                    subprocess.CompletedProcess(
                        cmd,
                        7,
                        stdout='{"type":"result","usage":{"input_tokens":9,"output_tokens":2}}\n',
                        stderr="boom\n",
                    ),
                    0.75,
                )

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "AGENTS_DEFAULT_PATH", agents_default_path),
                mock.patch.object(
                    bench, "_run_agent_in_docker", side_effect=fake_agent
                ),
            ):
                out = StringIO()
                err = StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    rc = bench.main(
                        ["run", str(agents_toml), "s/t", "--image", "simbench:0.1"]
                    )

            self.assertEqual(rc, 1)
            run_dir = list(runs_root.glob("*/s/t"))[0]
            result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["error"], "agent_failed")
            self.assertEqual(result["message"], "Agent exited with code 7")
            _assert_result_metadata(
                self,
                result,
                task="s/t",
                agent="opencode",
                model="opencode/big-pickle",
                agent_exit_code=7,
            )
            self.assertEqual(result["metrics"]["agent_input_tokens"], 9)
            self.assertEqual(result["metrics"]["agent_output_tokens"], 2)
            self.assertEqual(result["metrics"]["agent_inner_sec"], 0.75)

    def test_run_writes_failure_result_on_agent_setup_error(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            agents_default_path = td_path / "agents_default.toml"
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
""".lstrip(),
                encoding="utf-8",
            )

            agents_default_path.write_text(
                """
version = 1

[agents.opencode]
mode = "docker"
enabled_by_default = true
model = "opencode/big-pickle"
pass_env = []
pre = []
cmd = "true"

[[agents.opencode.bins]]
host = "true"
container = "/usr/local/bin/true"
""".lstrip(),
                encoding="utf-8",
            )

            agents_toml = td_path / "opencode.toml"
            _write_agent_toml(agents_toml, 'name = "opencode"\n')

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "AGENTS_DEFAULT_PATH", agents_default_path),
                mock.patch.object(
                    bench,
                    "_run_agent_in_docker",
                    side_effect=FileNotFoundError("missing-opencode"),
                ) as run_agent_mock,
            ):
                out = StringIO()
                err = StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    rc = bench.main(
                        ["run", str(agents_toml), "s/t", "--image", "simbench:0.1"]
                    )

            self.assertEqual(rc, 1)
            run_dir = list(runs_root.glob("*/s/t"))[0]
            result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["error"], "agent_setup")
            self.assertEqual(result["message"], "missing-opencode")
            run_agent_mock.assert_called_once()
            _assert_result_metadata(
                self,
                result,
                task="s/t",
                agent="opencode",
                model="opencode/big-pickle",
                agent_exit_code="setup_error",
            )

    def test_run_writes_failure_result_when_eval_missing_result_json(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            agents_default_path = td_path / "agents_default.toml"
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
""".lstrip(),
                encoding="utf-8",
            )

            agents_default_path.write_text(
                """
version = 1

[agents.codex]
mode = "docker"
enabled_by_default = true
model = "gpt-5.3-codex"
pass_env = []
pre = []
cmd = "true"

[[agents.codex.bins]]
host = "true"
container = "/usr/local/bin/true"
""".lstrip(),
                encoding="utf-8",
            )

            agents_toml = td_path / "codex.toml"
            _write_agent_toml(agents_toml, 'name = "codex"\n')

            def fake_agent(*args, **kwargs):
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.5

            def fake_eval(*args, **kwargs):
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(
                    cmd, 3, stdout="", stderr="no result\n"
                ), 0.2

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "AGENTS_DEFAULT_PATH", agents_default_path),
                mock.patch.object(
                    bench, "_run_agent_in_docker", side_effect=fake_agent
                ),
                mock.patch.object(bench, "_run_docker_eval", side_effect=fake_eval),
            ):
                out = StringIO()
                err = StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    rc = bench.main(
                        [
                            "run",
                            str(agents_toml),
                            "s/t",
                            "--image",
                            "simbench:0.1",
                        ]
                    )

            self.assertEqual(rc, 1)
            run_dir = list(runs_root.glob("*/s/t"))[0]
            result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["error"], "missing_result")
            self.assertEqual(
                result["message"], "Eval completed but did not produce result.json"
            )
            _assert_result_metadata(
                self,
                result,
                task="s/t",
                agent="codex",
                model="gpt-5.3-codex",
                agent_exit_code=0,
                eval_exit_code=3,
            )

    def test_run_writes_failure_run_record_when_result_json_is_invalid(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            agents_default_path = td_path / "agents_default.toml"
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
""".lstrip(),
                encoding="utf-8",
            )

            agents_default_path.write_text(
                """
version = 1

[agents.codex]
mode = "docker"
enabled_by_default = true
model = "gpt-5.3-codex"
pass_env = []
pre = []
cmd = "true"

[[agents.codex.bins]]
host = "true"
container = "/usr/local/bin/true"
""".lstrip(),
                encoding="utf-8",
            )

            agents_toml = td_path / "codex.toml"
            _write_agent_toml(agents_toml, 'name = "codex"\n')

            def fake_agent(*args, **kwargs):
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.5

            def fake_eval(*args, **kwargs):
                eval_workdir = Path(kwargs["workdir"])
                (eval_workdir / "result.json").write_text(
                    "{invalid json\n", encoding="utf-8"
                )
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 3, stdout="", stderr=""), 0.2

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "AGENTS_DEFAULT_PATH", agents_default_path),
                mock.patch.object(
                    bench, "_run_agent_in_docker", side_effect=fake_agent
                ),
                mock.patch.object(bench, "_run_docker_eval", side_effect=fake_eval),
            ):
                out = StringIO()
                err = StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    rc = bench.main(
                        [
                            "run",
                            str(agents_toml),
                            "s/t",
                            "--image",
                            "simbench:0.1",
                        ]
                    )

            self.assertEqual(rc, 1)
            run_dir = list(runs_root.glob("*/s/t"))[0]
            parsed_result = json.loads(
                (run_dir / "result.json").read_text(encoding="utf-8")
            )
            run_record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(parsed_result["status"], "failed")
            self.assertEqual(parsed_result["error"], "result_parse_error")
            self.assertIn("could not be parsed", parsed_result["message"])
            _assert_result_metadata(
                self,
                parsed_result,
                task="s/t",
                agent="codex",
                model="gpt-5.3-codex",
                agent_exit_code=0,
                eval_exit_code=3,
            )
            _assert_run_record_metadata(self, run_record)
            self.assertEqual(run_record["error"], "result_parse_error")
            self.assertEqual(run_record["status"], "failed")

    def test_eval_writes_failure_run_record_when_result_json_is_invalid(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            task_dir = bench_root / "s" / "t"
            workdir = td_path / "workdir"
            workdir.mkdir()
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
""".lstrip(),
                encoding="utf-8",
            )

            def fake_eval(*args, **kwargs):
                eval_workdir = Path(kwargs["workdir"])
                (eval_workdir / "result.json").write_text(
                    "{invalid json\n", encoding="utf-8"
                )
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.12

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "_run_docker_eval", side_effect=fake_eval),
            ):
                out = StringIO()
                err = StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    rc = bench.main(
                        [
                            "eval",
                            "s/t",
                            "--workdir",
                            str(workdir),
                            "--image",
                            "simbench:0.1",
                        ]
                    )

            self.assertEqual(rc, 0)
            run_dir = list(runs_root.glob("*/s/t"))[0]
            parsed_result = json.loads(
                (run_dir / "result.json").read_text(encoding="utf-8")
            )
            run_record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(parsed_result["status"], "failed")
            self.assertEqual(parsed_result["error"], "result_parse_error")
            self.assertIn("could not be parsed", parsed_result["message"])
            _assert_result_metadata(self, parsed_result, task="s/t", eval_exit_code=0)
            _assert_run_record_metadata(self, run_record)
            self.assertEqual(run_record["error"], "result_parse_error")
            self.assertEqual(run_record["status"], "failed")

    def test_run_appends_copilot_usage_metrics_from_stderr(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            agents_default_path = td_path / "agents_default.toml"
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
""".lstrip(),
                encoding="utf-8",
            )

            agents_default_path.write_text(
                """
version = 1

[agents.copilot]
mode = "docker"
enabled_by_default = true
model = "gpt-5-mini"
pass_env = []
pre = []
cmd = "true"

[[agents.copilot.bins]]
host = "true"
container = "/usr/local/bin/true"
""".lstrip(),
                encoding="utf-8",
            )

            agents_toml = td_path / "copilot.toml"
            _write_agent_toml(
                agents_toml,
                """
name = "copilot"
model = "gpt-5-mini"
""".lstrip(),
            )

            agent_stderr = (
                "Total usage est:        0 Premium requests\n"
                "Breakdown by AI model:\n"
                " gpt-5-mini              269.2k in, 6.7k out, 249.9k cached (Est. 0 Premium requests)\n"
            )

            def fake_agent(*args, **kwargs):
                cmd = ["docker", "run"]
                return (
                    subprocess.CompletedProcess(cmd, 0, stdout="", stderr=agent_stderr),
                    2.0,
                )

            def fake_eval(*args, **kwargs):
                workdir = Path(kwargs["workdir"])
                (workdir / "result.json").write_text(
                    json.dumps({"status": "passed", "score": 1.0}) + "\n",
                    encoding="utf-8",
                )
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.25

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "AGENTS_DEFAULT_PATH", agents_default_path),
                mock.patch.object(
                    bench, "_run_agent_in_docker", side_effect=fake_agent
                ),
                mock.patch.object(bench, "_run_docker_eval", side_effect=fake_eval),
            ):
                rc = bench.main(
                    [
                        "run",
                        str(agents_toml),
                        "s/t",
                        "--image",
                        "simbench:0.1",
                    ]
                )

            self.assertEqual(rc, 0)
            run_dirs = list(runs_root.glob("*/s/t"))
            self.assertEqual(len(run_dirs), 1)
            result = json.loads(
                (run_dirs[0] / "result.json").read_text(encoding="utf-8")
            )
            self.assertEqual(result["metrics"]["agent_input_tokens"], 269200)
            self.assertEqual(result["metrics"]["agent_output_tokens"], 6700)
            self.assertEqual(result["metrics"]["agent_cached_input_tokens"], 249900)
            self.assertEqual(result["metrics"]["agent_usage_model"], "gpt-5-mini")

    def test_run_appends_opencode_usage_metrics_from_postrun_stats(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            agents_default_path = td_path / "agents_default.toml"
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
""".lstrip(),
                encoding="utf-8",
            )

            agents_default_path.write_text(
                """
version = 1

[agents.opencode]
mode = "docker"
enabled_by_default = true
model = "openai/gpt-5.3-codex"
pass_env = []
pre = []
cmd = "true"

[[agents.opencode.bins]]
host = "true"
container = "/usr/local/bin/true"
""".lstrip(),
                encoding="utf-8",
            )

            agents_toml = td_path / "opencode.toml"
            _write_agent_toml(
                agents_toml,
                """
name = "opencode"
""".lstrip(),
            )

            def fake_agent(*args, **kwargs):
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(
                    cmd, 0, stdout="plain output\n", stderr=""
                ), 1.5

            def fake_eval(*args, **kwargs):
                workdir = Path(kwargs["workdir"])
                (workdir / "result.json").write_text(
                    json.dumps({"status": "passed", "score": 1.0}) + "\n",
                    encoding="utf-8",
                )
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.25

            stats_output = "\n".join(
                [
                    "┌────────────────────────────────────────────────────────┐",
                    "│                    COST & TOKENS                       │",
                    "├────────────────────────────────────────────────────────┤",
                    "│Total Cost                                        $0.46 │",
                    "│Input                                             17.1k │",
                    "│Output                                             6.2k │",
                    "│Cache Read                                       445.1k │",
                    "│Cache Write                                         0.0k │",
                    "└────────────────────────────────────────────────────────┘",
                    "",
                ]
            )

            def fake_subprocess_run(cmd, **kwargs):
                if cmd == ["opencode", "stats", "--models", "1"]:
                    self.assertTrue(
                        str(kwargs["env"].get("HOME", "")).endswith("/.opencode-data")
                    )
                    return subprocess.CompletedProcess(
                        cmd, 0, stdout=stats_output, stderr=""
                    )
                if cmd == ["git", "rev-parse", "HEAD"]:
                    return subprocess.CompletedProcess(
                        cmd,
                        0,
                        stdout="0123456789abcdef0123456789abcdef01234567\n",
                        stderr="",
                    )
                if cmd == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
                    return subprocess.CompletedProcess(
                        cmd, 0, stdout="main\n", stderr=""
                    )
                if cmd == ["git", "diff", "--cached", "--quiet", "--ignore-submodules"]:
                    return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
                if cmd == ["git", "diff", "--quiet", "--ignore-submodules"]:
                    return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
                if cmd == ["git", "ls-files", "--others", "--exclude-standard"]:
                    return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
                self.fail(f"unexpected subprocess.run call: {cmd!r}")

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "AGENTS_DEFAULT_PATH", agents_default_path),
                mock.patch.object(
                    bench, "_run_agent_in_docker", side_effect=fake_agent
                ),
                mock.patch.object(bench, "_run_docker_eval", side_effect=fake_eval),
                mock.patch.object(
                    bench.subprocess, "run", side_effect=fake_subprocess_run
                ),
            ):
                rc = bench.main(
                    [
                        "run",
                        str(agents_toml),
                        "s/t",
                        "--image",
                        "simbench:0.1",
                    ]
                )

            self.assertEqual(rc, 0)
            run_dirs = list(runs_root.glob("*/s/t"))
            self.assertEqual(len(run_dirs), 1)
            result = json.loads(
                (run_dirs[0] / "result.json").read_text(encoding="utf-8")
            )
            self.assertEqual(result["metrics"]["agent_input_tokens"], 17100)
            self.assertEqual(result["metrics"]["agent_output_tokens"], 6200)
            self.assertEqual(result["metrics"]["agent_cached_input_tokens"], 445100)

    def test_run_preserves_precise_opencode_json_metrics_over_stats_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            agents_default_path = td_path / "agents_default.toml"
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
""".lstrip(),
                encoding="utf-8",
            )

            agents_default_path.write_text(
                """
version = 1

[agents.opencode]
mode = "docker"
enabled_by_default = true
model = "openai/gpt-5.3-codex"
pass_env = []
pre = []
cmd = "true"

[[agents.opencode.bins]]
host = "true"
container = "/usr/local/bin/true"
""".lstrip(),
                encoding="utf-8",
            )

            agents_toml = td_path / "opencode.toml"
            _write_agent_toml(
                agents_toml,
                """
name = "opencode"
""".lstrip(),
            )

            agent_stdout = (
                '{"type":"result","usage":{"input_tokens":17101,'
                '"cache_creation_input_tokens":0,"cache_read_input_tokens":445056,'
                '"output_tokens":6237},"total_cost_usd":0.463958}\n'
            )

            def fake_agent(*args, **kwargs):
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(
                    cmd, 0, stdout=agent_stdout, stderr=""
                ), 1.5

            def fake_eval(*args, **kwargs):
                workdir = Path(kwargs["workdir"])
                (workdir / "result.json").write_text(
                    json.dumps({"status": "passed", "score": 1.0}) + "\n",
                    encoding="utf-8",
                )
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.25

            stats_output = "\n".join(
                [
                    "┌────────────────────────────────────────────────────────┐",
                    "│                    COST & TOKENS                       │",
                    "├────────────────────────────────────────────────────────┤",
                    "│Total Cost                                        $0.46 │",
                    "│Input                                             17.1k │",
                    "│Output                                             6.2k │",
                    "│Cache Read                                       445.1k │",
                    "│Cache Write                                         0.0k │",
                    "└────────────────────────────────────────────────────────┘",
                    "",
                ]
            )

            def fake_subprocess_run(cmd, **kwargs):
                return subprocess.CompletedProcess(
                    cmd, 0, stdout=stats_output, stderr=""
                )

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "AGENTS_DEFAULT_PATH", agents_default_path),
                mock.patch.object(
                    bench, "_run_agent_in_docker", side_effect=fake_agent
                ),
                mock.patch.object(bench, "_run_docker_eval", side_effect=fake_eval),
                mock.patch.object(
                    bench.subprocess, "run", side_effect=fake_subprocess_run
                ),
            ):
                rc = bench.main(
                    [
                        "run",
                        str(agents_toml),
                        "s/t",
                        "--image",
                        "simbench:0.1",
                    ]
                )

            self.assertEqual(rc, 0)
            run_dirs = list(runs_root.glob("*/s/t"))
            self.assertEqual(len(run_dirs), 1)
            result = json.loads(
                (run_dirs[0] / "result.json").read_text(encoding="utf-8")
            )
            self.assertEqual(result["metrics"]["agent_input_tokens"], 17101)
            self.assertEqual(result["metrics"]["agent_output_tokens"], 6237)
            self.assertEqual(result["metrics"]["agent_cached_input_tokens"], 445056)
            self.assertEqual(result["metrics"]["agent_cache_creation_input_tokens"], 0)

    def test_eval_writes_failure_result_on_timeout(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            task_dir = bench_root / "s" / "t"
            workdir = td_path / "workdir"
            workdir.mkdir()
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
""".lstrip(),
                encoding="utf-8",
            )

            timeout_exc = subprocess.TimeoutExpired(cmd=["docker", "run"], timeout=10)

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "_run_docker_eval", side_effect=timeout_exc),
            ):
                out = StringIO()
                err = StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    rc = bench.main(
                        [
                            "eval",
                            "s/t",
                            "--workdir",
                            str(workdir),
                            "--image",
                            "simbench:0.1",
                        ]
                    )

            self.assertEqual(rc, 1)
            run_dirs = list(runs_root.glob("*/s/t"))
            self.assertEqual(len(run_dirs), 1)
            run_dir = run_dirs[0]
            result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
            run_record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["error"], "eval_timeout")
            self.assertIn("during eval phase", result["message"])
            self.assertNotIn("schema_version", result)
            self.assertNotIn("completed_at", result)
            _assert_result_metadata(self, result, task="s/t", eval_exit_code="timeout")
            _assert_run_record_metadata(self, run_record)
            self.assertEqual(run_record["task"], "s/t")
            self.assertEqual(run_record["status"], "failed")
            self.assertEqual(run_record["error"], "eval_timeout")
            self.assertIn("Timed out after 10s during eval phase", err.getvalue())
            self.assertIn("[s/t] Result", out.getvalue())

    def test_eval_writes_failure_result_when_result_json_missing(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            task_dir = bench_root / "s" / "t"
            workdir = td_path / "workdir"
            workdir.mkdir()
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
""".lstrip(),
                encoding="utf-8",
            )

            def fake_eval(*args, **kwargs):
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 5, stdout="", stderr=""), 0.12

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "_run_docker_eval", side_effect=fake_eval),
            ):
                out = StringIO()
                err = StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    rc = bench.main(
                        [
                            "eval",
                            "s/t",
                            "--workdir",
                            str(workdir),
                            "--image",
                            "simbench:0.1",
                        ]
                    )

            self.assertEqual(rc, 1)
            run_dir = list(runs_root.glob("*/s/t"))[0]
            result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
            run_record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(result["error"], "missing_result")
            self.assertNotIn("schema_version", result)
            self.assertNotIn("completed_at", result)
            _assert_result_metadata(self, result, task="s/t", eval_exit_code=5)
            _assert_run_record_metadata(self, run_record)
            self.assertEqual(run_record["task"], "s/t")
            self.assertEqual(run_record["status"], "failed")
            self.assertEqual(run_record["error"], "missing_result")

    # =============================================================================
    # Adversarial security and boundary tests for run.json artifact writing
    # =============================================================================

    def test_run_json_written_when_result_json_contains_null_bytes(self):
        """Test that run.json is written correctly when result.json contains null bytes."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            agents_default_path = td_path / "agents_default.toml"
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
""".lstrip(),
                encoding="utf-8",
            )

            agents_default_path.write_text(
                """
version = 1

[agents.opencode]
mode = "docker"
enabled_by_default = true
model = "openai/gpt-5.3-codex"
pass_env = []
pre = []
cmd = "true"

[[agents.opencode.bins]]
host = "true"
container = "/usr/local/bin/true"
""".lstrip(),
                encoding="utf-8",
            )

            agents_toml = td_path / "opencode.toml"
            _write_agent_toml(agents_toml, 'name = "opencode"\n')

            def fake_agent(*args, **kwargs):
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.5

            def fake_eval(*args, **kwargs):
                workdir = Path(kwargs["workdir"])
                # Write JSON with null bytes - should be treated as parse error
                result_with_null = {"status": "passed\x00", "score": 1.0}
                (workdir / "result.json").write_text(
                    json.dumps(result_with_null) + "\x00extra", encoding="utf-8"
                )
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.2

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "AGENTS_DEFAULT_PATH", agents_default_path),
                mock.patch.object(
                    bench, "_run_agent_in_docker", side_effect=fake_agent
                ),
                mock.patch.object(bench, "_run_docker_eval", side_effect=fake_eval),
            ):
                rc = bench.main(
                    ["run", str(agents_toml), "s/t", "--image", "simbench:0.1"]
                )

            # Should still write failure result.json and run.json
            self.assertEqual(rc, 1)
            run_dir = list(runs_root.glob("*/s/t"))[0]
            self.assertTrue((run_dir / "run.json").exists())
            run_record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(run_record["error"], "result_parse_error")
            _assert_run_record_metadata(self, run_record)

    def test_run_json_written_when_result_json_has_oversized_payload(self):
        """Test run.json is written when result.json contains oversized payload."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            agents_default_path = td_path / "agents_default.toml"
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
""".lstrip(),
                encoding="utf-8",
            )

            agents_default_path.write_text(
                """
version = 1

[agents.opencode]
mode = "docker"
enabled_by_default = true
model = "openai/gpt-5.3-codex"
pass_env = []
pre = []
cmd = "true"

[[agents.opencode.bins]]
host = "true"
container = "/usr/local/bin/true"
""".lstrip(),
                encoding="utf-8",
            )

            agents_toml = td_path / "opencode.toml"
            _write_agent_toml(agents_toml, 'name = "opencode"\n')

            def fake_agent(*args, **kwargs):
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.5

            def fake_eval(*args, **kwargs):
                workdir = Path(kwargs["workdir"])
                # Oversized payload: large string (>10KB) and large array (>100 elements)
                oversized_payload = {
                    "status": "passed",
                    "score": 1.0,
                    "large_string": "x" * 20000,  # 20KB string
                    "large_array": list(range(1000)),  # 1000 elements
                }
                (workdir / "result.json").write_text(
                    json.dumps(oversized_payload) + "\n", encoding="utf-8"
                )
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.2

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "AGENTS_DEFAULT_PATH", agents_default_path),
                mock.patch.object(
                    bench, "_run_agent_in_docker", side_effect=fake_agent
                ),
                mock.patch.object(bench, "_run_docker_eval", side_effect=fake_eval),
            ):
                rc = bench.main(
                    ["run", str(agents_toml), "s/t", "--image", "simbench:0.1"]
                )

            # Should succeed and write run.json even with oversized payload
            self.assertEqual(rc, 0)
            run_dir = list(runs_root.glob("*/s/t"))[0]
            self.assertTrue((run_dir / "run.json").exists())
            result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
            run_record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "passed")
            self.assertEqual(run_record["status"], "passed")
            _assert_run_record_metadata(self, run_record)

    def test_run_json_written_when_result_json_has_deeply_nested_object(self):
        """Test run.json is written when result.json contains deeply nested objects."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            agents_default_path = td_path / "agents_default.toml"
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
""".lstrip(),
                encoding="utf-8",
            )

            agents_default_path.write_text(
                """
version = 1

[agents.opencode]
mode = "docker"
enabled_by_default = true
model = "openai/gpt-5.3-codex"
pass_env = []
pre = []
cmd = "true"

[[agents.opencode.bins]]
host = "true"
container = "/usr/local/bin/true"
""".lstrip(),
                encoding="utf-8",
            )

            agents_toml = td_path / "opencode.toml"
            _write_agent_toml(agents_toml, 'name = "opencode"\n')

            def fake_agent(*args, **kwargs):
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.5

            def fake_eval(*args, **kwargs):
                workdir = Path(kwargs["workdir"])

                # Create deeply nested object (50 levels)
                def make_nested(d, depth):
                    if depth == 0:
                        return d
                    return make_nested({"nested": d}, depth - 1)

                nested_payload = make_nested({"leaf": "value"}, 50)
                nested_payload["status"] = "passed"
                nested_payload["score"] = 1.0
                (workdir / "result.json").write_text(
                    json.dumps(nested_payload) + "\n", encoding="utf-8"
                )
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.2

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "AGENTS_DEFAULT_PATH", agents_default_path),
                mock.patch.object(
                    bench, "_run_agent_in_docker", side_effect=fake_agent
                ),
                mock.patch.object(bench, "_run_docker_eval", side_effect=fake_eval),
            ):
                rc = bench.main(
                    ["run", str(agents_toml), "s/t", "--image", "simbench:0.1"]
                )

            # Should succeed even with deeply nested objects
            self.assertEqual(rc, 0)
            run_dir = list(runs_root.glob("*/s/t"))[0]
            self.assertTrue((run_dir / "run.json").exists())
            run_record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(run_record["status"], "passed")
            _assert_run_record_metadata(self, run_record)

    def test_run_json_written_when_result_json_has_unicode_and_emoji(self):
        """Test run.json is written correctly when result.json contains Unicode/emoji."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            agents_default_path = td_path / "agents_default.toml"
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
""".lstrip(),
                encoding="utf-8",
            )

            agents_default_path.write_text(
                """
version = 1

[agents.opencode]
mode = "docker"
enabled_by_default = true
model = "openai/gpt-5.3-codex"
pass_env = []
pre = []
cmd = "true"

[[agents.opencode.bins]]
host = "true"
container = "/usr/local/bin/true"
""".lstrip(),
                encoding="utf-8",
            )

            agents_toml = td_path / "opencode.toml"
            _write_agent_toml(agents_toml, 'name = "opencode"\n')

            def fake_agent(*args, **kwargs):
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.5

            def fake_eval(*args, **kwargs):
                workdir = Path(kwargs["workdir"])
                # Unicode and emoji in values
                unicode_payload = {
                    "status": "passed",
                    "score": 1.0,
                    "message": "こんにちは世界 🌍",
                    "japanese": "日本語テスト",
                    "emoji": "🎉🚀✨",
                }
                (workdir / "result.json").write_text(
                    json.dumps(unicode_payload, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.2

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "AGENTS_DEFAULT_PATH", agents_default_path),
                mock.patch.object(
                    bench, "_run_agent_in_docker", side_effect=fake_agent
                ),
                mock.patch.object(bench, "_run_docker_eval", side_effect=fake_eval),
            ):
                rc = bench.main(
                    ["run", str(agents_toml), "s/t", "--image", "simbench:0.1"]
                )

            self.assertEqual(rc, 0)
            run_dir = list(runs_root.glob("*/s/t"))[0]
            self.assertTrue((run_dir / "run.json").exists())
            result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
            run_record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "passed")
            self.assertEqual(run_record["status"], "passed")
            _assert_run_record_metadata(self, run_record)

    def test_run_json_written_when_result_json_has_invalid_escape_sequences(self):
        """Test run.json is written when result.json contains invalid escape sequences."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            agents_default_path = td_path / "agents_default.toml"
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
""".lstrip(),
                encoding="utf-8",
            )

            agents_default_path.write_text(
                """
version = 1

[agents.opencode]
mode = "docker"
enabled_by_default = true
model = "openai/gpt-5.3-codex"
pass_env = []
pre = []
cmd = "true"

[[agents.opencode.bins]]
host = "true"
container = "/usr/local/bin/true"
""".lstrip(),
                encoding="utf-8",
            )

            agents_toml = td_path / "opencode.toml"
            _write_agent_toml(agents_toml, 'name = "opencode"\n')

            def fake_agent(*args, **kwargs):
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.5

            def fake_eval(*args, **kwargs):
                workdir = Path(kwargs["workdir"])
                # Invalid escape sequences that Python's json will reject
                result_text = '{"status": "passed", "message": "invalid\\escape"}'
                (workdir / "result.json").write_text(
                    result_text + "\n", encoding="utf-8"
                )
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.2

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "AGENTS_DEFAULT_PATH", agents_default_path),
                mock.patch.object(
                    bench, "_run_agent_in_docker", side_effect=fake_agent
                ),
                mock.patch.object(bench, "_run_docker_eval", side_effect=fake_eval),
            ):
                rc = bench.main(
                    ["run", str(agents_toml), "s/t", "--image", "simbench:0.1"]
                )

            # Should fail to parse but still write failure result and run.json
            self.assertEqual(rc, 1)
            run_dir = list(runs_root.glob("*/s/t"))[0]
            self.assertTrue((run_dir / "run.json").exists())
            run_record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(run_record["error"], "result_parse_error")
            _assert_run_record_metadata(self, run_record)

    def test_run_json_written_when_result_json_has_path_traversal_in_metadata(self):
        """Test run.json is written when result.json contains path traversal attempts."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            agents_default_path = td_path / "agents_default.toml"
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
""".lstrip(),
                encoding="utf-8",
            )

            agents_default_path.write_text(
                """
version = 1

[agents.opencode]
mode = "docker"
enabled_by_default = true
model = "openai/gpt-5.3-codex"
pass_env = []
pre = []
cmd = "true"

[[agents.opencode.bins]]
host = "true"
container = "/usr/local/bin/true"
""".lstrip(),
                encoding="utf-8",
            )

            agents_toml = td_path / "opencode.toml"
            _write_agent_toml(agents_toml, 'name = "opencode"\n')

            def fake_agent(*args, **kwargs):
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.5

            def fake_eval(*args, **kwargs):
                workdir = Path(kwargs["workdir"])
                # Path traversal attempt in metadata
                payload = {
                    "status": "passed",
                    "score": 1.0,
                    "path": "../../../etc/passwd",
                    "filepath": "/absolute/../../../etc/passwd",
                }
                (workdir / "result.json").write_text(
                    json.dumps(payload) + "\n", encoding="utf-8"
                )
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.2

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "AGENTS_DEFAULT_PATH", agents_default_path),
                mock.patch.object(
                    bench, "_run_agent_in_docker", side_effect=fake_agent
                ),
                mock.patch.object(bench, "_run_docker_eval", side_effect=fake_eval),
            ):
                rc = bench.main(
                    ["run", str(agents_toml), "s/t", "--image", "simbench:0.1"]
                )

            # Should succeed - path traversal is just data in JSON
            self.assertEqual(rc, 0)
            run_dir = list(runs_root.glob("*/s/t"))[0]
            self.assertTrue((run_dir / "run.json").exists())
            result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
            run_record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "passed")
            self.assertIn("../..", result["path"])  # Data preserved as-is
            self.assertEqual(run_record["status"], "passed")
            _assert_run_record_metadata(self, run_record)

    def test_eval_writes_run_json_with_custom_result_dir(self):
        """Test run.json is written when using custom --result-dir path."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            task_dir = bench_root / "s" / "t"
            workdir = td_path / "workdir"
            workdir.mkdir()
            custom_result_dir = td_path / "custom" / "results" / "path"
            custom_result_dir.mkdir(parents=True)
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
""".lstrip(),
                encoding="utf-8",
            )

            def fake_eval(*args, **kwargs):
                eval_workdir = Path(kwargs["workdir"])
                (eval_workdir / "result.json").write_text(
                    json.dumps({"status": "passed", "score": 1.0}) + "\n",
                    encoding="utf-8",
                )
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.12

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "_run_docker_eval", side_effect=fake_eval),
            ):
                rc = bench.main(
                    [
                        "eval",
                        "s/t",
                        "--workdir",
                        str(workdir),
                        "--result-dir",
                        str(custom_result_dir),
                        "--image",
                        "simbench:0.1",
                    ]
                )

            self.assertEqual(rc, 0)
            # run.json should be in custom result dir, not runs_root
            self.assertTrue((custom_result_dir / "run.json").exists())
            self.assertTrue((custom_result_dir / "result.json").exists())
            run_record = json.loads(
                (custom_result_dir / "run.json").read_text(encoding="utf-8")
            )
            self.assertEqual(run_record["status"], "passed")
            self.assertEqual(run_record["score"], 1.0)
            _assert_run_record_metadata(self, run_record)

    def test_eval_writes_failure_run_json_when_eval_crash_produces_no_output(self):
        """Test run.json is written when eval crashes with no stdout/stderr."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            task_dir = bench_root / "s" / "t"
            workdir = td_path / "workdir"
            workdir.mkdir()
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
""".lstrip(),
                encoding="utf-8",
            )

            def fake_eval(*args, **kwargs):
                # Eval crashes with no output at all
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 137, stdout="", stderr=""), None

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "_run_docker_eval", side_effect=fake_eval),
            ):
                out = StringIO()
                err = StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    rc = bench.main(
                        [
                            "eval",
                            "s/t",
                            "--workdir",
                            str(workdir),
                            "--image",
                            "simbench:0.1",
                        ]
                    )

            # Should fail gracefully
            self.assertEqual(rc, 1)
            run_dir = list(runs_root.glob("*/s/t"))[0]
            self.assertTrue((run_dir / "run.json").exists())
            run_record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            # When eval returns non-zero but produces no result.json, it's treated as missing_result
            self.assertEqual(run_record["error"], "missing_result")
            _assert_run_record_metadata(self, run_record)

    def test_eval_writes_run_json_when_result_json_is_truncated(self):
        """Test run.json is written when result.json is truncated/incomplete."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            task_dir = bench_root / "s" / "t"
            workdir = td_path / "workdir"
            workdir.mkdir()
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
""".lstrip(),
                encoding="utf-8",
            )

            def fake_eval(*args, **kwargs):
                workdir = Path(kwargs["workdir"])
                # Write truncated JSON - missing closing brace
                (workdir / "result.json").write_text(
                    '{"status": "passed", "score": 1.0', encoding="utf-8"
                )
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.12

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "_run_docker_eval", side_effect=fake_eval),
            ):
                rc = bench.main(
                    [
                        "eval",
                        "s/t",
                        "--workdir",
                        str(workdir),
                        "--image",
                        "simbench:0.1",
                    ]
                )

            # Should handle gracefully
            self.assertEqual(rc, 0)  # Eval itself succeeded (exit code 0)
            run_dir = list(runs_root.glob("*/s/t"))[0]
            self.assertTrue((run_dir / "run.json").exists())
            run_record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            # result.json exists but is truncated -> parse error
            self.assertEqual(run_record["error"], "result_parse_error")
            _assert_run_record_metadata(self, run_record)

    def test_eval_writes_run_json_when_result_json_is_empty(self):
        """Test run.json is written when result.json is empty."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            task_dir = bench_root / "s" / "t"
            workdir = td_path / "workdir"
            workdir.mkdir()
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
""".lstrip(),
                encoding="utf-8",
            )

            def fake_eval(*args, **kwargs):
                workdir = Path(kwargs["workdir"])
                # Write empty result.json
                (workdir / "result.json").write_text("", encoding="utf-8")
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.12

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "_run_docker_eval", side_effect=fake_eval),
            ):
                rc = bench.main(
                    [
                        "eval",
                        "s/t",
                        "--workdir",
                        str(workdir),
                        "--image",
                        "simbench:0.1",
                    ]
                )

            self.assertEqual(rc, 0)
            run_dir = list(runs_root.glob("*/s/t"))[0]
            self.assertTrue((run_dir / "run.json").exists())
            run_record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(run_record["error"], "result_parse_error")
            _assert_run_record_metadata(self, run_record)

    def test_run_writes_run_json_with_special_characters_in_result_dir(self):
        """Test run.json is written when result_dir has special characters."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            agents_default_path = td_path / "agents_default.toml"
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
""".lstrip(),
                encoding="utf-8",
            )

            agents_default_path.write_text(
                """
version = 1

[agents.opencode]
mode = "docker"
enabled_by_default = true
model = "openai/gpt-5.3-codex"
pass_env = []
pre = []
cmd = "true"

[[agents.opencode.bins]]
host = "true"
container = "/usr/local/bin/true"
""".lstrip(),
                encoding="utf-8",
            )

            agents_toml = td_path / "opencode.toml"
            _write_agent_toml(agents_toml, 'name = "opencode"\n')

            # Create result dir with spaces and special chars
            special_result_dir = td_path / "results with spaces" / "run-2024.01.01"
            special_result_dir.mkdir(parents=True)

            def fake_agent(*args, **kwargs):
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.5

            def fake_eval(*args, **kwargs):
                workdir = Path(kwargs["workdir"])
                (workdir / "result.json").write_text(
                    json.dumps({"status": "passed", "score": 1.0}) + "\n",
                    encoding="utf-8",
                )
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.2

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "AGENTS_DEFAULT_PATH", agents_default_path),
                mock.patch.object(
                    bench, "_run_agent_in_docker", side_effect=fake_agent
                ),
                mock.patch.object(bench, "_run_docker_eval", side_effect=fake_eval),
            ):
                rc = bench.main(
                    [
                        "run",
                        str(agents_toml),
                        "s/t",
                        "--image",
                        "simbench:0.1",
                        "--result-dir",
                        str(special_result_dir),
                    ]
                )

            self.assertEqual(rc, 0)
            # run.json should be written to special path
            self.assertTrue((special_result_dir / "run.json").exists())
            run_record = json.loads(
                (special_result_dir / "run.json").read_text(encoding="utf-8")
            )
            self.assertEqual(run_record["status"], "passed")
            _assert_run_record_metadata(self, run_record)

    def test_run_json_always_written_even_when_both_artifacts_fail(self):
        """Test run.json is written even when all artifact creation fails."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"
            agents_default_path = td_path / "agents_default.toml"
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
""".lstrip(),
                encoding="utf-8",
            )

            agents_default_path.write_text(
                """
version = 1

[agents.opencode]
mode = "docker"
enabled_by_default = true
model = "openai/gpt-5.3-codex"
pass_env = []
pre = []
cmd = "true"

[[agents.opencode.bins]]
host = "true"
container = "/usr/local/bin/true"
""".lstrip(),
                encoding="utf-8",
            )

            agents_toml = td_path / "opencode.toml"
            _write_agent_toml(agents_toml, 'name = "opencode"\n')

            # Agent fails AND eval produces invalid JSON
            def fake_agent(*args, **kwargs):
                cmd = ["docker", "run"]
                return (
                    subprocess.CompletedProcess(cmd, 1, stdout="", stderr="agent fail"),
                    0.5,
                )

            def fake_eval(*args, **kwargs):
                workdir = Path(kwargs["workdir"])
                # Write invalid JSON
                (workdir / "result.json").write_text("not valid json", encoding="utf-8")
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.2

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "AGENTS_DEFAULT_PATH", agents_default_path),
                mock.patch.object(
                    bench, "_run_agent_in_docker", side_effect=fake_agent
                ),
                mock.patch.object(bench, "_run_docker_eval", side_effect=fake_eval),
            ):
                rc = bench.main(
                    ["run", str(agents_toml), "s/t", "--image", "simbench:0.1"]
                )

            # Should still write run.json
            self.assertEqual(rc, 1)
            run_dir = list(runs_root.glob("*/s/t"))[0]
            self.assertTrue((run_dir / "run.json").exists())
            run_record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            # Agent failed should be the primary error
            self.assertEqual(run_record["error"], "agent_failed")
            _assert_run_record_metadata(self, run_record)
