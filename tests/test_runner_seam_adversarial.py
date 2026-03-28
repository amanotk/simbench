"""Adversarial tests for bench.py compatibility seams.

These tests verify the stability of the patching interface for:
- bench._run_agent_in_docker
- bench._run_agent_on_host

Focus areas:
- Malformed patch seams
- Missing dependency passthrough
- Wrapper/delegate mismatch
- Argument forwarding drift
- Edge-case failures
"""

import importlib.util
import json
import subprocess
import tempfile
import unittest
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


class TestSeamArgumentForwardingDrift(unittest.TestCase):
    """Test that arguments are properly forwarded from bench wrapper to execution_agent.

    Attack vector: If new parameters are added to execution_agent but not to bench wrapper,
    or vice versa, callers patching bench might receive incorrect behavior.
    """

    def test_run_agent_in_docker_passes_all_expected_kwargs(self):
        """Verify _run_agent_in_docker passes all required kwargs to execution_agent."""
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "work"
            run_dir = Path(td) / "run"
            workdir.mkdir()
            run_dir.mkdir()
            (run_dir / "spec.md").write_text("spec\n", encoding="utf-8")
            (run_dir / "prompt.txt").write_text("prompt\n", encoding="utf-8")

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
                bench._run_agent_in_docker(
                    image="simbench:0.1",
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="openai/gpt-5.3-codex",
                    timeout_sec=5,
                    extra_env={"KEY": "value"},
                    verbose=True,
                    cmd_log_path=run_dir / "cmd.txt",
                )

            delegate.assert_called_once()
            kwargs = delegate.call_args.kwargs

            # Critical seam markers - these must always be present
            self.assertEqual(kwargs["image"], "simbench:0.1")
            self.assertEqual(kwargs["workdir"], workdir)
            self.assertEqual(kwargs["run_dir"], run_dir)
            self.assertEqual(kwargs["agent_name"], "dummy")
            self.assertEqual(kwargs["agent_cfg"], agent_cfg)
            self.assertEqual(kwargs["model"], "openai/gpt-5.3-codex")
            self.assertEqual(kwargs["timeout_sec"], 5)
            self.assertEqual(kwargs["extra_env"], {"KEY": "value"})
            self.assertEqual(kwargs["verbose"], True)
            self.assertEqual(kwargs["cmd_log_path"], run_dir / "cmd.txt")

    def test_run_agent_on_host_passes_all_expected_kwargs(self):
        """Verify _run_agent_on_host passes all required kwargs to execution_agent."""
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
                bench._run_agent_on_host(
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="gpt-5.3-codex",
                    timeout_sec=5,
                    extra_env={"KEY": "value"},
                    verbose=True,
                    cmd_log_path=run_dir / "cmd.txt",
                )

            delegate.assert_called_once()
            kwargs = delegate.call_args.kwargs

            # Critical seam markers - these must always be present
            self.assertEqual(kwargs["workdir"], workdir)
            self.assertEqual(kwargs["run_dir"], run_dir)
            self.assertEqual(kwargs["agent_name"], "dummy")
            self.assertEqual(kwargs["agent_cfg"], agent_cfg)
            self.assertEqual(kwargs["model"], "gpt-5.3-codex")
            self.assertEqual(kwargs["timeout_sec"], 5)
            self.assertEqual(kwargs["extra_env"], {"KEY": "value"})
            self.assertEqual(kwargs["verbose"], True)
            self.assertEqual(kwargs["cmd_log_path"], run_dir / "cmd.txt")


