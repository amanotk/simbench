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
    spec = importlib.util.spec_from_file_location("simbench_runner_bench", bench_py)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


bench = _load_bench_module()


def _write_agent_toml(path: Path, body: str) -> None:
    path.write_text("version = 1\n" + body, encoding="utf-8")


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
                        "eval_inner_sec": 0.25,
                    },
                },
            )

        text = out.getvalue()
        self.assertIn("agent_input_tokens: 269.2k", text)
        self.assertIn("agent_output_tokens: 6.7k", text)
        self.assertIn("agent_cached_input_tokens: 249.9k", text)
        self.assertIn("eval_inner_sec: 0.25", text)

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
        self.assertNotIn('[agent:opencode] stdout: {"type": "reasoning"', streamed)
        self.assertNotIn('[agent:opencode] stdout: {"type": "result"', streamed)

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
                    image="simbench:0.1",
                    workdir=workdir,
                    eval_dir=eval_dir,
                    eval_cmd="/eval/run.sh",
                    shared_eval_dir=shared_eval_dir,
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
            self.assertEqual(result["error"], "agent_setup")
            self.assertEqual(result["message"], "missing-opencode")
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
                        ["run", str(agents_toml), "s/t", "--image", "simbench:0.1"]
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


class TestAgentBinaries(unittest.TestCase):
    def _require_or_skip(self, name: str) -> str:
        found = shutil.which(name)
        if found:
            return found
        if os.environ.get("SIMBENCH_REQUIRE_AGENT_BINS") == "1":
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


