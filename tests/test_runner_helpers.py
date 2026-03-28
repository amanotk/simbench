import importlib.util
import json
import os
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
    spec = importlib.util.spec_from_file_location("simbench_runner_bench", bench_py)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


bench = _load_bench_module()


def _write_agent_toml(path: Path, body: str) -> None:
    path.write_text("version = 1\n" + body, encoding="utf-8")


def _fixture_text(name: str) -> str:
    path = Path(__file__).resolve().parent / "fixtures" / "agent_streams" / name
    return path.read_text(encoding="utf-8")


def _replay_pretty_stdout(agent_name: str, stdout: str) -> list[str]:
    phase = f"agent:{agent_name}"
    state = bench._StreamPrettyState(agent_name=agent_name)
    rendered_lines: list[str] = []

    for line in stdout.splitlines(keepends=True):
        parsed, rendered, suppress_raw = bench._format_agent_stream_event(
            phase,
            line,
            state=state,
        )
        if parsed:
            if rendered:
                rendered_lines.append(rendered)
                continue
            if suppress_raw:
                continue

        parsed_plain, rendered_plain = bench._format_agent_plain_stream_line(
            phase, line
        )
        if parsed_plain:
            if rendered_plain:
                rendered_lines.append(rendered_plain)
            continue

        stripped = line.rstrip("\n")
        if stripped:
            rendered_lines.append(f"[{phase}] stdout: {stripped}")

    flushed = bench.flush_stream_state(phase, state)
    if flushed:
        rendered_lines.append(flushed)
    return rendered_lines


