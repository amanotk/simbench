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
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["score"], 0.0)
            self.assertEqual(result["error"], "agent_timeout")
            self.assertIn("during agent phase", result["message"])
            _assert_result_metadata(
                self,
                result,
                task="s/t",
                agent="opencode",
                model="openai/gpt-5.3-codex",
                agent_exit_code="timeout",
            )
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
            result = json.loads(
                (run_dirs[0] / "result.json").read_text(encoding="utf-8")
            )
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
                self.assertEqual(
                    cmd,
                    ["opencode", "stats", "--models", "1"],
                )
                self.assertIn("XDG_DATA_HOME", kwargs["env"])
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
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["error"], "eval_timeout")
            self.assertIn("during eval phase", result["message"])
            _assert_result_metadata(self, result, task="s/t", eval_exit_code="timeout")
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
            self.assertEqual(result["error"], "missing_result")
            _assert_result_metadata(self, result, task="s/t", eval_exit_code=5)
