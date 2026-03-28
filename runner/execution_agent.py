from __future__ import annotations

import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

try:
    from runner import config_helpers as _config_helpers
except ModuleNotFoundError:  # pragma: no cover
    import config_helpers as _config_helpers  # type: ignore[no-redef]

try:
    from runner import execution_helpers as _execution_helpers
except ModuleNotFoundError:  # pragma: no cover
    import execution_helpers as _execution_helpers  # type: ignore[no-redef]


_normalize_model_options = _config_helpers._normalize_model_options
_model_options_env = _config_helpers._model_options_env
_inject_model_options_args = _config_helpers._inject_model_options_args
_resolve_host_executable = _config_helpers._resolve_host_executable
_expand_path = _config_helpers._expand_path

_cmd_str = _execution_helpers._cmd_str
_timed_bash_script = _execution_helpers._timed_bash_script
_extract_inner_sec = _execution_helpers._extract_inner_sec


def _vprint(enabled: bool, msg: str) -> None:
    if enabled:
        print(msg, file=sys.stderr)


def _vsection(enabled: bool, title: str) -> None:
    if enabled:
        print(f"\n=== {title} ===", file=sys.stderr)


def _opencode_state_dir(run_dir: Path) -> Path:
    return run_dir / ".opencode-data"


def _run_agent_in_docker(
    *,
    image: str,
    workdir: Path,
    run_dir: Path,
    agent_name: str,
    agent_cfg: dict[str, Any],
    model: str,
    timeout_sec: int,
    extra_env: dict[str, str] | None = None,
    verbose: bool = False,
    cmd_log_path: Path | None = None,
    run_capture_stream: Callable[
        ..., subprocess.CompletedProcess
    ] = _execution_helpers._run_capture_stream,
    cleanup_docker_container: Callable[
        ..., None
    ] = _execution_helpers._cleanup_docker_container,
    cmd_str: Callable[[list[str]], str] = _cmd_str,
    timed_bash_script: Callable[[str], str] = _timed_bash_script,
    extract_inner_sec: Callable[..., float | None] = _extract_inner_sec,
    normalize_model_options: Callable[
        [str, dict[str, Any]], Any
    ] = _normalize_model_options,
    model_options_env: Callable[[Any], dict[str, str]] = _model_options_env,
    inject_model_options_args: Callable[[str, Any], str] = _inject_model_options_args,
    resolve_host_executable: Callable[[str], Path] = _resolve_host_executable,
    expand_path: Callable[[str], str] = _expand_path,
    vprint: Callable[[bool, str], None] = _vprint,
    vsection: Callable[[bool, str], None] = _vsection,
    subprocess_mod: Any = subprocess,
    os_mod: Any = os,
    secrets_mod: Any = secrets,
) -> tuple[subprocess.CompletedProcess, float | None]:
    uid = os_mod.getuid() if hasattr(os_mod, "getuid") else 1000
    gid = os_mod.getgid() if hasattr(os_mod, "getgid") else 1000

    container_name = f"simbench-agent-{agent_name}-{secrets_mod.token_hex(6)}"
    docker_cmd: list[str] = [
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
        "-e",
        f"BENCH_AGENT={agent_name}",
        "-e",
        f"BENCH_MODEL={model}",
        "-e",
        "BENCH_WORKDIR=/work",
        "-e",
        "BENCH_RUN_DIR=/run",
        "-e",
        "BENCH_PROMPT_FILE=/run/prompt.txt",
        "-e",
        "BENCH_SPEC_FILE=/run/spec.md",
        "-v",
        f"{str(workdir)}:/work:rw",
        "-v",
        f"{str(run_dir)}:/run:ro",
        "-w",
        "/work",
    ]
    if agent_name == "opencode":
        opencode_state_dir = _opencode_state_dir(run_dir)
        opencode_state_dir.mkdir(parents=True, exist_ok=True)
        docker_cmd += [
            "-e",
            "XDG_DATA_HOME=/opencode-data",
            "-v",
            f"{str(opencode_state_dir)}:/opencode-data:rw",
        ]
    model_options = normalize_model_options(agent_name, agent_cfg)
    for k, v in model_options_env(model_options).items():
        docker_cmd += ["-e", f"{k}={v}"]

    bins = agent_cfg.get("bins", [])
    if not isinstance(bins, list):
        raise ValueError(f"Agent {agent_name!r} bins must be a list")
    for b in bins:
        if not isinstance(b, dict):
            raise ValueError(f"Agent {agent_name!r} has invalid bin entry")
        host = str(b.get("host", "")).strip()
        container = str(b.get("container", "")).strip()
        if not host or not container:
            raise ValueError(f"Agent {agent_name!r} bin entries require host+container")
        host_path = resolve_host_executable(host)
        docker_cmd += ["-v", f"{str(host_path)}:{container}:ro"]

    mounts = agent_cfg.get("mounts", [])
    if mounts:
        if not isinstance(mounts, list):
            raise ValueError(f"Agent {agent_name!r} mounts must be a list")
        for m in mounts:
            if not isinstance(m, dict):
                raise ValueError(f"Agent {agent_name!r} has invalid mount entry")
            host = str(m.get("host", "")).strip()
            container = str(m.get("container", "")).strip()
            mode = str(m.get("mode", "ro")).strip()
            optional = bool(m.get("optional", False))
            if not host or not container:
                raise ValueError(
                    f"Agent {agent_name!r} mount entries require host+container"
                )
            if mode not in ("ro", "rw"):
                raise ValueError(f"Agent {agent_name!r} mount mode must be ro|rw")

            host_path = Path(expand_path(host))
            if not host_path.exists():
                if optional:
                    continue
                raise FileNotFoundError(f"Mount source not found: {host_path}")
            docker_cmd += ["-v", f"{str(host_path.resolve())}:{container}:{mode}"]

    env_kv = agent_cfg.get("env", {})
    if env_kv:
        if not isinstance(env_kv, dict):
            raise ValueError(f"Agent {agent_name!r} env must be an object")
        for k, v in env_kv.items():
            docker_cmd += ["-e", f"{k}={v}"]

    if extra_env:
        for k, v in extra_env.items():
            docker_cmd += ["-e", f"{k}={v}"]

    pre = agent_cfg.get("pre", [])
    cmd = str(agent_cfg.get("cmd", "")).strip()
    if not cmd:
        raise ValueError(f"Agent {agent_name!r} missing 'cmd'")
    if pre and not isinstance(pre, list):
        raise ValueError(f"Agent {agent_name!r} pre must be a list")
    cmd = inject_model_options_args(cmd, model_options)

    inner_parts: list[str] = []
    inner_parts.append('test -f "$BENCH_PROMPT_FILE"')
    inner_parts.append('test -f "$BENCH_SPEC_FILE"')
    for part in pre:
        inner_parts.append(str(part))
    inner_parts.append(timed_bash_script(cmd))
    docker_cmd += [image, "bash", "-lc", " && ".join(inner_parts)]

    if cmd_log_path is not None:
        cmd_log_path.write_text(cmd_str(docker_cmd) + "\n", encoding="utf-8")
    vsection(verbose, "AGENT PHASE")
    vprint(verbose, f"[agent:{agent_name}] command:")
    vprint(verbose, cmd_str(docker_cmd))
    vprint(verbose, f"[agent:{agent_name}] output:")

    proc = run_capture_stream(
        docker_cmd,
        timeout_sec=timeout_sec,
        verbose=verbose,
        phase=f"agent:{agent_name}",
        pretty_timeline=True,
        timeout_cleanup=lambda: cleanup_docker_container(
            container_name=container_name,
            phase=f"agent:{agent_name}",
            verbose=verbose,
        ),
    )
    return proc, extract_inner_sec(proc.stdout, proc.stderr)