class TestSeamMissingDependencyPassthrough(unittest.TestCase):
    """Test that all required dependencies are passed through the seam.

    Attack vector: If a dependency is missing from the passthrough, callers
    patching bench._run_agent_in_docker may find that some functionality breaks.
    """

    def test_run_agent_in_docker_passes_run_capture_stream(self):
        """Verify run_capture_stream dependency is properly passed."""
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "work"
            run_dir = Path(td) / "run"
            workdir.mkdir()
            run_dir.mkdir()
            (run_dir / "spec.md").write_text("spec\n", encoding="utf-8")
            (run_dir / "prompt.txt").write_text("prompt\n", encoding="utf-8")

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
                bench._run_agent_in_docker(
                    image="simbench:0.1",
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="openai/gpt-5.3-codex",
                    timeout_sec=5,
                )

            kwargs = delegate.call_args.kwargs
            # Critical: run_capture_stream must be the bench wrapper, not raw function
            self.assertIs(kwargs["run_capture_stream"], bench._run_capture_stream)

    def test_run_agent_in_docker_passes_cleanup_docker_container(self):
        """Verify cleanup_docker_container dependency is properly passed."""
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "work"
            run_dir = Path(td) / "run"
            workdir.mkdir()
            run_dir.mkdir()
            (run_dir / "spec.md").write_text("spec\n", encoding="utf-8")
            (run_dir / "prompt.txt").write_text("prompt\n", encoding="utf-8")

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
                bench._run_agent_in_docker(
                    image="simbench:0.1",
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="openai/gpt-5.3-codex",
                    timeout_sec=5,
                )

            kwargs = delegate.call_args.kwargs
            # Critical: cleanup_docker_container must be the bench wrapper
            self.assertIs(
                kwargs["cleanup_docker_container"], bench._cleanup_docker_container
            )

    def test_run_agent_in_docker_passes_os_and_secrets_mods(self):
        """Verify os_mod and secrets_mod are passed for docker mode."""
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "work"
            run_dir = Path(td) / "run"
            workdir.mkdir()
            run_dir.mkdir()
            (run_dir / "spec.md").write_text("spec\n", encoding="utf-8")
            (run_dir / "prompt.txt").write_text("prompt\n", encoding="utf-8")

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
                bench._run_agent_in_docker(
                    image="simbench:0.1",
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="openai/gpt-5.3-codex",
                    timeout_sec=5,
                )

            kwargs = delegate.call_args.kwargs
            # Critical: os_mod and secrets_mod must be passed through for docker mode
            self.assertIs(kwargs["os_mod"], bench.os)
            self.assertIs(kwargs["secrets_mod"], bench.secrets)

    def test_run_agent_in_docker_passes_model_options_helpers(self):
        """Verify model options helper dependencies are properly passed."""
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "work"
            run_dir = Path(td) / "run"
            workdir.mkdir()
            run_dir.mkdir()
            (run_dir / "spec.md").write_text("spec\n", encoding="utf-8")
            (run_dir / "prompt.txt").write_text("prompt\n", encoding="utf-8")

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
                bench._run_agent_in_docker(
                    image="simbench:0.1",
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="openai/gpt-5.3-codex",
                    timeout_sec=5,
                )

            kwargs = delegate.call_args.kwargs
            # All model options helpers must be passed through
            self.assertIs(
                kwargs["normalize_model_options"], bench._normalize_model_options
            )
            self.assertIs(kwargs["model_options_env"], bench._model_options_env)
            self.assertIs(
                kwargs["inject_model_options_args"], bench._inject_model_options_args
            )

    def test_run_agent_in_docker_passes_expand_path(self):
        """Verify expand_path is passed for docker mode."""
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "work"
            run_dir = Path(td) / "run"
            workdir.mkdir()
            run_dir.mkdir()
            (run_dir / "spec.md").write_text("spec\n", encoding="utf-8")
            (run_dir / "prompt.txt").write_text("prompt\n", encoding="utf-8")

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
                bench._run_agent_in_docker(
                    image="simbench:0.1",
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="openai/gpt-5.3-codex",
                    timeout_sec=5,
                )

            kwargs = delegate.call_args.kwargs
            # Critical: expand_path must be passed through for docker mode
            self.assertIs(kwargs["expand_path"], bench._expand_path)

    def test_run_agent_on_host_passes_model_options_helpers(self):
        """Verify model options helpers are passed for host mode."""
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
                bench._run_agent_on_host(
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="gpt-5.3-codex",
                    timeout_sec=5,
                )

            kwargs = delegate.call_args.kwargs
            # Model options helpers must be passed through for host mode too
            self.assertIs(
                kwargs["normalize_model_options"], bench._normalize_model_options
            )
            self.assertIs(kwargs["model_options_env"], bench._model_options_env)
            self.assertIs(
                kwargs["inject_model_options_args"], bench._inject_model_options_args
            )

    def test_run_agent_on_host_passes_resolve_host_executable(self):
        """Verify resolve_host_executable is passed for host mode."""
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
                bench._run_agent_on_host(
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="gpt-5.3-codex",
                    timeout_sec=5,
                )

            kwargs = delegate.call_args.kwargs
            self.assertIs(
                kwargs["resolve_host_executable"], bench._resolve_host_executable
            )


class TestSeamEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions for the seam."""

    def test_run_agent_in_docker_with_none_extra_env(self):
        """Verify None extra_env is handled correctly."""
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "work"
            run_dir = Path(td) / "run"
            workdir.mkdir()
            run_dir.mkdir()
            (run_dir / "spec.md").write_text("spec\n", encoding="utf-8")
            (run_dir / "prompt.txt").write_text("prompt\n", encoding="utf-8")

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
            ):
                # Should not raise - None is a valid value for extra_env
                result = bench._run_agent_in_docker(
                    image="simbench:0.1",
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="openai/gpt-5.3-codex",
                    timeout_sec=5,
                    extra_env=None,
                )

            self.assertEqual(result, expected)

    def test_run_agent_on_host_with_none_extra_env(self):
        """Verify None extra_env is handled correctly in host mode."""
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
            ):
                # Should not raise - None is a valid value for extra_env
                result = bench._run_agent_on_host(
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="gpt-5.3-codex",
                    timeout_sec=5,
                    extra_env=None,
                )

            self.assertEqual(result, expected)

    def test_run_agent_in_docker_with_empty_extra_env(self):
        """Verify empty dict extra_env is handled correctly."""
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "work"
            run_dir = Path(td) / "run"
            workdir.mkdir()
            run_dir.mkdir()
            (run_dir / "spec.md").write_text("spec\n", encoding="utf-8")
            (run_dir / "prompt.txt").write_text("prompt\n", encoding="utf-8")

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
            ):
                result = bench._run_agent_in_docker(
                    image="simbench:0.1",
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="openai/gpt-5.3-codex",
                    timeout_sec=5,
                    extra_env={},
                )

            self.assertEqual(result, expected)

    def test_run_agent_in_docker_with_pathlike_workdir(self):
        """Verify Path objects work correctly for workdir/run_dir."""
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "work"
            run_dir = Path(td) / "run"
            workdir.mkdir()
            run_dir.mkdir()
            (run_dir / "spec.md").write_text("spec\n", encoding="utf-8")
            (run_dir / "prompt.txt").write_text("prompt\n", encoding="utf-8")

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
            ):
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

    def test_run_agent_in_docker_with_string_workdir(self):
        """Verify string paths work correctly for workdir/run_dir."""
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
            ):
                # Pass as strings instead of Path objects
                result = bench._run_agent_in_docker(
                    image="simbench:0.1",
                    workdir=str(workdir),
                    run_dir=str(run_dir),
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="openai/gpt-5.3-codex",
                    timeout_sec=5,
                )

            self.assertEqual(result, expected)

    def test_run_agent_in_docker_verbose_false_still_works(self):
        """Verify verbose=False is properly passed through."""
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "work"
            run_dir = Path(td) / "run"
            workdir.mkdir()
            run_dir.mkdir()
            (run_dir / "spec.md").write_text("spec\n", encoding="utf-8")
            (run_dir / "prompt.txt").write_text("prompt\n", encoding="utf-8")

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
                bench._run_agent_in_docker(
                    image="simbench:0.1",
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="openai/gpt-5.3-codex",
                    timeout_sec=5,
                    verbose=False,
                )

            kwargs = delegate.call_args.kwargs
            self.assertEqual(kwargs["verbose"], False)

    def test_run_agent_on_host_verbose_false_still_works(self):
        """Verify verbose=False is properly passed through in host mode."""
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
                bench._run_agent_on_host(
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="gpt-5.3-codex",
                    timeout_sec=5,
                    verbose=False,
                )

            kwargs = delegate.call_args.kwargs
            self.assertEqual(kwargs["verbose"], False)


class TestSeamMalformedPatchSeams(unittest.TestCase):
    """Test behavior when callers patch the seams incorrectly.

    Attack vector: Callers might try to patch the seam in ways that break
    the expected contract. We verify the seam handles these gracefully.
    """

    def test_patching_run_agent_in_docker_to_return_wrong_type(self):
        """If caller patches to return wrong type, the result is unusable."""
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

            # Simulate a broken patch that returns wrong type
            def broken_patcher(*args, **kwargs):
                return "not a tuple"  # Should be (CompletedProcess, float|None)

            with mock.patch.object(
                bench, "_run_agent_in_docker", side_effect=broken_patcher
            ):
                result = bench._run_agent_in_docker(
                    image="simbench:0.1",
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="openai/gpt-5.3-codex",
                    timeout_sec=5,
                )
                # The wrong type is returned - attempting to use it as expected
                # will fail downstream (this verifies the contract violation)
                self.assertEqual(result, "not a tuple")
                # Verify it's NOT the expected tuple structure
                self.assertIsInstance(result, str)

    def test_patching_run_agent_on_host_to_return_wrong_type(self):
        """If caller patches to return wrong type, the result is unusable."""
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

            # Simulate a broken patch that returns wrong type
            def broken_patcher(*args, **kwargs):
                return "not a tuple"  # Should be (CompletedProcess, float|None)

            with mock.patch.object(
                bench, "_run_agent_on_host", side_effect=broken_patcher
            ):
                result = bench._run_agent_on_host(
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="gpt-5.3-codex",
                    timeout_sec=5,
                )
                # The wrong type is returned - attempting to use it as expected
                # will fail downstream (this verifies the contract violation)
                self.assertEqual(result, "not a tuple")
                # Verify it's NOT the expected tuple structure
                self.assertIsInstance(result, str)

    def test_run_agent_in_docker_with_missing_required_args(self):
        """Verify missing required arguments raise appropriate errors."""
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "work"
            run_dir = Path(td) / "run"
            workdir.mkdir()
            run_dir.mkdir()

            # Missing agent_cfg - should fail
            with self.assertRaises(TypeError):
                bench._run_agent_in_docker(
                    image="simbench:0.1",
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    # agent_cfg missing
                    model="openai/gpt-5.3-codex",
                    timeout_sec=5,
                )

    def test_run_agent_on_host_with_missing_required_args(self):
        """Verify missing required arguments raise appropriate errors in host mode."""
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "work"
            run_dir = Path(td) / "run"
            workdir.mkdir()
            run_dir.mkdir()

            # Missing agent_cfg - should fail
            with self.assertRaises(TypeError):
                bench._run_agent_on_host(
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    # agent_cfg missing
                    model="gpt-5.3-codex",
                    timeout_sec=5,
                )


class TestSeamWrapperDelegateMismatch(unittest.TestCase):
    """Test wrapper/delegate behavior consistency.

    Attack vector: If the wrapper and delegate have different behavior,
    callers patching bench._run_agent_in_docker might get unexpected results.
    """

    def test_run_agent_in_docker_returns_exactly_what_delegate_returns(self):
        """Verify the wrapper returns exactly what the delegate returns."""
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "work"
            run_dir = Path(td) / "run"
            workdir.mkdir()
            run_dir.mkdir()
            (run_dir / "spec.md").write_text("spec\n", encoding="utf-8")
            (run_dir / "prompt.txt").write_text("prompt\n", encoding="utf-8")

            agent_cfg = {
                "name": "dummy",
                "bins": [],
                "mounts": [],
                "pre": [],
                "cmd": "true",
            }

            proc = subprocess.CompletedProcess(
                ["docker", "run", "image"],
                0,
                stdout="agent output",
                stderr="agent error",
            )
            expected = (proc, 1.234)

            with mock.patch.object(
                bench._execution_agent,
                "_run_agent_in_docker",
                return_value=expected,
            ):
                result = bench._run_agent_in_docker(
                    image="simbench:0.1",
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="openai/gpt-5.3-codex",
                    timeout_sec=5,
                )

            # Must be exactly the same tuple
            self.assertIs(result[0], expected[0])
            self.assertEqual(result[1], expected[1])

    def test_run_agent_on_host_returns_exactly_what_delegate_returns(self):
        """Verify the wrapper returns exactly what the delegate returns in host mode."""
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

            proc = subprocess.CompletedProcess(
                ["bash", "-lc", "true"],
                0,
                stdout="host output",
                stderr="host error",
            )
            expected = (proc, 2.5)

            with mock.patch.object(
                bench._execution_agent,
                "_run_agent_on_host",
                return_value=expected,
            ):
                result = bench._run_agent_on_host(
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="gpt-5.3-codex",
                    timeout_sec=5,
                )

            # Must be exactly the same tuple
            self.assertIs(result[0], expected[0])
            self.assertEqual(result[1], expected[1])

    def test_run_agent_in_docker_returns_none_for_inner_sec_on_failure(self):
        """Verify None inner_sec is properly propagated on failure."""
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "work"
            run_dir = Path(td) / "run"
            workdir.mkdir()
            run_dir.mkdir()
            (run_dir / "spec.md").write_text("spec\n", encoding="utf-8")
            (run_dir / "prompt.txt").write_text("prompt\n", encoding="utf-8")

            agent_cfg = {
                "name": "dummy",
                "bins": [],
                "mounts": [],
                "pre": [],
                "cmd": "true",
            }

            proc = subprocess.CompletedProcess(
                ["docker", "run", "image"],
                1,  # Non-zero exit
                stdout="",
                stderr="failed",
            )
            expected = (proc, None)  # Some failures may not have timing

            with mock.patch.object(
                bench._execution_agent,
                "_run_agent_in_docker",
                return_value=expected,
            ):
                result = bench._run_agent_in_docker(
                    image="simbench:0.1",
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="openai/gpt-5.3-codex",
                    timeout_sec=5,
                )

            # Must preserve None for timing
            self.assertIsNone(result[1])


class TestSeamSubprocessModulePassthrough(unittest.TestCase):
    """Test subprocess module passthrough.

    Attack vector: If subprocess_mod is not passed correctly,
    the execution agent may use a different subprocess than expected.
    """

    def test_run_agent_in_docker_passes_subprocess_mod(self):
        """Verify subprocess_mod is correctly passed."""
        with tempfile.TemporaryDirectory() as td:
            workdir = Path(td) / "work"
            run_dir = Path(td) / "run"
            workdir.mkdir()
            run_dir.mkdir()
            (run_dir / "spec.md").write_text("spec\n", encoding="utf-8")
            (run_dir / "prompt.txt").write_text("prompt\n", encoding="utf-8")

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
                bench._run_agent_in_docker(
                    image="simbench:0.1",
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="openai/gpt-5.3-codex",
                    timeout_sec=5,
                )

            kwargs = delegate.call_args.kwargs
            # Must pass the actual subprocess module, not a mock
            self.assertIs(kwargs["subprocess_mod"], bench.subprocess)

    def test_run_agent_on_host_passes_subprocess_and_time_mods(self):
        """Verify subprocess_mod and time_mod are correctly passed for host mode."""
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
                bench._run_agent_on_host(
                    workdir=workdir,
                    run_dir=run_dir,
                    agent_name="dummy",
                    agent_cfg=agent_cfg,
                    model="gpt-5.3-codex",
                    timeout_sec=5,
                )

            kwargs = delegate.call_args.kwargs
            # Must pass the actual modules
            self.assertIs(kwargs["subprocess_mod"], bench.subprocess)
            self.assertIs(kwargs["time_mod"], bench.time)


class TestSeamCLIPassthroughVerification(unittest.TestCase):
    """Verify CLI commands properly use the seams."""

    def test_run_command_uses_run_agent_in_docker_seam(self):
        """Verify the run command properly delegates to _run_agent_in_docker."""
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

[agents.test]
mode = "docker"
enabled_by_default = true
model = "test/model"
pass_env = []
pre = []
cmd = "true"
""".lstrip(),
                encoding="utf-8",
            )

            agents_toml = td_path / "test.toml"
            _write_agent_toml(agents_toml, 'name = "test"\n')

            def fake_agent(*args, **kwargs):
                cmd = ["docker", "run"]
                return (
                    subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""),
                    0.1,
                )

            def fake_eval(*, workdir: Path, **_kwargs):
                (workdir / "result.json").write_text(
                    json.dumps({"status": "passed", "score": 1.0}) + "\n",
                    encoding="utf-8",
                )
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.1

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(
                    bench, "_run_agent_in_docker", side_effect=fake_agent
                ) as run_agent_mock,
                mock.patch.object(bench, "_run_docker_eval", side_effect=fake_eval),
                mock.patch.object(bench, "AGENTS_DEFAULT_PATH", agents_default_path),
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

            # Verify seam was called exactly once
            run_agent_mock.assert_called_once()

            # Verify the call includes expected parameters
            call_kwargs = run_agent_mock.call_args.kwargs
            self.assertEqual(call_kwargs["image"], "simbench:0.1")
            self.assertEqual(call_kwargs["agent_name"], "test")
            self.assertEqual(call_kwargs["model"], "test/model")

    def test_run_command_uses_run_agent_on_host_seam(self):
        """Verify the run command properly delegates to _run_agent_on_host."""
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

