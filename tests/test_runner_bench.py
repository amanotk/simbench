import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock


def _load_bench_module():
    repo_root = Path(__file__).resolve().parents[1]
    bench_py = repo_root / "runner" / "bench.py"
    spec = importlib.util.spec_from_file_location("scibench_runner_bench", bench_py)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


bench = _load_bench_module()


def _write_agent_toml(path: Path, body: str) -> None:
    path.write_text("version = 1\n" + body, encoding="utf-8")


class TestBenchHelpers(unittest.TestCase):
    def test_expand_path(self):
        with mock.patch.dict(os.environ, {"SCIBENCH_X": "abc"}, clear=False):
            self.assertEqual(bench._expand_path("$SCIBENCH_X"), "abc")

    def test_load_agent_config_missing(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "missing.toml"
            with self.assertRaises(FileNotFoundError):
                bench._load_agent_config(p)

    def test_load_agent_config_invalid_version(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "agents.toml"
            p.write_text('version = 2\nname = "opencode"\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                bench._load_agent_config(p)

    def test_load_agent_config_missing_name(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "agents.toml"
            p.write_text("version = 1\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                bench._load_agent_config(p)

    def test_run_agent_in_docker_builds_expected_command(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "work"
            run_dir = Path(td) / "run"
            workdir.mkdir()
            run_dir.mkdir()
            (run_dir / "spec.md").write_text("spec\n", encoding="utf-8")
            (run_dir / "prompt.txt").write_text("prompt\n", encoding="utf-8")

            agent_cfg = {
                "name": "dummy",
                "bins": [{"host": "true", "container": "/usr/local/bin/true"}],
                "mounts": [],
                "model_options": {"reasoning_effort": "high"},
                "pre": ["true"],
                "cmd": "true",
            }

            captured = {}

            def fake_run_capture_stream(cmd, **_kwargs):
                captured["cmd"] = cmd
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            with mock.patch.object(
                bench, "_run_capture_stream", side_effect=fake_run_capture_stream
            ):
                bench._run_agent_in_docker(
                    image="scibench:0.1",
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="openai/gpt-5.3-codex",
                    network="off",
                    timeout_sec=5,
                    extra_env={"OPENAI_API_KEY": "dummy"},
                )

            cmd = " ".join(captured["cmd"])
            self.assertIn("--network none", cmd)
            self.assertIn(":/work:rw", cmd)
            self.assertIn(":/run:ro", cmd)
            self.assertIn("BENCH_AGENT=dummy", cmd)
            self.assertIn("BENCH_MODEL=openai/gpt-5.3-codex", cmd)
            self.assertIn("BENCH_MODEL_OPTIONS_JSON=", cmd)
            self.assertIn("BENCH_MODEL_OPTIONS_ARGS=--reasoning-effort high", cmd)

            err = StringIO()
            with redirect_stderr(err):
                with mock.patch.object(
                    bench, "_run_capture_stream", side_effect=fake_run_capture_stream
                ):
                    bench._run_agent_in_docker(
                        image="scibench:0.1",
                        workdir=workdir,
                        run_dir=run_dir,
                        agent_name="dummy",
                        agent_cfg=agent_cfg,
                        model="openai/gpt-5.3-codex",
                        network="off",
                        timeout_sec=5,
                        extra_env={"OPENAI_API_KEY": "dummy"},
                        verbose=True,
                    )
            self.assertIn("=== AGENT PHASE ===", err.getvalue())

    def test_run_agent_in_docker_allows_no_bins(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "work"
            run_dir = Path(td) / "run"
            workdir.mkdir()
            run_dir.mkdir()
            (run_dir / "spec.md").write_text("spec\n", encoding="utf-8")
            (run_dir / "prompt.txt").write_text("prompt\n", encoding="utf-8")

            agent_cfg = {
                "name": "dummy",
                "mounts": [],
                "pre": [],
                "cmd": "true",
            }

            def fake_run_capture_stream(cmd, **_kwargs):
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            with mock.patch.object(
                bench, "_run_capture_stream", side_effect=fake_run_capture_stream
            ):
                bench._run_agent_in_docker(
                    image="scibench:0.1",
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="openai/gpt-5.3-codex",
                    network="on",
                    timeout_sec=5,
                    extra_env=None,
                )

    def test_run_agent_on_host_runs_bash(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            workdir = td_path / "work"
            run_dir = td_path / "run"
            workdir.mkdir()
            run_dir.mkdir()
            (run_dir / "spec.md").write_text("spec\n", encoding="utf-8")
            (run_dir / "prompt.txt").write_text("prompt\n", encoding="utf-8")

            agent_cfg = {
                "name": "dummy",
                "mode": "host",
                "bins": [{"host": "true", "container": "/bin/true"}],
                "pre": ["true"],
                "cmd": "true",
            }

            captured = {}

            def fake_run_capture_stream(cmd, **kwargs):
                captured["cmd"] = cmd
                captured["cwd"] = kwargs.get("cwd")
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            with mock.patch.object(
                bench, "_run_capture_stream", side_effect=fake_run_capture_stream
            ):
                bench._run_agent_on_host(
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="gpt-5.3-codex",
                    timeout_sec=5,
                    extra_env=None,
                )

            self.assertEqual(captured["cmd"][0:2], ["bash", "-lc"])
            self.assertEqual(captured["cwd"], workdir)

    def test_run_docker_shell_tty_only_for_interactive_bash(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td)
            captured = {}

            def fake_call(cmd, **_kwargs):
                captured["cmd"] = cmd
                return 0

            with mock.patch.object(bench.subprocess, "call", side_effect=fake_call):
                bench._run_docker_shell(
                    image="scibench:0.1",
                    workdir=workdir,
                    network="on",
                    cmd=["python3", "-V"],
                )
            self.assertNotIn("-it", captured["cmd"])

            with mock.patch.object(bench.subprocess, "call", side_effect=fake_call):
                bench._run_docker_shell(
                    image="scibench:0.1",
                    workdir=workdir,
                    network="on",
                    cmd=["bash"],
                )
            self.assertIn("-it", captured["cmd"])

    def test_run_capture_stream_verbose_streams_realtime(self):
        err = StringIO()
        with redirect_stderr(err):
            proc = bench._run_capture_stream(
                [
                    "bash",
                    "-lc",
                    "python3 -c \"import sys; print('hi'); print('oops', file=sys.stderr)\"",
                ],
                timeout_sec=10,
                verbose=True,
                phase="test-phase",
            )

        self.assertEqual(proc.returncode, 0)
        self.assertIn("hi", proc.stdout)
        self.assertIn("oops", proc.stderr)
        streamed = err.getvalue()
        self.assertIn("[test-phase] stdout: hi", streamed)
        self.assertIn("[test-phase] stderr: oops", streamed)

    def test_format_agent_stream_event_parses_thinking_and_tool(self):
        state = bench._StreamPrettyState(agent_name="dummy")
        parsed, rendered, suppress_raw = bench._format_agent_stream_event(
            "agent:dummy",
            '{"type":"thinking_delta","thinking":"inspect tests"}\n',
            state=state,
        )
        self.assertTrue(parsed)
        self.assertEqual(rendered, "[agent:dummy] thinking: inspect tests")
        self.assertTrue(suppress_raw)

        parsed, rendered, suppress_raw = bench._format_agent_stream_event(
            "agent:dummy",
            '{"type":"tool_call","tool_name":"Bash","status":"started"}\n',
            state=state,
        )
        self.assertTrue(parsed)
        self.assertEqual(rendered, "[agent:dummy] tool: Bash (started)")
        self.assertTrue(suppress_raw)

    def test_format_agent_stream_event_claude_wrapped_stream_event(self):
        state = bench._StreamPrettyState(agent_name="claude")
        parsed, rendered, suppress_raw = bench._format_agent_stream_event(
            "agent:claude",
            '{"type":"stream_event","event":{"type":"content_block_delta","delta":{"type":"thinking_delta","thinking":"plan tests."}}}\n',
            state=state,
        )
        self.assertTrue(parsed)
        self.assertEqual(rendered, "[agent:claude] thinking: plan tests.")
        self.assertTrue(suppress_raw)

    def test_format_agent_stream_event_claude_assistant_tool_use(self):
        state = bench._StreamPrettyState(agent_name="claude")
        parsed, rendered, suppress_raw = bench._format_agent_stream_event(
            "agent:claude",
            '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Read","input":{"file_path":"/run/spec.md"}}]}}\n',
            state=state,
        )
        self.assertTrue(parsed)
        self.assertEqual(rendered, "[agent:claude] tool: Read /run/spec.md")
        self.assertTrue(suppress_raw)

    def test_format_agent_stream_event_claude_tool_start_event(self):
        state = bench._StreamPrettyState(agent_name="claude")
        parsed, rendered, suppress_raw = bench._format_agent_stream_event(
            "agent:claude",
            '{"type":"stream_event","event":{"type":"content_block_start","content_block":{"type":"tool_use","name":"Read"}}}\n',
            state=state,
        )
        self.assertTrue(parsed)
        self.assertEqual(rendered, "[agent:claude] tool: Read (start)")
        self.assertTrue(suppress_raw)

    def test_run_capture_stream_pretty_timeline_renders_json_events(self):
        err = StringIO()
        script = (
            "import json\n"
            "print(json.dumps({'type':'thinking_delta','thinking':'plan next step'}))\n"
            "print(json.dumps({'type':'tool_call','tool_name':'Bash','status':'started'}))\n"
            "print(json.dumps({'type':'progress','step':1}))\n"
            "print('plain stdout')\n"
        )
        with redirect_stderr(err):
            proc = bench._run_capture_stream(
                ["python3", "-c", script],
                timeout_sec=10,
                verbose=True,
                phase="agent:dummy",
                pretty_timeline=True,
            )

        self.assertEqual(proc.returncode, 0)
        self.assertIn("thinking_delta", proc.stdout)
        self.assertIn("tool_call", proc.stdout)
        streamed = err.getvalue()
        self.assertIn("[agent:dummy] thinking: plan next step", streamed)
        self.assertIn("[agent:dummy] tool: Bash (started)", streamed)
        self.assertIn('[agent:dummy] stdout: {"type": "progress", "step": 1}', streamed)
        self.assertIn("[agent:dummy] stdout: plain stdout", streamed)
        self.assertNotIn('[agent:dummy] stdout: {"type": "thinking_delta"', streamed)

    def test_format_agent_stream_event_codex_specialized_labels(self):
        state = bench._StreamPrettyState(agent_name="codex")
        parsed, rendered, suppress_raw = bench._format_agent_stream_event(
            "agent:codex",
            '{"type":"reasoning_delta","summary":"inspect failing test"}\n',
            state=state,
        )
        self.assertTrue(parsed)
        self.assertEqual(rendered, "[agent:codex] plan: inspect failing test")
        self.assertTrue(suppress_raw)

        parsed, rendered, suppress_raw = bench._format_agent_stream_event(
            "agent:codex",
            '{"type":"exec_command_begin","command":"pytest -q","status":"started"}\n',
            state=state,
        )
        self.assertTrue(parsed)
        self.assertEqual(rendered, "[agent:codex] tool: pytest -q (started)")
        self.assertTrue(suppress_raw)

    def test_format_agent_stream_event_codex_item_wrapper(self):
        state = bench._StreamPrettyState(agent_name="codex")
        parsed, rendered, suppress_raw = bench._format_agent_stream_event(
            "agent:codex",
            '{"type":"item.started","item":{"type":"command_execution","command":"/usr/bin/bash -lc ls","status":"in_progress"}}\n',
            state=state,
        )
        self.assertTrue(parsed)
        self.assertEqual(
            rendered,
            "[agent:codex] tool: /usr/bin/bash -lc ls (in_progress)",
        )
        self.assertTrue(suppress_raw)

    def test_format_agent_stream_event_copilot_permission_label(self):
        state = bench._StreamPrettyState(agent_name="copilot")
        parsed, rendered, suppress_raw = bench._format_agent_stream_event(
            "agent:copilot",
            '{"type":"permission_request","tool_name":"shell","status":"waiting"}\n',
            state=state,
        )
        self.assertTrue(parsed)
        self.assertEqual(rendered, "[agent:copilot] permission: shell (waiting)")
        self.assertTrue(suppress_raw)

    def test_run_capture_stream_pretty_timeline_formats_copilot_plain_lines(self):
        err = StringIO()
        script = "print('Thinking: inspect tests')\nprint('Running pytest -q')\n"
        with redirect_stderr(err):
            proc = bench._run_capture_stream(
                ["python3", "-c", script],
                timeout_sec=10,
                verbose=True,
                phase="agent:copilot",
                pretty_timeline=True,
            )

        self.assertEqual(proc.returncode, 0)
        streamed = err.getvalue()
        self.assertIn("[agent:copilot] thinking: inspect tests", streamed)
        self.assertIn("[agent:copilot] tool: Running pytest -q", streamed)
        self.assertNotIn("[agent:copilot] stdout: Thinking:", streamed)

    def test_model_options_render_args(self):
        args = bench._model_options_to_args(
            {
                "reasoning_effort": "high",
                "max_output_tokens": 1200,
            }
        )
        self.assertIn("--reasoning-effort high", args)
        self.assertIn("--max-output-tokens 1200", args)

    def test_inject_model_options_args_preserves_spaced_values(self):
        cmd = 'tool run $BENCH_MODEL_OPTIONS_ARGS --flag "x"'
        rendered = bench._inject_model_options_args(
            cmd,
            {
                "reasoning_effort": "high",
                "label": "hello world",
            },
        )
        self.assertIn("--reasoning-effort high", rendered)
        self.assertIn("--label 'hello world'", rendered)

    def test_timed_bash_script_does_not_require_python(self):
        script = bench._timed_bash_script("true")
        self.assertNotIn("python3", script)
        self.assertIn("__BENCH_T0__", script)
        self.assertIn("__BENCH_T1__", script)

    def test_extract_inner_sec_from_timepoint_markers(self):
        text = "__BENCH_T0__=100.125\n__BENCH_T1__=100.500\n"
        dt = bench._extract_inner_sec(text)
        self.assertIsNotNone(dt)
        assert dt is not None
        self.assertAlmostEqual(dt, 0.375, places=6)

    def test_prepare_run_dir_merges_suite_shared_workspace(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            runs_root = td_path / "runs"

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
""".lstrip(),
                encoding="utf-8",
            )

            shared_workspace = bench_root / "s" / "shared" / "workspace"
            shared_workspace.mkdir(parents=True)
            (shared_workspace / "from_shared.txt").write_text(
                "shared\n", encoding="utf-8"
            )
            (shared_workspace / "overlay.txt").write_text(
                "shared version\n", encoding="utf-8"
            )
            (task_dir / "workspace" / "overlay.txt").write_text(
                "task version\n", encoding="utf-8"
            )

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
            ):
                task = bench._load_task("s", "t")
                _run_dir, workdir, _logs_dir = bench._prepare_run_dir(
                    task=task, run_id="rid"
                )

            self.assertEqual(
                (workdir / "from_shared.txt").read_text(encoding="utf-8"), "shared\n"
            )
            self.assertEqual(
                (workdir / "overlay.txt").read_text(encoding="utf-8"), "task version\n"
            )

    def test_run_docker_eval_mounts_suite_shared_eval(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            workdir = td_path / "work"
            eval_dir = td_path / "eval"
            shared_eval_dir = td_path / "shared_eval"
            workdir.mkdir()
            eval_dir.mkdir()
            shared_eval_dir.mkdir()

            captured = {}

            def fake_run_capture_stream(cmd, **_kwargs):
                captured["cmd"] = cmd
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            with mock.patch.object(
                bench, "_run_capture_stream", side_effect=fake_run_capture_stream
            ):
                bench._run_docker_eval(
                    image="scibench:0.1",
                    workdir=workdir,
                    eval_dir=eval_dir,
                    eval_cmd="/eval/run.sh",
                    shared_eval_dir=shared_eval_dir,
                    network="off",
                    timeout_sec=5,
                )

            cmd = " ".join(captured["cmd"])
            self.assertIn(f"{str(shared_eval_dir)}:/eval_shared:ro", cmd)


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
                                "scibench:0.1",
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
                            "scibench:0.1",
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

            stderr_text = err.getvalue()
            self.assertIn("=== RUN SETUP ===", stderr_text)


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


class TestAgentBinaries(unittest.TestCase):
    def _require_or_skip(self, name: str) -> str:
        found = shutil.which(name)
        if found:
            return found
        if os.environ.get("SCIBENCH_REQUIRE_AGENT_BINS") == "1":
            self.fail(f"Required binary missing on PATH: {name}")
        self.skipTest(f"Binary not on PATH: {name}")

    def test_agent_bins_runnable(self):
        cmds = [
            ("opencode", ["--version"]),
            ("claude", ["--version"]),
            ("codex", ["--help"]),
            ("copilot", ["--help"]),
        ]
        for name, args in cmds:
            path = self._require_or_skip(name)
            proc = subprocess.run(
                [path] + args,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=15,
            )
            self.assertEqual(
                proc.returncode,
                0,
                msg=(
                    f"{name} returned {proc.returncode}. "
                    f"stdout={proc.stdout.strip()} stderr={proc.stderr.strip()}"
                ),
            )
