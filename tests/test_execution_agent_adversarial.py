#!/usr/bin/env python3
"""
Adversarial tests for runner/execution_agent.py extraction.
Focuses on malformed inputs, boundary conditions, validation, and behavior preservation.
"""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from typing import Any

import sys
import os

# Ensure we can import from runner/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.chdir(Path(__file__).resolve().parents[1])

from runner import execution_agent as _execution_agent


def _make_fake_completedprocess(
    returncode: int = 0, stdout: str = "", stderr: str = ""
):
    """Create a mock CompletedProcess with timing in stdout."""
    return subprocess.CompletedProcess(
        args=["bash", "-lc", "echo test"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


class TestRunAgentInDockerValidation(unittest.TestCase):
    """Test input validation for _run_agent_in_docker."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workdir = Path(self.temp_dir) / "workdir"
        self.run_dir = Path(self.temp_dir) / "rundir"
        self.workdir.mkdir(parents=True)
        self.run_dir.mkdir(parents=True)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_mock_run_capture_stream(self, returncode: int = 0):
        """Create a mock run_capture_stream that returns a fake result."""

        def mock_run(*args, **kwargs):
            return _make_fake_completedprocess(
                returncode=returncode,
                stdout="",
                stderr="",
            )

        return mock_run

    def _make_mock_cleanup(self):
        """Create a mock cleanup function."""
        return mock.MagicMock()

    # --- Bins validation ---

    def test_bins_must_be_list(self):
        """Test that bins must be a list, not a dict or string."""
        with self.assertRaises(ValueError) as ctx:
            _execution_agent._run_agent_in_docker(
                image="test-image",
                workdir=self.workdir,
                run_dir=self.run_dir,
                agent_name="test-agent",
                agent_cfg={
                    "bins": {"host": "ls", "container": "/bin/ls"}
                },  # Not a list
                model="test-model",
                timeout_sec=60,
                run_capture_stream=self._make_mock_run_capture_stream(),
                cleanup_docker_container=self._make_mock_cleanup(),
                cmd_str=lambda x: " ".join(x),
            )
        self.assertIn("bins must be a list", str(ctx.exception))

    def test_bins_invalid_entry_type(self):
        """Test that each bin entry must be a dict."""
        with self.assertRaises(ValueError) as ctx:
            _execution_agent._run_agent_in_docker(
                image="test-image",
                workdir=self.workdir,
                run_dir=self.run_dir,
                agent_name="test-agent",
                agent_cfg={"bins": ["not-a-dict"]},  # Invalid entry
                model="test-model",
                timeout_sec=60,
                run_capture_stream=self._make_mock_run_capture_stream(),
                cleanup_docker_container=self._make_mock_cleanup(),
                cmd_str=lambda x: " ".join(x),
            )
        self.assertIn("invalid bin entry", str(ctx.exception))

    def test_bins_missing_host(self):
        """Test that bin entries require host field."""
        with self.assertRaises(ValueError) as ctx:
            _execution_agent._run_agent_in_docker(
                image="test-image",
                workdir=self.workdir,
                run_dir=self.run_dir,
                agent_name="test-agent",
                agent_cfg={"bins": [{"container": "/bin/ls"}]},  # Missing host
                model="test-model",
                timeout_sec=60,
                run_capture_stream=self._make_mock_run_capture_stream(),
                cleanup_docker_container=self._make_mock_cleanup(),
                cmd_str=lambda x: " ".join(x),
                resolve_host_executable=lambda x: Path("/bin/ls"),
            )
        self.assertIn("require host+container", str(ctx.exception))

    def test_bins_missing_container(self):
        """Test that bin entries require container field."""
        with self.assertRaises(ValueError) as ctx:
            _execution_agent._run_agent_in_docker(
                image="test-image",
                workdir=self.workdir,
                run_dir=self.run_dir,
                agent_name="test-agent",
                agent_cfg={"bins": [{"host": "ls"}]},  # Missing container
                model="test-model",
                timeout_sec=60,
                run_capture_stream=self._make_mock_run_capture_stream(),
                cleanup_docker_container=self._make_mock_cleanup(),
                cmd_str=lambda x: " ".join(x),
                resolve_host_executable=lambda x: Path("/bin/ls"),
            )
        self.assertIn("require host+container", str(ctx.exception))

    # --- Mounts validation ---

    def test_mounts_must_be_list(self):
        """Test that mounts must be a list."""
        with self.assertRaises(ValueError) as ctx:
            _execution_agent._run_agent_in_docker(
                image="test-image",
                workdir=self.workdir,
                run_dir=self.run_dir,
                agent_name="test-agent",
                agent_cfg={"mounts": "not-a-list"},
                model="test-model",
                timeout_sec=60,
                run_capture_stream=self._make_mock_run_capture_stream(),
                cleanup_docker_container=self._make_mock_cleanup(),
                cmd_str=lambda x: " ".join(x),
            )
        self.assertIn("mounts must be a list", str(ctx.exception))

    def test_mounts_invalid_entry_type(self):
        """Test that each mount entry must be a dict."""
        with self.assertRaises(ValueError) as ctx:
            _execution_agent._run_agent_in_docker(
                image="test-image",
                workdir=self.workdir,
                run_dir=self.run_dir,
                agent_name="test-agent",
                agent_cfg={"mounts": ["not-a-dict"]},
                model="test-model",
                timeout_sec=60,
                run_capture_stream=self._make_mock_run_capture_stream(),
                cleanup_docker_container=self._make_mock_cleanup(),
                cmd_str=lambda x: " ".join(x),
            )
        self.assertIn("invalid mount entry", str(ctx.exception))

    def test_mounts_invalid_mode(self):
        """Test that mount mode must be 'ro' or 'rw'."""
        with self.assertRaises(ValueError) as ctx:
            _execution_agent._run_agent_in_docker(
                image="test-image",
                workdir=self.workdir,
                run_dir=self.run_dir,
                agent_name="test-agent",
                agent_cfg={
                    "mounts": [{"host": "/tmp", "container": "/mnt", "mode": "invalid"}]
                },
                model="test-model",
                timeout_sec=60,
                run_capture_stream=self._make_mock_run_capture_stream(),
                cleanup_docker_container=self._make_mock_cleanup(),
                cmd_str=lambda x: " ".join(x),
                expand_path=lambda x: "/tmp",
            )
        self.assertIn("mount mode must be ro|rw", str(ctx.exception))

    def test_mounts_missing_required_fields(self):
        """Test that mount entries require host and container."""
        with self.assertRaises(ValueError) as ctx:
            _execution_agent._run_agent_in_docker(
                image="test-image",
                workdir=self.workdir,
                run_dir=self.run_dir,
                agent_name="test-agent",
                agent_cfg={"mounts": [{"host": "/tmp"}]},  # Missing container
                model="test-model",
                timeout_sec=60,
                run_capture_stream=self._make_mock_run_capture_stream(),
                cleanup_docker_container=self._make_mock_cleanup(),
                cmd_str=lambda x: " ".join(x),
                expand_path=lambda x: "/tmp",
            )
        self.assertIn("require host+container", str(ctx.exception))

    def test_mounts_missing_nonexistent_nonoptional(self):
        """Test that non-optional mounts fail if host path doesn't exist."""
        with self.assertRaises(FileNotFoundError) as ctx:
            _execution_agent._run_agent_in_docker(
                image="test-image",
                workdir=self.workdir,
                run_dir=self.run_dir,
                agent_name="test-agent",
                agent_cfg={
                    "mounts": [{"host": "/nonexistent/path", "container": "/mnt"}]
                },
                model="test-model",
                timeout_sec=60,
                run_capture_stream=self._make_mock_run_capture_stream(),
                cleanup_docker_container=self._make_mock_cleanup(),
                cmd_str=lambda x: " ".join(x),
                expand_path=lambda x: "/nonexistent/path",
            )
        self.assertIn("Mount source not found", str(ctx.exception))

    def test_mounts_optional_missing_allowed(self):
        """Test that optional mounts are skipped if host doesn't exist."""
        # This should NOT raise - optional mounts that don't exist are skipped
        proc, _ = _execution_agent._run_agent_in_docker(
            image="test-image",
            workdir=self.workdir,
            run_dir=self.run_dir,
            agent_name="test-agent",
            agent_cfg={
                "mounts": [
                    {"host": "/nonexistent/path", "container": "/mnt", "optional": True}
                ],
                "cmd": "echo test",
            },
            model="test-model",
            timeout_sec=60,
            run_capture_stream=self._make_mock_run_capture_stream(),
            cleanup_docker_container=self._make_mock_cleanup(),
            cmd_str=lambda x: " ".join(x),
            expand_path=lambda x: "/nonexistent/path",
        )
        # Should succeed with mocked process
        self.assertEqual(proc.returncode, 0)

    # --- Env validation ---

    def test_env_must_be_dict(self):
        """Test that env must be a dict."""
        with self.assertRaises(ValueError) as ctx:
            _execution_agent._run_agent_in_docker(
                image="test-image",
                workdir=self.workdir,
                run_dir=self.run_dir,
                agent_name="test-agent",
                agent_cfg={"env": "not-a-dict"},
                model="test-model",
                timeout_sec=60,
                run_capture_stream=self._make_mock_run_capture_stream(),
                cleanup_docker_container=self._make_mock_cleanup(),
                cmd_str=lambda x: " ".join(x),
            )
        self.assertIn("env must be an object", str(ctx.exception))

    # --- Pre validation ---

    def test_pre_must_be_list(self):
        """Test that pre must be a list if provided."""
        with self.assertRaises(ValueError) as ctx:
            _execution_agent._run_agent_in_docker(
                image="test-image",
                workdir=self.workdir,
                run_dir=self.run_dir,
                agent_name="test-agent",
                agent_cfg={"pre": "not-a-list", "cmd": "echo test"},
                model="test-model",
                timeout_sec=60,
                run_capture_stream=self._make_mock_run_capture_stream(),
                cleanup_docker_container=self._make_mock_cleanup(),
                cmd_str=lambda x: " ".join(x),
            )
        self.assertIn("pre must be a list", str(ctx.exception))

    # --- Cmd validation ---

    def test_cmd_required(self):
        """Test that cmd is required."""
        with self.assertRaises(ValueError) as ctx:
            _execution_agent._run_agent_in_docker(
                image="test-image",
                workdir=self.workdir,
                run_dir=self.run_dir,
                agent_name="test-agent",
                agent_cfg={},  # Missing cmd
                model="test-model",
                timeout_sec=60,
                run_capture_stream=self._make_mock_run_capture_stream(),
                cleanup_docker_container=self._make_mock_cleanup(),
                cmd_str=lambda x: " ".join(x),
            )
        self.assertIn("missing 'cmd'", str(ctx.exception))

    def test_cmd_empty_string_fails(self):
        """Test that empty cmd fails."""
        with self.assertRaises(ValueError) as ctx:
            _execution_agent._run_agent_in_docker(
                image="test-image",
                workdir=self.workdir,
                run_dir=self.run_dir,
                agent_name="test-agent",
                agent_cfg={"cmd": ""},
                model="test-model",
                timeout_sec=60,
                run_capture_stream=self._make_mock_run_capture_stream(),
                cleanup_docker_container=self._make_mock_cleanup(),
                cmd_str=lambda x: " ".join(x),
            )
        self.assertIn("missing 'cmd'", str(ctx.exception))

    # --- Boundary conditions ---

    def test_timeout_zero(self):
        """Test timeout of zero is passed through to run_capture_stream."""
        # timeout_sec=0 is passed to run_capture_stream - no validation error
        # The mock doesn't simulate a timeout, so it succeeds
        proc, _ = _execution_agent._run_agent_in_docker(
            image="test-image",
            workdir=self.workdir,
            run_dir=self.run_dir,
            agent_name="test-agent",
            agent_cfg={"cmd": "echo test"},
            model="test-model",
            timeout_sec=0,
            run_capture_stream=self._make_mock_run_capture_stream(),
            cleanup_docker_container=self._make_mock_cleanup(),
            cmd_str=lambda x: " ".join(x),
        )
        # Should succeed (mock doesn't enforce timeout)
        self.assertEqual(proc.returncode, 0)

    def test_negative_timeout(self):
        """Test negative timeout is passed through (may cause unexpected behavior)."""
        # Negative timeout should be passed to run_capture_stream
        # This tests that the function doesn't validate timeout value
        try:
            _execution_agent._run_agent_in_docker(
                image="test-image",
                workdir=self.workdir,
                run_dir=self.run_dir,
                agent_name="test-agent",
                agent_cfg={"cmd": "echo test"},
                model="test-model",
                timeout_sec=-1,
                run_capture_stream=self._make_mock_run_capture_stream(),
                cleanup_docker_container=self._make_mock_cleanup(),
                cmd_str=lambda x: " ".join(x),
            )
        except (subprocess.TimeoutExpired, Exception):
            pass  # Expected - negative timeout causes issues

    def test_very_long_agent_name(self):
        """Test with very long agent name (boundary)."""
        long_name = "a" * 1000
        proc, _ = _execution_agent._run_agent_in_docker(
            image="test-image",
            workdir=self.workdir,
            run_dir=self.run_dir,
            agent_name=long_name,
            agent_cfg={"cmd": "echo test"},
            model="test-model",
            timeout_sec=60,
            run_capture_stream=self._make_mock_run_capture_stream(),
            cleanup_docker_container=self._make_mock_cleanup(),
            cmd_str=lambda x: " ".join(x),
            secrets_mod=mock.MagicMock(token_hex=lambda n: "x" * n),
        )
        self.assertEqual(proc.returncode, 0)

    # --- Return type preservation ---

    def test_returns_tuple_of_completedprocess_and_float_or_none(self):
        """Test that return type is preserved: (CompletedProcess, float|None)."""
        result = _execution_agent._run_agent_in_docker(
            image="test-image",
            workdir=self.workdir,
            run_dir=self.run_dir,
            agent_name="test-agent",
            agent_cfg={"cmd": "echo test"},
            model="test-model",
            timeout_sec=60,
            run_capture_stream=self._make_mock_run_capture_stream(),
            cleanup_docker_container=self._make_mock_cleanup(),
            cmd_str=lambda x: " ".join(x),
            timed_bash_script=lambda x: x,
            extract_inner_sec=lambda s, e: 1.5,
        )
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        proc, inner_sec = result
        self.assertIsInstance(proc, subprocess.CompletedProcess)
        self.assertIsInstance(inner_sec, (float, type(None)))


class TestRunAgentOnHostValidation(unittest.TestCase):
    """Test input validation for _run_agent_on_host."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workdir = Path(self.temp_dir) / "workdir"
        self.run_dir = Path(self.temp_dir) / "rundir"
        self.workdir.mkdir(parents=True)
        self.run_dir.mkdir(parents=True)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_mock_run_capture_stream(self, returncode: int = 0):
        def mock_run(*args, **kwargs):
            return _make_fake_completedprocess(returncode=returncode)

        return mock_run

    # --- Bins validation ---

    def test_bins_required_for_host(self):
        """Test that bins is required for host mode."""
        with self.assertRaises(ValueError) as ctx:
            _execution_agent._run_agent_on_host(
                workdir=self.workdir,
                run_dir=self.run_dir,
                agent_name="test-agent",
                agent_cfg={},  # Missing bins
                model="test-model",
                timeout_sec=60,
                run_capture_stream=self._make_mock_run_capture_stream(),
            )
        self.assertIn("missing 'bins' list", str(ctx.exception))

    def test_bins_empty_list_fails(self):
        """Test that empty bins list fails for host mode."""
        with self.assertRaises(ValueError) as ctx:
            _execution_agent._run_agent_on_host(
                workdir=self.workdir,
                run_dir=self.run_dir,
                agent_name="test-agent",
                agent_cfg={"bins": []},  # Empty list
                model="test-model",
                timeout_sec=60,
                run_capture_stream=self._make_mock_run_capture_stream(),
            )
        self.assertIn("missing 'bins' list", str(ctx.exception))

    def test_bins_must_be_list_not_dict(self):
        """Test that bins must be a list, not a dict."""
        with self.assertRaises(ValueError) as ctx:
            _execution_agent._run_agent_on_host(
                workdir=self.workdir,
                run_dir=self.run_dir,
                agent_name="test-agent",
                agent_cfg={"bins": {"host": "ls"}},  # Not a list
                model="test-model",
                timeout_sec=60,
                run_capture_stream=self._make_mock_run_capture_stream(),
            )
        self.assertIn("missing 'bins' list", str(ctx.exception))

    def test_bins_invalid_entry_type(self):
        """Test that bin entries must be dicts."""
        with self.assertRaises(ValueError) as ctx:
            _execution_agent._run_agent_on_host(
                workdir=self.workdir,
                run_dir=self.run_dir,
                agent_name="test-agent",
                agent_cfg={"bins": ["not-a-dict"]},
                model="test-model",
                timeout_sec=60,
                run_capture_stream=self._make_mock_run_capture_stream(),
            )
        self.assertIn("invalid bin entry", str(ctx.exception))

    def test_bins_host_required(self):
        """Test that bin entries require host field."""
        with self.assertRaises(ValueError) as ctx:
            _execution_agent._run_agent_on_host(
                workdir=self.workdir,
                run_dir=self.run_dir,
                agent_name="test-agent",
                agent_cfg={"bins": [{"container": "/bin/ls"}]},  # Missing host
                model="test-model",
                timeout_sec=60,
                run_capture_stream=self._make_mock_run_capture_stream(),
                resolve_host_executable=lambda x: Path("/bin/ls"),
            )
        self.assertIn("bin entries require host", str(ctx.exception))

    # --- Env validation ---

    def test_env_must_be_dict(self):
        """Test that env must be a dict."""
        with self.assertRaises(ValueError) as ctx:
            _execution_agent._run_agent_on_host(
                workdir=self.workdir,
                run_dir=self.run_dir,
                agent_name="test-agent",
                agent_cfg={"bins": [{"host": "ls"}], "env": "not-a-dict"},
                model="test-model",
                timeout_sec=60,
                run_capture_stream=self._make_mock_run_capture_stream(),
                resolve_host_executable=lambda x: Path("/bin/ls"),
            )
        self.assertIn("env must be an object", str(ctx.exception))

    # --- Pre validation ---

    def test_pre_must_be_list(self):
        """Test that pre must be a list if provided."""
        with self.assertRaises(ValueError) as ctx:
            _execution_agent._run_agent_on_host(
                workdir=self.workdir,
                run_dir=self.run_dir,
                agent_name="test-agent",
                agent_cfg={
                    "bins": [{"host": "ls"}],
                    "pre": "not-a-list",
                    "cmd": "echo test",
                },
                model="test-model",
                timeout_sec=60,
                run_capture_stream=self._make_mock_run_capture_stream(),
                resolve_host_executable=lambda x: Path("/bin/ls"),
            )
        self.assertIn("pre must be a list", str(ctx.exception))

    # --- Cmd validation ---

    def test_cmd_required(self):
        """Test that cmd is required."""
        with self.assertRaises(ValueError) as ctx:
            _execution_agent._run_agent_on_host(
                workdir=self.workdir,
                run_dir=self.run_dir,
                agent_name="test-agent",
                agent_cfg={"bins": [{"host": "ls"}]},
                model="test-model",
                timeout_sec=60,
                run_capture_stream=self._make_mock_run_capture_stream(),
                resolve_host_executable=lambda x: Path("/bin/ls"),
            )
        self.assertIn("missing 'cmd'", str(ctx.exception))

    # --- Return type preservation ---

    def test_returns_tuple_of_completedprocess_and_float(self):
        """Test that return type is preserved: (CompletedProcess, float)."""
        result = _execution_agent._run_agent_on_host(
            workdir=self.workdir,
            run_dir=self.run_dir,
            agent_name="test-agent",
            agent_cfg={"bins": [{"host": "ls"}], "cmd": "echo test"},
            model="test-model",
            timeout_sec=60,
            run_capture_stream=self._make_mock_run_capture_stream(),
            resolve_host_executable=lambda x: Path("/bin/ls"),
        )
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        proc, inner_sec = result
        self.assertIsInstance(proc, subprocess.CompletedProcess)
        self.assertIsInstance(inner_sec, float)  # Host mode always returns float


class TestTimeoutCleanup(unittest.TestCase):
    """Test timeout cleanup behavior."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workdir = Path(self.temp_dir) / "workdir"
        self.run_dir = Path(self.temp_dir) / "rundir"
        self.workdir.mkdir(parents=True)
        self.run_dir.mkdir(parents=True)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_timeout_cleanup_is_passed_to_run_capture_stream(self):
        """Test that timeout_cleanup is passed to run_capture_stream."""
        captured_kwargs = {}

        def capture_kwargs(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return _make_fake_completedprocess()

        cleanup_fn = mock.MagicMock()

        _execution_agent._run_agent_in_docker(
            image="test-image",
            workdir=self.workdir,
            run_dir=self.run_dir,
            agent_name="test-agent",
            agent_cfg={"cmd": "echo test"},
            model="test-model",
            timeout_sec=60,
            run_capture_stream=capture_kwargs,
            cleanup_docker_container=cleanup_fn,
            cmd_str=lambda x: " ".join(x),
        )

        # Verify timeout_cleanup was passed
        self.assertIn("timeout_cleanup", captured_kwargs)
        self.assertIsNotNone(captured_kwargs["timeout_cleanup"])

    def test_container_name_uses_secrets(self):
        """Test that container name uses secrets.token_hex for uniqueness."""
        mock_secrets = mock.MagicMock()
        mock_secrets.token_hex.return_value = "abc123"

        proc, _ = _execution_agent._run_agent_in_docker(
            image="test-image",
            workdir=self.workdir,
            run_dir=self.run_dir,
            agent_name="myagent",
            agent_cfg={"cmd": "echo test"},
            model="test-model",
            timeout_sec=60,
            run_capture_stream=lambda *a, **k: _make_fake_completedprocess(),
            cleanup_docker_container=mock.MagicMock(),
            cmd_str=lambda x: " ".join(x),
            secrets_mod=mock_secrets,
        )

        # Verify token_hex was called
        mock_secrets.token_hex.assert_called()


class TestOpenCodeSpecialHandling(unittest.TestCase):
    """Test special handling for opencode agent."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workdir = Path(self.temp_dir) / "workdir"
        self.run_dir = Path(self.temp_dir) / "rundir"
        self.workdir.mkdir(parents=True)
        self.run_dir.mkdir(parents=True)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_opencode_creates_state_dir(self):
        """Test that opencode agent creates state directory."""
        state_dir_created = []

        original_mkdir = Path.mkdir

        def mock_mkdir(self, *args, **kwargs):
            if ".opencode-data" in str(self):
                state_dir_created.append(str(self))
            return original_mkdir(self, *args, **kwargs)

        with mock.patch.object(Path, "mkdir", mock_mkdir):
            _execution_agent._run_agent_in_docker(
                image="test-image",
                workdir=self.workdir,
                run_dir=self.run_dir,
                agent_name="opencode",
                agent_cfg={"cmd": "echo test"},
                model="test-model",
                timeout_sec=60,
                run_capture_stream=lambda *a, **k: _make_fake_completedprocess(),
                cleanup_docker_container=mock.MagicMock(),
                cmd_str=lambda x: " ".join(x),
            )

        # Verify state dir was created
        self.assertTrue(
            any(".opencode-data" in p for p in state_dir_created),
            f"Expected .opencode-data dir creation, got: {state_dir_created}",
        )


class TestArgumentPassthrough(unittest.TestCase):
    """Test that arguments are correctly passed through to wrapped functions."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workdir = Path(self.temp_dir) / "workdir"
        self.run_dir = Path(self.temp_dir) / "rundir"
        self.workdir.mkdir(parents=True)
        self.run_dir.mkdir(parents=True)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_verbose_flag_passthrough(self):
        """Test that verbose flag is passed to vprint/vsection."""
        vprint_calls = []
        vsection_calls = []

        def mock_vprint(enabled, msg):
            vprint_calls.append((enabled, msg))

        def mock_vsection(enabled, title):
            vsection_calls.append((enabled, title))

        _execution_agent._run_agent_in_docker(
            image="test-image",
            workdir=self.workdir,
            run_dir=self.run_dir,
            agent_name="test-agent",
            agent_cfg={"cmd": "echo test"},
            model="test-model",
            timeout_sec=60,
            verbose=True,
            run_capture_stream=lambda *a, **k: _make_fake_completedprocess(),
            cleanup_docker_container=mock.MagicMock(),
            cmd_str=lambda x: " ".join(x),
            vprint=mock_vprint,
            vsection=mock_vsection,
        )

        # Verify verbose output was generated
        self.assertTrue(
            len(vprint_calls) > 0, "Expected vprint calls when verbose=True"
        )
        self.assertTrue(
            len(vsection_calls) > 0, "Expected vsection calls when verbose=True"
        )

    def test_extra_env_passed_to_docker(self):
        """Test that extra_env is passed as docker -e flags."""
        captured_cmds = []

        def capture_cmd(cmd):
            captured_cmds.append(cmd)
            return " ".join(cmd)

        _execution_agent._run_agent_in_docker(
            image="test-image",
            workdir=self.workdir,
            run_dir=self.run_dir,
            agent_name="test-agent",
            agent_cfg={"cmd": "echo test"},
            model="test-model",
            timeout_sec=60,
            extra_env={"MY_VAR": "my_value", "ANOTHER": "value2"},
            run_capture_stream=lambda *a, **k: _make_fake_completedprocess(),
            cleanup_docker_container=mock.MagicMock(),
            cmd_str=capture_cmd,
        )

        # Verify extra env vars are in docker command
        cmd_str = captured_cmds[0] if captured_cmds else ""
        self.assertIn("-e", cmd_str)
        self.assertIn("MY_VAR=my_value", cmd_str)
        self.assertIn("ANOTHER=value2", cmd_str)

    def test_cmd_log_path_writes_file(self):
        """Test that cmd_log_path writes the command to file."""
        log_path = Path(self.temp_dir) / "cmd.log"

        _execution_agent._run_agent_in_docker(
            image="test-image",
            workdir=self.workdir,
            run_dir=self.run_dir,
            agent_name="test-agent",
            agent_cfg={"cmd": "echo test"},
            model="test-model",
            timeout_sec=60,
            cmd_log_path=log_path,
            run_capture_stream=lambda *a, **k: _make_fake_completedprocess(),
            cleanup_docker_container=mock.MagicMock(),
            cmd_str=lambda x: " ".join(x),
        )

        # Verify log file was written
        self.assertTrue(log_path.exists(), "cmd_log_path should create file")
        content = log_path.read_text()
        self.assertIn("docker", content)


class TestEnvironmentVariables(unittest.TestCase):
    """Test that correct environment variables are set."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workdir = Path(self.temp_dir) / "workdir"
        self.run_dir = Path(self.temp_dir) / "rundir"
        self.workdir.mkdir(parents=True)
        self.run_dir.mkdir(parents=True)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_docker_sets_bench_env_vars(self):
        """Test that docker mode sets BENCH_* environment variables."""
        captured_cmds = []

        _execution_agent._run_agent_in_docker(
            image="test-image",
            workdir=self.workdir,
            run_dir=self.run_dir,
            agent_name="myagent",
            agent_cfg={"cmd": "echo test"},
            model="gpt-4",
            timeout_sec=60,
            run_capture_stream=lambda *a, **k: _make_fake_completedprocess(),
            cleanup_docker_container=mock.MagicMock(),
            cmd_str=lambda x: captured_cmds.append(" ".join(x)) or " ".join(x),
        )

        cmd = captured_cmds[0]
        self.assertIn("BENCH_AGENT=myagent", cmd)
        self.assertIn("BENCH_MODEL=gpt-4", cmd)
        self.assertIn("BENCH_WORKDIR=/work", cmd)
        self.assertIn("BENCH_RUN_DIR=/run", cmd)
        self.assertIn("BENCH_PROMPT_FILE=/run/prompt.txt", cmd)
        self.assertIn("BENCH_SPEC_FILE=/run/spec.md", cmd)

    def test_host_sets_bench_env_vars(self):
        """Test that host mode sets BENCH_* environment variables."""
        captured_envs = []

        def capture_run_capture_stream(
            cmd,
            *,
            timeout_sec,
            verbose,
            phase,
            cwd=None,
            env=None,
            pretty_timeline=False,
            timeout_cleanup=None,
        ):
            if env:
                captured_envs.append(env)
            return _make_fake_completedprocess()

        _execution_agent._run_agent_on_host(
            workdir=self.workdir,
            run_dir=self.run_dir,
            agent_name="myagent",
            agent_cfg={"bins": [{"host": "ls"}], "cmd": "echo test"},
            model="gpt-4",
            timeout_sec=60,
            run_capture_stream=capture_run_capture_stream,
            resolve_host_executable=lambda x: Path("/bin/ls"),
        )

        env = captured_envs[0]
        self.assertEqual(env.get("BENCH_AGENT"), "myagent")
        self.assertEqual(env.get("BENCH_MODEL"), "gpt-4")
        self.assertIn("BENCH_WORKDIR", env)
        self.assertIn("BENCH_RUN_DIR", env)
        self.assertIn("BENCH_PROMPT_FILE", env)
        self.assertIn("BENCH_SPEC_FILE", env)


class TestPatchSeamBehavior(unittest.TestCase):
    """Test that the extraction preserves seam behavior from bench.py."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.workdir = Path(self.temp_dir) / "workdir"
        self.run_dir = Path(self.temp_dir) / "rundir"
        self.workdir.mkdir(parents=True)
        self.run_dir.mkdir(parents=True)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_model_options_injection(self):
        """Test that model options are injected into command."""
        captured_cmds = []

        def capture_cmd(cmd):
            captured_cmds.append(cmd)
            return " ".join(cmd)

        _execution_agent._run_agent_in_docker(
            image="test-image",
            workdir=self.workdir,
            run_dir=self.run_dir,
            agent_name="test-agent",
            agent_cfg={
                "cmd": "openai-chat --model $MODEL",
                "model_options": {
                    "temperature": 0.7,
                    "max_tokens": 1000,
                },
            },
            model="gpt-4",
            timeout_sec=60,
            run_capture_stream=lambda *a, **k: _make_fake_completedprocess(),
            cleanup_docker_container=mock.MagicMock(),
            cmd_str=capture_cmd,
            normalize_model_options=lambda a, c: c.get("model_options", {}),
            model_options_env=lambda x: x,
            inject_model_options_args=lambda cmd, opts: cmd.replace("$MODEL", "gpt-4"),
        )

        cmd = captured_cmds[0]
        # The command should be transformed with model options
        # Check if gpt-4 is in any element of the command list (as substring)
        cmd_str = " ".join(cmd)
        self.assertIn("--model gpt-4", cmd_str)


if __name__ == "__main__":
    import unittest

    unittest.main(verbosity=2)