def _assert_result_metadata(
    case: unittest.TestCase,
    result: dict,
    *,
    task: str,
    agent: str | None = None,
    model: str | None = None,
    agent_exit_code=None,
    eval_exit_code=None,
) -> None:
    case.assertIn("run_id", result)
    case.assertIsInstance(result["run_id"], str)
    case.assertTrue(result["run_id"])
    case.assertIn("started_at", result)
    case.assertRegex(result["started_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    case.assertEqual(result["task"], task)
    if agent is not None:
        case.assertEqual(result["agent"], agent)
    if model is not None:
        case.assertEqual(result["model"], model)
    if agent_exit_code is not None:
        case.assertEqual(result["agent_exit_code"], agent_exit_code)
    if eval_exit_code is not None:
        case.assertEqual(result["eval_exit_code"], eval_exit_code)


class TestBenchHelpers(unittest.TestCase):
    def test_expand_path(self):
        with mock.patch.dict(os.environ, {"SIMBENCH_X": "abc"}, clear=False):
            self.assertEqual(bench._expand_path("$SIMBENCH_X"), "abc")

    def test_deep_merge_merges_nested_mappings(self):
        base = {
            "runner": {
                "name": "bench",
                "limits": {"seconds": 10, "retries": 1},
            },
            "mode": "safe",
        }
        override = {
            "runner": {
                "limits": {"retries": 3, "jitter": 2},
                "label": "smoke",
            },
            "mode": {"label": "replace"},
        }

        merged = bench._deep_merge(base, override)

        self.assertEqual(
            merged,
            {
                "runner": {
                    "name": "bench",
                    "limits": {"seconds": 10, "retries": 3, "jitter": 2},
                    "label": "smoke",
                },
                "mode": {"label": "replace"},
            },
        )
        self.assertEqual(
            base,
            {
                "runner": {
                    "name": "bench",
                    "limits": {"seconds": 10, "retries": 1},
                },
                "mode": "safe",
            },
        )

    def test_parse_task_ref_supports_prefixed_and_plain_refs(self):
        cases = [
            ("s/t", (None, "s", "t")),
            ("benchmark: s/t", (bench.BENCH_ROOT, "s", "t")),
            ("test-tasks: smoke/py", (bench.TEST_TASK_ROOT, "smoke", "py")),
        ]

        for task_ref, expected in cases:
            with self.subTest(task_ref=task_ref):
                self.assertEqual(bench._parse_task_ref(task_ref), expected)

        for task_ref in ("", "   ", "suite-only", "bench: missing-slash"):
            with self.subTest(task_ref=task_ref):
                with self.assertRaises(ValueError):
                    bench._parse_task_ref(task_ref)

    def test_resolve_host_executable_handles_path_and_path_lookup(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bin_dir = td_path / "bin"
            bin_dir.mkdir()
            exe_path = bin_dir / "fake-runner"
            exe_path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            os.chmod(exe_path, 0o755)

            with mock.patch.dict(
                os.environ,
                {"PATH": str(bin_dir), "SIMBENCH_FAKE_RUNNER": str(exe_path)},
                clear=False,
            ):
                self.assertEqual(
                    bench._resolve_host_executable("fake-runner"), exe_path.resolve()
                )
                self.assertEqual(
                    bench._resolve_host_executable("$SIMBENCH_FAKE_RUNNER"),
                    exe_path.resolve(),
                )
                with self.assertRaises(FileNotFoundError):
                    bench._resolve_host_executable("missing-runner")

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

    def test_extract_agent_usage_metrics_for_opencode_result(self):
        stdout = "\n".join(
            [
                '{"type":"result","usage":{"input_tokens":17101,"cache_creation_input_tokens":0,"cache_read_input_tokens":445056,"output_tokens":6237},"total_cost_usd":0.463958}',
                "",
            ]
        )

        metrics = bench._extract_agent_usage_metrics("opencode", stdout)

        self.assertEqual(metrics["agent_input_tokens"], 17101)
        self.assertEqual(metrics["agent_output_tokens"], 6237)
        self.assertEqual(metrics["agent_cached_input_tokens"], 445056)
        self.assertEqual(metrics["agent_cache_creation_input_tokens"], 0)

    def test_extract_agent_usage_metrics_for_opencode_golden_output(self):
        stdout = _fixture_text("opencode_smoke.stdout.txt")

        metrics = bench._extract_agent_usage_metrics("opencode", stdout)

        self.assertEqual(metrics, {})

    def test_extract_agent_usage_metrics_for_claude_result(self):
        stdout = "\n".join(
            [
                '{"type":"result","subtype":"success","usage":{"input_tokens":2048,"output_tokens":512,"cache_read_input_tokens":4096}}',
                "",
            ]
        )

        metrics = bench._extract_agent_usage_metrics("claude", stdout)

        self.assertEqual(metrics["agent_input_tokens"], 2048)
        self.assertEqual(metrics["agent_output_tokens"], 512)
        self.assertEqual(metrics["agent_cached_input_tokens"], 4096)

    def test_extract_agent_usage_metrics_for_claude_golden_output(self):
        stdout = _fixture_text("claude_smoke.stdout.txt")

        metrics = bench._extract_agent_usage_metrics("claude", stdout)

        self.assertEqual(metrics["agent_input_tokens"], 30)
        self.assertEqual(metrics["agent_output_tokens"], 414)
        self.assertEqual(metrics["agent_cached_input_tokens"], 81590)
        self.assertEqual(metrics["agent_cache_creation_input_tokens"], 20847)

    def test_extract_agent_usage_metrics_for_codex_turn_completed(self):
        stdout = "\n".join(
            [
                '{"type":"thread.started","thread_id":"abc"}',
                '{"type":"turn.completed","usage":{"input_tokens":24763,"cached_input_tokens":24448,"output_tokens":122}}',
                "",
            ]
        )

        metrics = bench._extract_agent_usage_metrics("codex", stdout)

        self.assertEqual(metrics["agent_input_tokens"], 24763)
        self.assertEqual(metrics["agent_output_tokens"], 122)
        self.assertEqual(metrics["agent_cached_input_tokens"], 24448)

    def test_extract_agent_usage_metrics_for_codex_golden_output(self):
        stdout = _fixture_text("codex_smoke.stdout.txt")

        metrics = bench._extract_agent_usage_metrics("codex", stdout)

        self.assertEqual(metrics["agent_input_tokens"], 40987)
        self.assertEqual(metrics["agent_output_tokens"], 605)
        self.assertEqual(metrics["agent_cached_input_tokens"], 37248)

    def test_extract_agent_usage_metrics_ignores_plain_text_opencode_output(self):
        metrics = bench._extract_agent_usage_metrics(
            "opencode", "Thinking: plain text output without JSON\n"
        )
        self.assertEqual(metrics, {})

    def test_extract_agent_usage_metrics_for_copilot_stderr_summary(self):
        stderr = "\n".join(
            [
                "Total usage est:        0 Premium requests",
                "Breakdown by AI model:",
                " gpt-5-mini              269.2k in, 6.7k out, 249.9k cached (Est. 0 Premium requests)",
                "",
            ]
        )

        metrics = bench._extract_agent_usage_metrics("copilot", "", stderr)

        self.assertEqual(metrics["agent_input_tokens"], 269200)
        self.assertEqual(metrics["agent_output_tokens"], 6700)
        self.assertEqual(metrics["agent_cached_input_tokens"], 249900)
        self.assertEqual(metrics["agent_usage_model"], "gpt-5-mini")

    def test_extract_agent_usage_metrics_for_copilot_golden_output(self):
        stderr = _fixture_text("copilot_smoke.stderr.txt")

        metrics = bench._extract_agent_usage_metrics("copilot", "", stderr)

        self.assertEqual(metrics["agent_input_tokens"], 70800)
        self.assertEqual(metrics["agent_output_tokens"], 157)
        self.assertEqual(metrics["agent_cached_input_tokens"], 47400)
        self.assertEqual(metrics["agent_usage_model"], "gpt-4.1")

    def test_extract_opencode_stats_metrics(self):
        stdout = "\n".join(
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

        metrics = bench._extract_opencode_stats_metrics(stdout)

        self.assertEqual(metrics["agent_input_tokens"], 17100)
        self.assertEqual(metrics["agent_output_tokens"], 6200)
        self.assertEqual(metrics["agent_cached_input_tokens"], 445100)
        self.assertEqual(metrics["agent_cache_creation_input_tokens"], 0)

    def test_print_result_summary_formats_token_metrics_in_kilotokens(self):
        out = StringIO()
        with redirect_stdout(out):
            bench._print_result_summary(
                "s/t",
                Path("/tmp/run"),
                {
                    "status": "passed",
                    "score": 1.0,
                    "metrics": {
                        "agent_input_tokens": 269200,
                        "agent_output_tokens": 6700,
                        "agent_cached_input_tokens": 249900,
                        "non_token_value": 1000,
                        "eval_inner_sec": 0.25,
                    },
                },
            )

        text = out.getvalue()
        self.assertIn("agent_input_tokens: 269.2k", text)
        self.assertIn("agent_output_tokens: 6.7k", text)
        self.assertIn("agent_cached_input_tokens: 249.9k", text)
        self.assertIn("non_token_value: 1000", text)
        self.assertIn("eval_inner_sec: 0.25", text)

    def test_print_result_summary_omits_empty_metrics_section(self):
        out = StringIO()
        with redirect_stdout(out):
            bench._print_result_summary(
                "s/t",
                Path("/tmp/run"),
                {
                    "status": "passed",
                    "score": 1.0,
                    "metrics": {},
                },
            )

        text = out.getvalue()
        self.assertNotIn("- metrics:", text)

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
                    image="simbench:0.1",
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="openai/gpt-5.3-codex",
                    timeout_sec=5,
                    extra_env={"OPENAI_API_KEY": "dummy"},
                )

            cmd = " ".join(captured["cmd"])
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
                        image="simbench:0.1",
                        workdir=workdir,
                        run_dir=run_dir,
                        agent_name="dummy",
                        agent_cfg=agent_cfg,
                        model="openai/gpt-5.3-codex",
                        timeout_sec=5,
                        extra_env={"OPENAI_API_KEY": "dummy"},
                        verbose=True,
                    )
            self.assertIn("=== AGENT PHASE ===", err.getvalue())

    def test_run_agent_in_docker_delegates_to_execution_agent(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "work"
            run_dir = Path(td) / "run"
            workdir.mkdir()
            run_dir.mkdir()

            agent_cfg = {
                "name": "dummy",
                "bins": [],
                "mounts": [],
                "pre": [],
                "cmd": "true",
            }
            expected = (
                subprocess.CompletedProcess(["docker", "run"], 0, stdout="", stderr=""),
                0.25,
            )

            with mock.patch.object(
                bench._execution_agent,
                "_run_agent_in_docker",
                return_value=expected,
            ) as delegate:
                result = bench._run_agent_in_docker(
                    image="simbench:0.1",
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="openai/gpt-5.3-codex",
                    timeout_sec=5,
                )

            self.assertEqual(result, expected)
            delegate.assert_called_once()
            kwargs = delegate.call_args.kwargs
            self.assertIs(kwargs["run_capture_stream"], bench._run_capture_stream)
            self.assertIs(
                kwargs["cleanup_docker_container"], bench._cleanup_docker_container
            )
            self.assertIs(kwargs["cmd_str"], bench._cmd_str)
            self.assertIs(kwargs["timed_bash_script"], bench._timed_bash_script)
            self.assertIs(kwargs["extract_inner_sec"], bench._extract_inner_sec)
            self.assertIs(
                kwargs["normalize_model_options"], bench._normalize_model_options
            )

    def test_run_agent_on_host_delegates_to_execution_agent(self):
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "work"
            run_dir = Path(td) / "run"
            workdir.mkdir()
            run_dir.mkdir()

            agent_cfg = {
                "name": "dummy",
                "mode": "host",
                "bins": [],
                "pre": [],
                "cmd": "true",
            }
            expected = (
                subprocess.CompletedProcess(["bash", "-lc"], 0, stdout="", stderr=""),
                0.5,
            )

            with mock.patch.object(
                bench._execution_agent,
                "_run_agent_on_host",
                return_value=expected,
            ) as delegate:
                result = bench._run_agent_on_host(
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="gpt-5.3-codex",
                    timeout_sec=5,
                )

            self.assertEqual(result, expected)
            delegate.assert_called_once()
            kwargs = delegate.call_args.kwargs
            self.assertIs(kwargs["run_capture_stream"], bench._run_capture_stream)
            self.assertIs(
                kwargs["normalize_model_options"], bench._normalize_model_options
            )
            self.assertIs(kwargs["model_options_env"], bench._model_options_env)
            self.assertIs(
                kwargs["inject_model_options_args"], bench._inject_model_options_args
            )

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
                    image="simbench:0.1",
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="openai/gpt-5.3-codex",
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
                    image="simbench:0.1",
                    workdir=workdir,
                    cmd=["python3", "-V"],
                )
            self.assertNotIn("-it", captured["cmd"])

            with mock.patch.object(bench.subprocess, "call", side_effect=fake_call):
                bench._run_docker_shell(
                    image="simbench:0.1",
                    workdir=workdir,
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

    def test_run_capture_stream_timeout_invokes_cleanup(self):
        called = {"count": 0}

        def _cleanup() -> None:
            called["count"] += 1

        with self.assertRaises(subprocess.TimeoutExpired):
            bench._run_capture_stream(
                ["bash", "-lc", "sleep 2"],
                timeout_sec=1,
                verbose=False,
                phase="test-timeout",
                timeout_cleanup=_cleanup,
            )

        self.assertEqual(called["count"], 1)

    def test_run_capture_stream_keyboard_interrupt_invokes_cleanup(self):
        called = {"count": 0}

        class _FakeProc:
            def __init__(self):
                self.stdout = StringIO("")
                self.stderr = StringIO("")
                self._wait_calls = 0
                self.killed = False

            def wait(self, timeout=None):  # noqa: ARG002
                self._wait_calls += 1
                if self._wait_calls == 1:
                    raise KeyboardInterrupt
                return 130

            def kill(self):
                self.killed = True

        fake_proc = _FakeProc()

        def _cleanup() -> None:
            called["count"] += 1

        with mock.patch.object(bench.subprocess, "Popen", return_value=fake_proc):
            with self.assertRaises(KeyboardInterrupt):
                bench._run_capture_stream(
                    ["bash", "-lc", "sleep 10"],
                    timeout_sec=5,
                    verbose=False,
                    phase="test-ctrl-c",
                    timeout_cleanup=_cleanup,
                )

        self.assertTrue(fake_proc.killed)
        self.assertEqual(called["count"], 1)

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

    def test_format_agent_stream_event_claude_message_start_is_suppressed(self):
        state = bench._StreamPrettyState(agent_name="claude")
        parsed, rendered, suppress_raw = bench._format_agent_stream_event(
            "agent:claude",
            '{"type":"stream_event","event":{"type":"message_start","message":{"role":"assistant","content":[]}}}\n',
            state=state,
        )
        self.assertTrue(parsed)
        self.assertIsNone(rendered)
        self.assertTrue(suppress_raw)

    def test_format_agent_stream_event_claude_result_event(self):
        state = bench._StreamPrettyState(agent_name="claude")
        parsed, rendered, suppress_raw = bench._format_agent_stream_event(
            "agent:claude",
            '{"type":"result","subtype":"success","result":"Implemented solver and tests pass.","usage":{"input_tokens":10,"output_tokens":20}}\n',
            state=state,
        )
        self.assertTrue(parsed)
        self.assertEqual(
            rendered, "[agent:claude] text: Implemented solver and tests pass."
        )
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

    def test_run_capture_stream_pretty_timeline_suppresses_claude_message_start(self):
        err = StringIO()
        script = (
            "import json\n"
            "print(json.dumps({'type':'stream_event','event':{'type':'message_start','message':{'role':'assistant','content':[]}}}))\n"
            "print(json.dumps({'type':'stream_event','event':{'type':'content_block_delta','delta':{'type':'thinking_delta','thinking':'plan tests.'}}}))\n"
        )
        with redirect_stderr(err):
            proc = bench._run_capture_stream(
                ["python3", "-c", script],
                timeout_sec=10,
                verbose=True,
                phase="agent:claude",
                pretty_timeline=True,
            )

        self.assertEqual(proc.returncode, 0)
        streamed = err.getvalue()
        self.assertIn("[agent:claude] thinking: plan tests.", streamed)
        self.assertNotIn("message_start", streamed)
        self.assertNotIn('[agent:claude] stdout: {"type": "stream_event"', streamed)

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

    def test_format_agent_stream_event_opencode_specialized_labels(self):
        state = bench._StreamPrettyState(agent_name="opencode")
        parsed, rendered, suppress_raw = bench._format_agent_stream_event(
            "agent:opencode",
            '{"type":"reasoning","part":{"type":"reasoning","text":"**Assessing repo tasks**"}}\n',
            state=state,
        )
        self.assertTrue(parsed)
        self.assertEqual(rendered, "[agent:opencode] plan: Assessing repo tasks")
        self.assertTrue(suppress_raw)

        parsed, rendered, suppress_raw = bench._format_agent_stream_event(
            "agent:opencode",
            '{"type":"tool_use","part":{"type":"tool","tool":"read","state":{"status":"completed","input":{"filePath":"/work/hlld.md"}}}}\n',
            state=state,
        )
        self.assertTrue(parsed)
        self.assertEqual(rendered, "[agent:opencode] tool: read /work/hlld.md")
        self.assertTrue(suppress_raw)

    def test_run_capture_stream_pretty_timeline_renders_opencode_json_events(self):
        err = StringIO()
        script = (
            "import json\n"
            "print(json.dumps({'type':'reasoning','part':{'type':'reasoning','text':'**Check tests**'}}))\n"
            "print(json.dumps({'type':'tool_use','part':{'type':'tool','tool':'bash','state':{'status':'completed','input':{'command':'pytest -q'}}}}))\n"
            "print(json.dumps({'type':'result','result':'done summary','usage':{'input_tokens':1,'output_tokens':2}}))\n"
            "print(json.dumps({'type':'step_finish','part':{'type':'step-finish'}}))\n"
        )
        with redirect_stderr(err):
            proc = bench._run_capture_stream(
                ["python3", "-c", script],
                timeout_sec=10,
                verbose=True,
                phase="agent:opencode",
                pretty_timeline=True,
            )

        self.assertEqual(proc.returncode, 0)
        streamed = err.getvalue()
        self.assertIn("[agent:opencode] plan: Check tests", streamed)
        self.assertIn("[agent:opencode] tool: bash pytest -q", streamed)
        self.assertIn("[agent:opencode] text: done summary", streamed)
        self.assertNotIn('[agent:opencode] stdout: {"type":"reasoning"', streamed)
        self.assertNotIn('[agent:opencode] stdout: {"type":"result"', streamed)

    def test_run_capture_stream_pretty_timeline_formats_opencode_plain_lines(self):
        err = StringIO()
        script = (
            "print('Thinking: inspect smoke task')\n"
            "print('Implementation complete. Public tests pass.')\n"
        )
        with redirect_stderr(err):
            proc = bench._run_capture_stream(
                ["python3", "-c", script],
                timeout_sec=10,
                verbose=True,
                phase="agent:opencode",
                pretty_timeline=True,
            )

        self.assertEqual(proc.returncode, 0)
        streamed = err.getvalue()
        self.assertIn("[agent:opencode] thinking: inspect smoke task", streamed)
        self.assertIn(
            "[agent:opencode] text: Implementation complete. Public tests pass.",
            streamed,
        )
        self.assertNotIn("[agent:opencode] stdout: Thinking:", streamed)

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

    def test_replay_pretty_stdout_for_codex_golden_output(self):
        rendered_lines = _replay_pretty_stdout(
            "codex", _fixture_text("codex_smoke.stdout.txt")
        )
        rendered = "\n".join(rendered_lines)

        self.assertIn(
            "[agent:codex] text: I’ll read the spec at `/run/spec.md` first",
            rendered,
        )
        self.assertIn(
            "[agent:codex] tool: /usr/bin/bash -lc 'pytest -q' (completed)",
            rendered,
        )
        self.assertIn("[agent:codex] patch: /work/src/add.py", rendered)
        self.assertNotIn('[agent:codex] stdout: {"type":"turn.completed"', rendered)

    def test_replay_pretty_stdout_for_claude_golden_output(self):
        rendered_lines = _replay_pretty_stdout(
            "claude", _fixture_text("claude_smoke.stdout.txt")
        )
        rendered = "\n".join(rendered_lines)

        self.assertIn(
            "[agent:claude] thinking: I need to read the spec file first",
            rendered,
        )
        self.assertIn("[agent:claude] tool: Read /run/spec.md", rendered)
        self.assertIn("[agent:claude] tool: Bash pytest -q", rendered)
        self.assertIn("[agent:claude] text: All tests pass.", rendered)
        self.assertNotIn('[agent:claude] stdout: {"type":"result"', rendered)

    def test_replay_pretty_stdout_for_opencode_golden_output(self):
        rendered_lines = _replay_pretty_stdout(
            "opencode", _fixture_text("opencode_smoke.stdout.txt")
        )
        rendered = "\n".join(rendered_lines)

        self.assertIn(
            "[agent:opencode] text: Done. The function now returns `a + b`",
            rendered,
        )
        self.assertNotIn('[agent:opencode] stdout: {"type":"result"', rendered)

    def test_replay_pretty_stdout_for_copilot_golden_output(self):
        rendered_lines = _replay_pretty_stdout(
            "copilot", _fixture_text("copilot_smoke.stdout.txt")
        )
        rendered = "\n".join(rendered_lines)

        self.assertIn("[agent:copilot] tool: Read /run/spec.md", rendered)
        self.assertIn("[agent:copilot] tool: Edit src/add.py (+1 -1)", rendered)
        self.assertIn(
            "[agent:copilot] text: The function add_numbers in src/add.py was updated",
            rendered,
        )

    def test_model_options_render_args(self):
        args = bench._model_options_to_args(
            {
                "reasoning_effort": "high",
                "max_output_tokens": 1200,
            }
        )
        self.assertIn("--reasoning-effort high", args)
        self.assertIn("--max-output-tokens 1200", args)

    def test_normalize_model_options_handles_missing_and_invalid_values(self):
        self.assertEqual(bench._normalize_model_options("opencode", {}), {})
        self.assertEqual(
            bench._normalize_model_options("opencode", {"model_options": None}), {}
        )

        raw_options = {"max_output_tokens": 1200, "reasoning_effort": "high"}
        normalized = bench._normalize_model_options(
            "opencode", {"model_options": raw_options}
        )

        self.assertEqual(normalized, raw_options)
        self.assertIsNot(normalized, raw_options)

        with self.assertRaises(ValueError):
            bench._normalize_model_options("opencode", {"model_options": [1, 2, 3]})

    def test_model_options_env_renders_json_and_typed_entries(self):
        options = {
            "max_output_tokens": 1200,
            "reasoning_effort": "high",
            "debug": True,
            "nested_value": {"z": 2, "a": [1, "x"]},
            "skip": None,
        }

        env = bench._model_options_env(options)

        self.assertEqual(
            json.loads(env["BENCH_MODEL_OPTIONS_JSON"]),
            {
                "debug": True,
                "max_output_tokens": 1200,
                "nested_value": {"a": [1, "x"], "z": 2},
                "reasoning_effort": "high",
                "skip": None,
            },
        )
        self.assertIn("--debug true", env["BENCH_MODEL_OPTIONS_ARGS"])
        self.assertIn("--max-output-tokens 1200", env["BENCH_MODEL_OPTIONS_ARGS"])
        self.assertIn("--reasoning-effort high", env["BENCH_MODEL_OPTIONS_ARGS"])
        self.assertIn(
            '--nested-value \'{"a":[1,"x"],"z":2}\'',
            env["BENCH_MODEL_OPTIONS_ARGS"],
        )
        self.assertEqual(env["BENCH_MODEL_OPT_DEBUG"], "true")
        self.assertEqual(env["BENCH_MODEL_OPT_MAX_OUTPUT_TOKENS"], "1200")
        self.assertEqual(env["BENCH_MODEL_OPT_REASONING_EFFORT"], "high")
        self.assertEqual(env["BENCH_MODEL_OPT_NESTED_VALUE"], '{"a":[1,"x"],"z":2}')
        self.assertNotIn("BENCH_MODEL_OPT_SKIP", env)

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
                    image="simbench:0.1",
                    workdir=workdir,
                    eval_dir=eval_dir,
                    eval_cmd="/eval/run.sh",
                    shared_eval_dir=shared_eval_dir,
                    timeout_sec=5,
                )

            cmd = " ".join(captured["cmd"])
            self.assertIn(f"{str(shared_eval_dir)}:/eval_shared:ro", cmd)
