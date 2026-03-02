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

    def test_is_agent_enabled_requires_env_for_non_default(self):
        cfg = {"name": "codex"}
        with mock.patch.dict(os.environ, {"SCIBENCH_ENABLE_CODEX": "0"}, clear=False):
            enabled, reason = bench._is_agent_enabled(cfg)
        self.assertFalse(enabled)
        self.assertIn("SCIBENCH_ENABLE_CODEX", reason)

    def test_is_agent_enabled_opencode_default_true(self):
        cfg = {"name": "opencode"}
        with mock.patch.dict(
            os.environ, {"SCIBENCH_ENABLE_OPENCODE": "0"}, clear=False
        ):
            enabled, _reason = bench._is_agent_enabled(cfg)
        self.assertTrue(enabled)

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
                "pre": ["true"],
                "cmd": "true",
            }

            captured = {}

            def fake_run(cmd, **kwargs):
                captured["cmd"] = cmd
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            with mock.patch.object(bench.subprocess, "run", side_effect=fake_run):
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

            def fake_run(cmd, **_kwargs):
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            with mock.patch.object(bench.subprocess, "run", side_effect=fake_run):
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

            def fake_run(cmd, **kwargs):
                captured["cmd"] = cmd
                captured["cwd"] = kwargs.get("cwd")
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            with mock.patch.object(bench.subprocess, "run", side_effect=fake_run):
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
default_model = "provider/model-x"
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
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            def fake_eval(*, workdir: Path, **_kwargs):
                (workdir / "result.json").write_text(
                    json.dumps({"status": "passed", "score": 1.0}) + "\n",
                    encoding="utf-8",
                )
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

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
                        "SCIBENCH_ENABLE_DUMMY": "1",
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

    def test_convenience_form_toml_prefix_maps_to_run(self):
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
default_model = "openai/gpt-5.3-codex"
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
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            def fake_eval(*, workdir: Path, **_kwargs):
                (workdir / "result.json").write_text(
                    json.dumps({"status": "passed", "score": 1.0}) + "\n",
                    encoding="utf-8",
                )
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(bench, "AGENTS_DEFAULT_PATH", agents_default_path),
                mock.patch.object(
                    bench, "_run_agent_in_docker", side_effect=fake_agent
                ),
                mock.patch.object(bench, "_run_docker_eval", side_effect=fake_eval),
            ):
                rc = bench.main([str(agents_toml), "s/t", "--image", "scibench:0.1"])

            self.assertEqual(rc, 0)


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