[agents.test]
mode = "host"
enabled_by_default = true
model = "test/model"
pass_env = []
pre = []
cmd = "true"
""".lstrip(),
                encoding="utf-8",
            )

            agents_toml = td_path / "test.toml"
            _write_agent_toml(agents_toml, 'name = "test"\n')

            def fake_agent(*args, **kwargs):
                cmd = ["bash", "-lc"]
                return (
                    subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""),
                    0.1,
                )

            def fake_eval(*, workdir: Path, **_kwargs):
                (workdir / "result.json").write_text(
                    json.dumps({"status": "passed", "score": 1.0}) + "\n",
                    encoding="utf-8",
                )
                cmd = ["docker", "run"]
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr=""), 0.1

            with (
                mock.patch.object(bench, "BENCH_ROOT", bench_root),
                mock.patch.object(bench, "RUNS_ROOT", runs_root),
                mock.patch.object(
                    bench, "_run_agent_on_host", side_effect=fake_agent
                ) as run_agent_mock,
                mock.patch.object(bench, "_run_docker_eval", side_effect=fake_eval),
                mock.patch.object(bench, "AGENTS_DEFAULT_PATH", agents_default_path),
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

            # Verify seam was called exactly once
            run_agent_mock.assert_called_once()

            # Verify the call includes expected parameters
            call_kwargs = run_agent_mock.call_args.kwargs
            self.assertEqual(call_kwargs["agent_name"], "test")
            self.assertEqual(call_kwargs["model"], "test/model")


if __name__ == "__main__":
    unittest.main()