class SmokeTestHelpers:
    def _require_docker_image_with_binary(
        self, image: str, binary: str, *, skip_env: str, label: str
    ) -> None:
        inspect = subprocess.run(
            ["docker", "image", "inspect", image],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
        if inspect.returncode != 0:
            self.skipTest(
                f"Docker image {image} not found locally; set {skip_env}=1 to suppress this smoke test explicitly"
            )

        probe = subprocess.run(
            ["docker", "run", "--rm", image, "bash", "-lc", f"command -v {binary}"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
        if probe.returncode != 0:
            self.skipTest(
                f"{label} CLI not available inside {image}; set {skip_env}=1 to suppress this smoke test explicitly"
            )


class TestOpenCodeSmoke(SmokeTestHelpers, unittest.TestCase):
    def _require_docker_image_with_opencode(self, image: str) -> None:
        self._require_docker_image_with_binary(
            image,
            "opencode",
            skip_env="SIMBENCH_SKIP_OPENCODE_SMOKE",
            label="OpenCode",
        )

    def test_run_uses_fake_opencode_end_to_end(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bench_root = td_path / "benchmarks"
            test_task_root = td_path / "test-tasks"
            runs_root = td_path / "runs"
            agents_default_path = td_path / "agents_default.toml"
            task_src = (
                Path(__file__).resolve().parents[1] / "test-tasks" / "smoke" / "py"
            )
            task_dir = test_task_root / "smoke" / "py"
            shutil.copytree(task_src, task_dir)

            run_sh = task_dir / "eval" / "run.sh"
            os.chmod(run_sh, 0o755)

            bin_dir = td_path / "bin"
            bin_dir.mkdir()
            fake_opencode = bin_dir / "opencode"
            fake_opencode.write_text(
                """#!/usr/bin/env python3
import os
import sys
from pathlib import Path


def main() -> int:
    args = sys.argv[1:]
    if args[:2] == [\"stats\", \"--models\"]:
        sys.stdout.write(
            \"\\n\".join(
                [
                    \"┌────────────────────────────────────────────────────────┐\",
                    \"│                    COST & TOKENS                       │\",
                    \"├────────────────────────────────────────────────────────┤\",
                    \"│Total Cost                                        $0.00 │\",
                    \"│Input                                              1.2k │\",
                    \"│Output                                             0.1k │\",
                    \"│Cache Read                                         0.4k │\",
                    \"│Cache Write                                        0.0k │\",
                    \"└────────────────────────────────────────────────────────┘\",
                    \"\",
                ]
            )
        )
        return 0

    if not args or args[0] != \"run\":
        sys.stderr.write(f\"unsupported fake opencode args: {args}\\n\")
        return 2

    workdir = Path(os.environ[\"BENCH_WORKDIR\"])
    target = workdir / \"src\" / \"add.py\"
    target.write_text(
        \"def add_numbers(a, b):\\n    return a + b\\n\",
        encoding=\"utf-8\",
    )

    sys.stdout.write(\"Thinking: inspect smoke task\\n\")
    sys.stdout.write(\"Thinking: implement add_numbers correctly\\n\")
    sys.stdout.write(\"Implementation complete. Public tests pass.\\n\")
    sys.stderr.write(\"→ Read /run/spec.md\\n\")
    sys.stderr.write(\"$ pytest -q\\n\")
    return 0


if __name__ == \"__main__\":
    raise SystemExit(main())
""",
                encoding="utf-8",
            )
            os.chmod(fake_opencode, 0o755)

            agents_default_path.write_text(
                """
version = 1

[agents.opencode]
mode = "host"
enabled_by_default = true
model = "opencode/big-pickle"
pass_env = []
pre = []
cmd = 'opencode run -m "$BENCH_MODEL" "$(cat "$BENCH_PROMPT_FILE")"'
[[agents.opencode.bins]]
host = "opencode"
container = "/usr/local/bin/opencode"
""".lstrip(),
                encoding="utf-8",
            )

            agents_toml = td_path / "opencode.toml"
            _write_agent_toml(
                agents_toml,
                """
name = "opencode"
model = "opencode/big-pickle"
""".lstrip(),
            )

            env = dict(os.environ)
            env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")

            def fake_eval(*, workdir, cmd_log_path=None, **_kwargs):
                (workdir / "result.json").write_text(
                    json.dumps({"status": "passed", "score": 1.0}) + "\n",
                    encoding="utf-8",
                )
                if cmd_log_path is not None:
                    cmd_log_path.write_text(
                        "docker run simbench fake-eval\n", encoding="utf-8"
                    )
                return (
                    subprocess.CompletedProcess(
                        ["docker", "run", "simbench", "fake-eval"],
                        0,
                        stdout="",
                        stderr="",
                    ),
                    0.05,
                )

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "TEST_TASK_ROOT", test_task_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "AGENTS_DEFAULT_PATH", agents_default_path),
                mock.patch.object(bench, "_run_docker_eval", side_effect=fake_eval),
                mock.patch.dict(os.environ, env, clear=True),
            ):
                out = StringIO()
                err = StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    rc = bench.main(
                        [
                            "run",
                            str(agents_toml),
                            "test:smoke/py",
                            "--image",
                            "simbench:0.1",
                        ]
                    )

            self.assertEqual(rc, 0)
            run_dirs = list(runs_root.glob("*/smoke/py"))
            self.assertEqual(len(run_dirs), 1)
            run_dir = run_dirs[0]
            logs_dir = run_dir / "logs"

            result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["score"], 1.0)
            _assert_result_metadata(
                self,
                result,
                task="smoke/py",
                agent="opencode",
                model="opencode/big-pickle",
                agent_exit_code=0,
                eval_exit_code=0,
            )
            self.assertEqual(result["metrics"]["agent_input_tokens"], 1200)
            self.assertEqual(result["metrics"]["agent_output_tokens"], 100)
            self.assertEqual(result["metrics"]["agent_cached_input_tokens"], 400)
            self.assertEqual(result["metrics"]["agent_cache_creation_input_tokens"], 0)
            self.assertIn("agent_inner_sec", result["metrics"])
            self.assertIn("eval_inner_sec", result["metrics"])

            self.assertIn(
                "Thinking: inspect smoke task",
                (logs_dir / "agent.stdout.txt").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "→ Read /run/spec.md",
                (logs_dir / "agent.stderr.txt").read_text(encoding="utf-8"),
            )
            self.assertTrue((logs_dir / "agent.host_cmd.txt").exists())
            self.assertTrue((logs_dir / "eval.docker_cmd.txt").exists())
            self.assertTrue((run_dir / "prompt.txt").exists())
            self.assertTrue((run_dir / "spec.md").exists())

            stderr_text = err.getvalue()
            self.assertIn("[agent:opencode] thinking: inspect smoke task", stderr_text)
            self.assertIn(
                "[agent:opencode] text: Implementation complete. Public tests pass.",
                stderr_text,
            )
            self.assertIn("[agent:opencode] stderr: → Read /run/spec.md", stderr_text)

    def test_real_opencode_smoke_task(self):
        if os.environ.get("SIMBENCH_SKIP_OPENCODE_SMOKE") == "1":
            self.skipTest(
                "Skipping OpenCode smoke test via SIMBENCH_SKIP_OPENCODE_SMOKE"
            )

        if not shutil.which("docker"):
            self.skipTest(
                "Docker binary not found on PATH; set SIMBENCH_SKIP_OPENCODE_SMOKE=1 to suppress this smoke test explicitly"
            )

        repo_root = Path(__file__).resolve().parents[1]
        sample_cfg = repo_root / "sample" / "opencode-smoke.toml"
        self._require_docker_image_with_opencode("simbench:0.1")
        with tempfile.TemporaryDirectory() as td:
            result_dir = Path(td) / "run"
            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = bench.main(
                    [
                        "run",
                        str(sample_cfg),
                        "test:smoke/py",
                        "--image",
                        "simbench:0.1",
                        "--result-dir",
                        str(result_dir),
                    ]
                )

            self.assertEqual(
                rc,
                0,
                msg=(
                    "OpenCode smoke run failed. "
                    f"stdout={out.getvalue()} stderr={err.getvalue()}"
                ),
            )
            self.assertTrue((result_dir / "result.json").exists())
            self.assertTrue((result_dir / "logs" / "agent.stdout.txt").exists())
            self.assertTrue((result_dir / "logs" / "agent.stderr.txt").exists())
            self.assertTrue((result_dir / "logs" / "eval.stdout.txt").exists())
            self.assertTrue((result_dir / "logs" / "eval.stderr.txt").exists())

            result = json.loads(
                (result_dir / "result.json").read_text(encoding="utf-8")
            )
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["score"], 1.0)
            _assert_result_metadata(
                self,
                result,
                task="smoke/py",
                agent="opencode",
                model="opencode/big-pickle",
                agent_exit_code=0,
                eval_exit_code=0,
            )
            self.assertIn("metrics", result)

            agent_stdout = (result_dir / "logs" / "agent.stdout.txt").read_text(
                encoding="utf-8"
            )
            agent_stderr = (result_dir / "logs" / "agent.stderr.txt").read_text(
                encoding="utf-8"
            )
            self.assertTrue(agent_stdout.strip() or agent_stderr.strip())


