from __future__ import annotations

import os
import secrets
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

try:
    from runner import execution_helpers as _execution_helpers
except ModuleNotFoundError:  # pragma: no cover
    import execution_helpers as _execution_helpers  # type: ignore[no-redef]


_cmd_str = _execution_helpers._cmd_str
_timed_bash_script = _execution_helpers._timed_bash_script
_extract_inner_sec = _execution_helpers._extract_inner_sec


def _vprint(enabled: bool, msg: str) -> None:
    if enabled:
        print(msg, file=sys.stderr)


def _vsection(enabled: bool, title: str) -> None:
    if enabled:
        print(f"\n=== {title} ===", file=sys.stderr)


def _uid_gid() -> tuple[int, int]:
    uid = os.getuid() if hasattr(os, "getuid") else 1000
    gid = os.getgid() if hasattr(os, "getgid") else 1000
    return uid, gid


def _docker_run_base_cmd(*, uid: int, gid: int, workdir: Path) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "-u",
        f"{uid}:{gid}",
        "-e",
        "HOME=/tmp",
        "-e",
        "OMP_NUM_THREADS=1",
        "-e",
        "OPENBLAS_NUM_THREADS=1",
        "-e",
        "MKL_NUM_THREADS=1",
        "-e",
        "VECLIB_MAXIMUM_THREADS=1",
        "-e",
        "NUMEXPR_NUM_THREADS=1",
        "-v",
        f"{str(workdir)}:/work:rw",
        "-w",
        "/work",
    ]


def _run_docker_eval(
    *,
    image: str,
    workdir: Path,
    eval_dir: Path,
    eval_cmd: str,
    shared_eval_dir: Path | None,
    timeout_sec: int,
    extra_env: dict[str, str] | None = None,
    verbose: bool = False,
    cmd_log_path: Path | None = None,
    run_capture_stream: Callable[..., subprocess.CompletedProcess],
    cleanup_docker_container: Callable[..., None],
    cmd_str: Callable[[list[str]], str] = _cmd_str,
    timed_bash_script: Callable[[str], str] = _timed_bash_script,
    extract_inner_sec: Callable[..., float | None] = _extract_inner_sec,
    subprocess_mod: Any = subprocess,
) -> tuple[subprocess.CompletedProcess, float | None]:
    uid, gid = _uid_gid()

    container_name = f"simbench-eval-{secrets.token_hex(6)}"
    docker_cmd = [
        "docker",
        "run",
        "--rm",
        "--name",
        container_name,
        "-u",
        f"{uid}:{gid}",
        "-e",
        "HOME=/tmp",
        "-e",
        "OMP_NUM_THREADS=1",
        "-e",
        "OPENBLAS_NUM_THREADS=1",
        "-e",
        "MKL_NUM_THREADS=1",
        "-e",
        "VECLIB_MAXIMUM_THREADS=1",
        "-e",
        "NUMEXPR_NUM_THREADS=1",
        "-v",
        f"{str(workdir)}:/work:rw",
        "-v",
        f"{str(eval_dir)}:/eval:ro",
        "-w",
        "/work",
    ]
    if shared_eval_dir is not None:
        docker_cmd += ["-v", f"{str(shared_eval_dir)}:/eval_shared:ro"]
    if extra_env:
        for key, value in extra_env.items():
            docker_cmd += ["-e", f"{key}={value}"]

    docker_cmd += [image, "bash", "-lc", timed_bash_script(eval_cmd)]

    if cmd_log_path is not None:
        cmd_log_path.write_text(cmd_str(docker_cmd) + "\n", encoding="utf-8")
    _vsection(verbose, "EVAL PHASE")
    _vprint(verbose, "[eval] command:")
    _vprint(verbose, cmd_str(docker_cmd))
    _vprint(verbose, "[eval] output:")

    proc = run_capture_stream(
        docker_cmd,
        timeout_sec=timeout_sec,
        verbose=verbose,
        phase="eval",
        timeout_cleanup=lambda: cleanup_docker_container(
            container_name=container_name,
            phase="eval",
            verbose=verbose,
        ),
    )
    return proc, extract_inner_sec(proc.stdout, proc.stderr)


def _run_docker_shell(
    *,
    image: str,
    workdir: Path,
    cmd: list[str],
    subprocess_mod: Any = subprocess,
) -> int:
    uid, gid = _uid_gid()
    docker_cmd = _docker_run_base_cmd(uid=uid, gid=gid, workdir=workdir)
    if cmd == ["bash"]:
        docker_cmd += ["-it"]

    docker_cmd += [image] + cmd
    return subprocess_mod.call(docker_cmd)