def _run_agent_on_host(
    *,
    workdir: Path,
    run_dir: Path,
    agent_name: str,
    agent_cfg: dict[str, Any],
    model: str,
    timeout_sec: int,
    extra_env: dict[str, str] | None = None,
    verbose: bool = False,
    cmd_log_path: Path | None = None,
    run_capture_stream: Callable[
        ..., subprocess.CompletedProcess
    ] = _execution_helpers._run_capture_stream,
    normalize_model_options: Callable[
        [str, dict[str, Any]], Any
    ] = _normalize_model_options,
    model_options_env: Callable[[Any], dict[str, str]] = _model_options_env,
    inject_model_options_args: Callable[[str, Any], str] = _inject_model_options_args,
    resolve_host_executable: Callable[[str], Path] = _resolve_host_executable,
    vprint: Callable[[bool, str], None] = _vprint,
    vsection: Callable[[bool, str], None] = _vsection,
    subprocess_mod: Any = subprocess,
    os_mod: Any = os,
    time_mod: Any = time,
) -> tuple[subprocess.CompletedProcess, float | None]:
    bins = agent_cfg.get("bins", [])
    if not isinstance(bins, list) or not bins:
        raise ValueError(f"Agent {agent_name!r} missing 'bins' list")
    for b in bins:
        if not isinstance(b, dict):
            raise ValueError(f"Agent {agent_name!r} has invalid bin entry")
        host = str(b.get("host", "")).strip()
        if not host:
            raise ValueError(f"Agent {agent_name!r} bin entries require host")
        resolve_host_executable(host)

    env = dict(os_mod.environ)
    env.update(
        {
            "BENCH_AGENT": agent_name,
            "BENCH_MODEL": model,
            "BENCH_WORKDIR": str(workdir),
            "BENCH_RUN_DIR": str(run_dir),
            "BENCH_PROMPT_FILE": str(run_dir / "prompt.txt"),
            "BENCH_SPEC_FILE": str(run_dir / "spec.md"),
        }
    )
    if agent_name == "opencode":
        opencode_state_dir = _opencode_state_dir(run_dir)
        opencode_state_dir.mkdir(parents=True, exist_ok=True)
        env["XDG_DATA_HOME"] = str(opencode_state_dir)
    model_options = normalize_model_options(agent_name, agent_cfg)
    env.update(model_options_env(model_options))

    env_kv = agent_cfg.get("env", {})
    if env_kv:
        if not isinstance(env_kv, dict):
            raise ValueError(f"Agent {agent_name!r} env must be an object")
        for k, v in env_kv.items():
            env[str(k)] = str(v)

    if extra_env:
        env.update(extra_env)

    pre = agent_cfg.get("pre", [])
    cmd = str(agent_cfg.get("cmd", "")).strip()
    if not cmd:
        raise ValueError(f"Agent {agent_name!r} missing 'cmd'")
    if pre and not isinstance(pre, list):
        raise ValueError(f"Agent {agent_name!r} pre must be a list")
    cmd = inject_model_options_args(cmd, model_options)

    parts: list[str] = []
    parts.append('test -f "$BENCH_PROMPT_FILE"')
    parts.append('test -f "$BENCH_SPEC_FILE"')
    for part in pre:
        parts.append(str(part))
    parts.append(cmd)

    cmdline = ["bash", "-lc", " && ".join(parts)]
    if cmd_log_path is not None:
        cmd_log_path.write_text(_cmd_str(cmdline) + "\n", encoding="utf-8")
    vsection(verbose, "AGENT PHASE")
    vprint(verbose, f"[agent:{agent_name}:host] command:")
    vprint(verbose, _cmd_str(cmdline))
    vprint(verbose, f"[agent:{agent_name}:host] output:")

    t0 = time_mod.perf_counter()
    proc = run_capture_stream(
        cmdline,
        timeout_sec=timeout_sec,
        verbose=verbose,
        phase=f"agent:{agent_name}",
        cwd=workdir,
        env=env,
        pretty_timeline=True,
    )
    return proc, round(time_mod.perf_counter() - t0, 6)