class TestCopilotSmoke(SmokeTestHelpers, unittest.TestCase):
    def _require_docker_image_with_copilot(self, image: str) -> None:
        self._require_docker_image_with_binary(
            image,
            "copilot",
            skip_env="SIMBENCH_SKIP_COPILOT_SMOKE",
            label="Copilot",
        )

    def test_real_copilot_smoke_task(self):
        if os.environ.get("SIMBENCH_SKIP_COPILOT_SMOKE") == "1":
            self.skipTest("Skipping Copilot smoke test via SIMBENCH_SKIP_COPILOT_SMOKE")

        if not os.environ.get("COPILOT_GITHUB_TOKEN"):
            self.skipTest(
                "COPILOT_GITHUB_TOKEN not set; set SIMBENCH_SKIP_COPILOT_SMOKE=1 to suppress this smoke test explicitly"
            )

        if not shutil.which("docker"):
            self.skipTest(
                "Docker binary not found on PATH; set SIMBENCH_SKIP_COPILOT_SMOKE=1 to suppress this smoke test explicitly"
            )

        repo_root = Path(__file__).resolve().parents[1]
        sample_cfg = repo_root / "sample" / "copilot-smoke.toml"
        self._require_docker_image_with_copilot("simbench:0.1")
        with tempfile.TemporaryDirectory() as td:
            result_dir = Path(td) / "run"
            out = StringIO()
            err = StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                rc = bench.main(
                    [
                        "run",
                        str(sample_cfg),
                        "test:smoke/py",
                        "--image",
                        "simbench:0.1",
                        "--result-dir",
                        str(result_dir),
                    ]
                )

            self.assertEqual(
                rc,
                0,
                msg=(
                    "Copilot smoke run failed. "
                    f"stdout={out.getvalue()} stderr={err.getvalue()}"
                ),
            )
            self.assertTrue((result_dir / "result.json").exists())
            self.assertTrue((result_dir / "logs" / "agent.stdout.txt").exists())
            self.assertTrue((result_dir / "logs" / "agent.stderr.txt").exists())
            self.assertTrue((result_dir / "logs" / "eval.stdout.txt").exists())
            self.assertTrue((result_dir / "logs" / "eval.stderr.txt").exists())

            result = json.loads(
                (result_dir / "result.json").read_text(encoding="utf-8")
            )
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["score"], 1.0)
            _assert_result_metadata(
                self,
                result,
                task="smoke/py",
                agent="copilot",
                model="gpt-4.1",
                agent_exit_code=0,
                eval_exit_code=0,
            )
            self.assertIn("metrics", result)
            self.assertIn("agent_input_tokens", result["metrics"])
            self.assertIn("agent_output_tokens", result["metrics"])
            self.assertIn("agent_cached_input_tokens", result["metrics"])
            self.assertEqual(result["metrics"].get("agent_usage_model"), "gpt-4.1")

            agent_stdout = (result_dir / "logs" / "agent.stdout.txt").read_text(
                encoding="utf-8"
            )
            agent_stderr = (result_dir / "logs" / "agent.stderr.txt").read_text(
                encoding="utf-8"
            )
            self.assertTrue(agent_stdout.strip() or agent_stderr.strip())
            self.assertIn("Total usage est:", agent_stderr)
