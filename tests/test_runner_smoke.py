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

from tests.test_runner_helpers import (
    _assert_result_metadata,
    _write_agent_toml,
    bench,
)


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
