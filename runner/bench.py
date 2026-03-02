#!/usr/bin/env python3

import argparse
import datetime as _dt
import json
import os
import secrets
import shlex
import shutil
import subprocess
import sys
from typing import Any
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib as _toml_lib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - fallback for Python <3.11
    try:
        import tomli as _toml_lib  # type: ignore[no-redef]
    except ModuleNotFoundError:  # pragma: no cover
        _toml_lib = None  # type: ignore[assignment]


REPO_ROOT = Path(__file__).resolve().parents[1]
BENCH_ROOT = REPO_ROOT / "benchmarks"
RUNS_ROOT = REPO_ROOT / "runs"
AGENTS_DEFAULT_PATH = REPO_ROOT / "agents_default.toml"


def _vprint(enabled: bool, msg: str) -> None:
    if enabled:
        print(msg, file=sys.stderr)


def _redacted_cmd(cmd: list[str]) -> list[str]:
    out: list[str] = []
    redact_next_env = False
    for tok in cmd:
        if redact_next_env:
            if "=" in tok:
                k, _v = tok.split("=", 1)
                out.append(f"{k}=<redacted>")
            else:
                out.append(tok)
            redact_next_env = False
            continue

        out.append(tok)
        if tok == "-e":
            redact_next_env = True
    return out


def _cmd_str(cmd: list[str]) -> str:
    # Render a shell-ish command line for logs.
    return shlex.join(_redacted_cmd(cmd))


def _expand_path(s: str) -> str:
    return os.path.expandvars(os.path.expanduser(s))


def _is_env_true(name: str) -> bool:
    v = os.environ.get(name)
    if v is None:
        return False
    return v.strip().lower() in {"1", "true", "yes", "on"}


def _agent_enable_env_key(name: str) -> str:
    slug = "".join(ch if ch.isalnum() else "_" for ch in name).upper()
    return f"SCIBENCH_ENABLE_{slug}"


def _resolve_input_toml_path(path: Path) -> Path:
    p = Path(_expand_path(str(path)))
    if not p.is_absolute():
        p = (REPO_ROOT / p).resolve()
    return p


def _load_toml(path: Path, *, kind: str) -> dict[str, Any]:
    p = _resolve_input_toml_path(path)
    if not p.exists():
        raise FileNotFoundError(f"{kind} not found: {p}")

    if p.suffix.lower() != ".toml":
        raise ValueError(f"{kind} must be TOML: {p}")

    if _toml_lib is None:
        raise RuntimeError(
            "TOML parser unavailable (need Python 3.11+ or install tomli)"
        )

    data = _toml_lib.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{kind} root must be a table")
    return data


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_agent_config(path: Path) -> dict[str, Any]:
    override = _load_toml(path, kind="agent config")
    if int(override.get("version", 0)) != 1:
        raise ValueError(f"Unsupported agent config version: {override.get('version')}")

    name = str(override.get("name", "")).strip()
    if not name:
        raise ValueError("agent config missing required 'name'")

    defaults = _load_toml(AGENTS_DEFAULT_PATH, kind="agents default config")
    if int(defaults.get("version", 0)) != 1:
        raise ValueError(
            f"Unsupported agents default config version: {defaults.get('version')}"
        )
    agents = defaults.get("agents")
    if not isinstance(agents, dict):
        raise ValueError("agents default config missing [agents] table")

    base = agents.get(name)
    if not isinstance(base, dict):
        raise ValueError(f"Agent {name!r} not found in agents_default.toml")

    filtered = {k: v for k, v in override.items() if k not in {"version", "name"}}
    merged = _deep_merge(base, filtered)
    merged["name"] = name
    return merged


def _is_agent_enabled(cfg: dict[str, Any]) -> tuple[bool, str]:
    name = str(cfg.get("name", "")).strip()
    if not name:
        return False, "agent config missing required 'name'"

    enable_env = _agent_enable_env_key(name)
    enabled_by_default = bool(cfg.get("enabled_by_default", name == "opencode"))
    enabled = enabled_by_default or _is_env_true(enable_env)
    if not enabled:
        return False, (
            f"Agent {name!r} is disabled by default; export {enable_env}=1 to enable"
        )
    return True, ""


def _resolve_host_executable(spec: str) -> Path:
    s = _expand_path(spec)
    if "/" in s or s.startswith("."):
        p = Path(s)
        if p.exists():
            return p.resolve()
        raise FileNotFoundError(f"Executable not found: {p}")

    found = shutil.which(s)
    if not found:
        raise FileNotFoundError(f"Executable not found on PATH: {s}")
    return Path(found).resolve()


@dataclass(frozen=True)
class Task:
    suite: str
    task_id: str
    path: Path
    spec_path: Path
    task_toml_path: Path
    workspace_tpl: Path
    eval_dir: Path
    meta: dict


def _coerce_text(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    return str(v)


def _load_task(suite: str, task_id: str) -> Task:
    task_path = BENCH_ROOT / suite / task_id
    spec_path = task_path / "spec.md"
    task_toml_path = task_path / "task.toml"
    workspace_tpl = task_path / "workspace"
    eval_dir = task_path / "eval"

    missing = [
        p
        for p in [spec_path, task_toml_path, workspace_tpl, eval_dir]
        if not p.exists()
    ]
    if missing:
        msg = "Task is missing required paths:\n" + "\n".join(f"- {p}" for p in missing)
        raise FileNotFoundError(msg)

    if _toml_lib is None:
        raise RuntimeError(
            "TOML parser unavailable (need Python 3.11+ or install tomli)"
        )
    meta: dict[str, Any] = _toml_lib.loads(task_toml_path.read_text(encoding="utf-8"))
    return Task(
        suite=suite,
        task_id=task_id,
        path=task_path,
        spec_path=spec_path,
        task_toml_path=task_toml_path,
        workspace_tpl=workspace_tpl,
        eval_dir=eval_dir,
        meta=meta,
    )


def _iter_tasks():
    if not BENCH_ROOT.exists():
        return
    for suite_dir in sorted([p for p in BENCH_ROOT.iterdir() if p.is_dir()]):
        for task_dir in sorted([p for p in suite_dir.iterdir() if p.is_dir()]):
            if (task_dir / "spec.md").exists() and (task_dir / "task.toml").exists():
                yield (suite_dir.name, task_dir.name)


def cmd_list(_args: argparse.Namespace) -> int:
    for suite, task_id in _iter_tasks():
        print(f"{suite}/{task_id}")
    return 0


def _resolve_result_dir(*, task: Task, run_id: str, result_dir: str) -> Path:
    if result_dir.strip():
        p = Path(_expand_path(result_dir))
        if not p.is_absolute():
            p = (Path.cwd() / p).resolve()
        return p
    return RUNS_ROOT / run_id / task.suite / task.task_id


def _prepare_run_dir(
    *, task: Task, run_id: str, result_dir: str = ""
) -> tuple[Path, Path, Path]:
    run_dir = _resolve_result_dir(task=task, run_id=run_id, result_dir=result_dir)
    workdir = run_dir / "workdir"
    logs_dir = run_dir / "logs"

    if run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError(f"result_dir already exists and is not empty: {run_dir}")

    workdir.parent.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    if workdir.exists():
        shutil.rmtree(workdir)
    shutil.copytree(task.workspace_tpl, workdir)

    (run_dir / "spec.md").write_text(
        task.spec_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (run_dir / "task.toml").write_text(
        task.task_toml_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return run_dir, workdir, logs_dir


def _prepare_eval_result_dir(
    *, task: Task, run_id: str, result_dir: str = ""
) -> tuple[Path, Path]:
    run_dir = _resolve_result_dir(task=task, run_id=run_id, result_dir=result_dir)
    logs_dir = run_dir / "logs"

    if run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError(f"result_dir already exists and is not empty: {run_dir}")

    run_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    return run_dir, logs_dir


def _gen_run_id() -> str:
    ts = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return f"{ts}-{secrets.token_hex(4)}"


def _run_docker_eval(
    *,
    image: str,
    workdir: Path,
    eval_dir: Path,
    eval_cmd: str,
    network: str,
    timeout_sec: int,
    extra_env: dict[str, str] | None = None,
    verbose: bool = False,
    cmd_log_path: Path | None = None,
) -> subprocess.CompletedProcess:
    uid = os.getuid() if hasattr(os, "getuid") else 1000
    gid = os.getgid() if hasattr(os, "getgid") else 1000

    docker_cmd = [
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
        "-v",
        f"{str(eval_dir)}:/eval:ro",
        "-w",
        "/work",
    ]
    if network == "off":
        docker_cmd += ["--network", "none"]
    elif network == "on":
        pass
    else:
        raise ValueError("network must be 'on' or 'off'")

    if extra_env:
        for k, v in extra_env.items():
            docker_cmd += ["-e", f"{k}={v}"]

    docker_cmd += [image, "bash", "-lc", eval_cmd]

    if cmd_log_path is not None:
        cmd_log_path.write_text(_cmd_str(docker_cmd) + "\n", encoding="utf-8")
    _vprint(verbose, f"[eval] {_cmd_str(docker_cmd)}")

    return subprocess.run(
        docker_cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_sec,
    )


def _run_docker_shell(
    *, image: str, workdir: Path, network: str, cmd: list[str]
) -> int:
    uid = os.getuid() if hasattr(os, "getuid") else 1000
    gid = os.getgid() if hasattr(os, "getgid") else 1000

    docker_cmd = [
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
    if network == "off":
        docker_cmd += ["--network", "none"]
    elif network == "on":
        pass
    else:
        raise ValueError("network must be 'on' or 'off'")

    if cmd == ["bash"]:
        docker_cmd += ["-it"]

    docker_cmd += [image] + cmd
    return subprocess.call(docker_cmd)


def _run_agent_in_docker(
    *,
    image: str,
    workdir: Path,
    run_dir: Path,
    agent_name: str,
    agent_cfg: dict[str, Any],
    model: str,
    network: str,
    timeout_sec: int,
    extra_env: dict[str, str] | None = None,
    verbose: bool = False,
    cmd_log_path: Path | None = None,
) -> subprocess.CompletedProcess:
    uid = os.getuid() if hasattr(os, "getuid") else 1000
    gid = os.getgid() if hasattr(os, "getgid") else 1000

    docker_cmd: list[str] = [
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

    bins = agent_cfg.get("bins", [])
    if not isinstance(bins, list) or not bins:
        raise ValueError(f"Agent {agent_name!r} missing 'bins' list")
    for b in bins:
        if not isinstance(b, dict):
            raise ValueError(f"Agent {agent_name!r} has invalid bin entry")
        host = str(b.get("host", "")).strip()
        container = str(b.get("container", "")).strip()
        if not host or not container:
            raise ValueError(f"Agent {agent_name!r} bin entries require host+container")
        host_path = _resolve_host_executable(host)
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

            host_path = Path(_expand_path(host))
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

    if network == "off":
        docker_cmd += ["--network", "none"]
    elif network == "on":
        pass
    else:
        raise ValueError("network must be 'on' or 'off'")

    if extra_env:
        for k, v in extra_env.items():
            docker_cmd += ["-e", f"{k}={v}"]

    pre = agent_cfg.get("pre", [])
    cmd = str(agent_cfg.get("cmd", "")).strip()
    if not cmd:
        raise ValueError(f"Agent {agent_name!r} missing 'cmd'")
    if pre and not isinstance(pre, list):
        raise ValueError(f"Agent {agent_name!r} pre must be a list")

    inner_parts: list[str] = []
    inner_parts.append('test -f "$BENCH_PROMPT_FILE"')
    inner_parts.append('test -f "$BENCH_SPEC_FILE"')
    for part in pre:
        inner_parts.append(str(part))
    inner_parts.append(cmd)
    docker_cmd += [image, "bash", "-lc", " && ".join(inner_parts)]

    if cmd_log_path is not None:
        cmd_log_path.write_text(_cmd_str(docker_cmd) + "\n", encoding="utf-8")
    _vprint(verbose, f"[agent:{agent_name}] {_cmd_str(docker_cmd)}")

    return subprocess.run(
        docker_cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_sec,
    )


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
) -> subprocess.CompletedProcess:
    # Validate that declared executables exist on PATH.
    bins = agent_cfg.get("bins", [])
    if not isinstance(bins, list) or not bins:
        raise ValueError(f"Agent {agent_name!r} missing 'bins' list")
    for b in bins:
        if not isinstance(b, dict):
            raise ValueError(f"Agent {agent_name!r} has invalid bin entry")
        host = str(b.get("host", "")).strip()
        if not host:
            raise ValueError(f"Agent {agent_name!r} bin entries require host")
        _resolve_host_executable(host)

    env = dict(os.environ)
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

    parts: list[str] = []
    parts.append('test -f "$BENCH_PROMPT_FILE"')
    parts.append('test -f "$BENCH_SPEC_FILE"')
    for part in pre:
        parts.append(str(part))
    parts.append(cmd)

    # Run under bash for consistent quoting/expansion.
    cmdline = ["bash", "-lc", " && ".join(parts)]
    if cmd_log_path is not None:
        cmd_log_path.write_text(_cmd_str(cmdline) + "\n", encoding="utf-8")
    _vprint(verbose, f"[agent:{agent_name}:host] {_cmd_str(cmdline)}")

    return subprocess.run(
        cmdline,
        cwd=workdir,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_sec,
    )


def cmd_run(args: argparse.Namespace) -> int:
    # Full benchmark run: agent solve + authoritative eval.
    return _cmd_agent_common(args=args)


def cmd_eval(args: argparse.Namespace) -> int:
    if "/" not in args.task:
        print("Task must be in the form <suite>/<task_id>", file=sys.stderr)
        return 2

    suite, task_id = args.task.split("/", 1)
    task = _load_task(suite, task_id)

    eval_cmd = str(task.meta.get("eval_cmd", ""))
    if not eval_cmd:
        print(f"Missing eval_cmd in {task.task_toml_path}", file=sys.stderr)
        return 2

    timeout_sec = int(task.meta.get("time_limit_sec", args.timeout_sec))

    run_id = args.run_id or _gen_run_id()
    try:
        run_dir, logs_dir = _prepare_eval_result_dir(
            task=task,
            run_id=run_id,
            result_dir=args.result_dir,
        )
    except FileExistsError as e:
        print(str(e), file=sys.stderr)
        return 2

    workdir = Path(_expand_path(args.workdir))
    if not workdir.is_absolute():
        workdir = (Path.cwd() / workdir).resolve()
    if not workdir.exists() or not workdir.is_dir():
        print(f"workdir not found or not a directory: {workdir}", file=sys.stderr)
        return 2

    (run_dir / "spec.md").write_text(
        task.spec_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (run_dir / "task.toml").write_text(
        task.task_toml_path.read_text(encoding="utf-8"), encoding="utf-8"
    )

    _vprint(args.verbose, f"run_id={run_id}")
    _vprint(args.verbose, f"run_dir={run_dir}")
    _vprint(args.verbose, f"workdir={workdir}")
    _vprint(args.verbose, f"task={suite}/{task_id}")
    _vprint(
        args.verbose,
        f"image={args.image} network={args.network} timeout_sec={timeout_sec}",
    )

    try:
        proc = _run_docker_eval(
            image=args.image,
            workdir=workdir,
            eval_dir=task.eval_dir,
            eval_cmd=eval_cmd,
            network=args.network,
            timeout_sec=timeout_sec,
            verbose=args.verbose,
            cmd_log_path=logs_dir / "eval.docker_cmd.txt",
        )
    except FileNotFoundError as e:
        print(f"Failed to run docker: {e}", file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired:
        (logs_dir / "eval.stdout.txt").write_text("", encoding="utf-8")
        (logs_dir / "eval.stderr.txt").write_text("Timed out\n", encoding="utf-8")
        print(f"Timed out after {timeout_sec}s", file=sys.stderr)
        return 1

    (logs_dir / "eval.stdout.txt").write_text(proc.stdout, encoding="utf-8")
    (logs_dir / "eval.stderr.txt").write_text(proc.stderr, encoding="utf-8")
    (logs_dir / "eval.exit_code.txt").write_text(
        str(proc.returncode) + "\n", encoding="utf-8"
    )

    final_rc = 0 if proc.returncode == 0 else 1

    # If eval harness wrote a result.json into /work, persist it alongside logs.
    result_path = workdir / "result.json"
    if result_path.exists():
        shutil.copy2(result_path, run_dir / "result.json")
        try:
            result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
            status = result.get("status", "unknown")
            score = result.get("score", None)
            print(f"{suite}/{task_id}: status={status} score={score}")
            if status != "passed":
                final_rc = 1
        except Exception:
            print(f"{suite}/{task_id}: wrote result.json")
    else:
        print(f"{suite}/{task_id}: eval completed (no result.json found)")
        final_rc = 1

    print(str(run_dir))
    return final_rc


def cmd_prepare(args: argparse.Namespace) -> int:
    if "/" not in args.task:
        print("Task must be in the form <suite>/<task_id>", file=sys.stderr)
        return 2
    suite, task_id = args.task.split("/", 1)
    task = _load_task(suite, task_id)

    try:
        agent_cfg = _load_agent_config(Path(str(args.agents)))
    except Exception as e:
        print(f"Failed to load agent config: {e}", file=sys.stderr)
        return 2

    enabled, reason = _is_agent_enabled(agent_cfg)
    if not enabled:
        print(f"Failed to load agent config: {reason}", file=sys.stderr)
        return 2

    run_id = args.run_id or _gen_run_id()
    try:
        run_dir, workdir, _logs_dir = _prepare_run_dir(
            task=task,
            run_id=run_id,
            result_dir=args.result_dir,
        )
    except FileExistsError as e:
        print(str(e), file=sys.stderr)
        return 2
    agent_cfg_path = _resolve_input_toml_path(Path(str(args.agents)))
    (run_dir / "agent.toml").write_text(
        agent_cfg_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    print(str(workdir))
    print(str(run_dir))
    return 0


def cmd_shell(args: argparse.Namespace) -> int:
    if "/" not in args.task:
        print("Task must be in the form <suite>/<task_id>", file=sys.stderr)
        return 2
    suite, task_id = args.task.split("/", 1)
    task = _load_task(suite, task_id)

    try:
        agent_cfg = _load_agent_config(Path(str(args.agents)))
    except Exception as e:
        print(f"Failed to load agent config: {e}", file=sys.stderr)
        return 2

    enabled, reason = _is_agent_enabled(agent_cfg)
    if not enabled:
        print(f"Failed to load agent config: {reason}", file=sys.stderr)
        return 2

    run_id = args.run_id or _gen_run_id()
    try:
        run_dir, workdir, _logs_dir = _prepare_run_dir(
            task=task,
            run_id=run_id,
            result_dir=args.result_dir,
        )
    except FileExistsError as e:
        print(str(e), file=sys.stderr)
        return 2
    agent_cfg_path = _resolve_input_toml_path(Path(str(args.agents)))
    (run_dir / "agent.toml").write_text(
        agent_cfg_path.read_text(encoding="utf-8"), encoding="utf-8"
    )

    cmd = args.cmd if args.cmd else ["bash"]
    try:
        return _run_docker_shell(
            image=args.image,
            workdir=workdir,
            network=args.network,
            cmd=cmd,
        )
    except FileNotFoundError as e:
        print(f"Failed to run docker: {e}", file=sys.stderr)
        return 1


def _cmd_agent_common(*, args: argparse.Namespace) -> int:
    if "/" not in args.task:
        print("Task must be in the form <suite>/<task_id>", file=sys.stderr)
        return 2

    suite, task_id = args.task.split("/", 1)
    task = _load_task(suite, task_id)

    eval_cmd = str(task.meta.get("eval_cmd", ""))
    if not eval_cmd:
        print(f"Missing eval_cmd in {task.task_toml_path}", file=sys.stderr)
        return 2

    timeout_sec = int(task.meta.get("time_limit_sec", args.timeout_sec))
    run_id = args.run_id or _gen_run_id()
    try:
        run_dir, workdir, logs_dir = _prepare_run_dir(
            task=task,
            run_id=run_id,
            result_dir=args.result_dir,
        )
    except FileExistsError as e:
        print(str(e), file=sys.stderr)
        return 2

    agents_config_path = Path(str(args.agents))
    try:
        agent_cfg = _load_agent_config(agents_config_path)
    except Exception as e:
        print(f"Failed to load agent config: {e}", file=sys.stderr)
        return 2

    configured_name = str(agent_cfg.get("name", "")).strip()
    if not configured_name:
        print("agent config missing required 'name'", file=sys.stderr)
        return 2

    enabled, reason = _is_agent_enabled(agent_cfg)
    if not enabled:
        print(f"Failed to load agent config: {reason}", file=sys.stderr)
        return 2

    agent_name = configured_name

    agent_cfg_path = _resolve_input_toml_path(Path(str(args.agents)))
    (run_dir / "agent.toml").write_text(
        agent_cfg_path.read_text(encoding="utf-8"), encoding="utf-8"
    )

    mode = str(agent_cfg.get("mode", "docker")).strip()
    if mode not in ("docker", "host"):
        print(f"Unknown agent mode: {mode!r} (expected docker|host)", file=sys.stderr)
        return 2

    model = str(agent_cfg.get("default_model", "")).strip()
    if model:
        _vprint(args.verbose, f"using default_model from agents config: {model}")
    if not model:
        print(
            f"No model configured. Set default_model for agent {agent_name!r} in agents config",
            file=sys.stderr,
        )
        return 2
    if agent_name == "opencode" and "/" not in model:
        before = model
        model = f"openai/{model}"
        _vprint(args.verbose, f"normalized model for opencode: {before} -> {model}")

    _vprint(args.verbose, f"run_id={run_id}")
    _vprint(args.verbose, f"run_dir={run_dir}")
    _vprint(args.verbose, f"workdir={workdir}")
    _vprint(args.verbose, f"agent={agent_name} mode={mode}")
    _vprint(args.verbose, f"agents_config={agents_config_path}")

    default_prompt = (
        "Solve the attached spec. Edit files in the working directory. "
        "Run the public tests while working and make them pass. "
        "If you need a toolchain, run commands via Docker using the image "
        f"{args.image!r}. Example: "
        f'docker run --rm -v "$PWD":/work -w /work {args.image} bash -lc "pytest -q"'
    )

    prompt = ""
    if args.prompt:
        prompt = args.prompt
    else:
        prompt_file = str(task.meta.get("prompt_file", "")).strip()
        if prompt_file:
            p = task.path / prompt_file
            if p.exists():
                prompt = p.read_text(encoding="utf-8").strip()
            else:
                print(f"prompt_file not found: {p}", file=sys.stderr)
                return 2

        if not prompt:
            prompt = str(task.meta.get("prompt", "")).strip()

        if not prompt:
            prompt = default_prompt

    # Always include pointers so different agent CLIs can locate inputs.
    spec_ptr = "/run/spec.md" if mode == "docker" else str(run_dir / "spec.md")
    work_ptr = "/work" if mode == "docker" else str(workdir)
    prompt = prompt.rstrip() + "\n\n" + f"Spec: {spec_ptr}\nWorkdir: {work_ptr}\n"

    # Persist the prompt so the agent doesn't need to receive it via env.
    (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")

    pass_env_keys = agent_cfg.get("pass_env", [])
    if pass_env_keys and not isinstance(pass_env_keys, list):
        print(f"Agent {agent_name!r} pass_env must be a list", file=sys.stderr)
        return 2
    extra_env: dict[str, str] = {}
    for k in pass_env_keys:
        if not isinstance(k, str):
            continue
        v = os.environ.get(k)
        if v:
            extra_env[k] = v

    if extra_env:
        keys = ",".join(sorted(extra_env.keys()))
        (logs_dir / "agent.forwarded_env.txt").write_text(keys + "\n", encoding="utf-8")
        print(f"Forwarding env into agent container: {keys}", file=sys.stderr)

    try:
        if mode == "docker":
            op = _run_agent_in_docker(
                image=args.image,
                workdir=workdir,
                run_dir=run_dir,
                agent_name=agent_name,
                agent_cfg=agent_cfg,
                model=model,
                network=args.network,
                timeout_sec=timeout_sec,
                extra_env=extra_env,
                verbose=args.verbose,
                cmd_log_path=logs_dir / "agent.docker_cmd.txt",
            )
        elif mode == "host":
            op = _run_agent_on_host(
                workdir=workdir,
                run_dir=run_dir,
                agent_name=agent_name,
                agent_cfg=agent_cfg,
                model=model,
                timeout_sec=timeout_sec,
                extra_env=extra_env,
                verbose=args.verbose,
                cmd_log_path=logs_dir / "agent.host_cmd.txt",
            )
        else:
            raise ValueError(f"Unknown agent mode: {mode!r} (expected docker|host)")
    except (FileNotFoundError, ValueError) as e:
        (logs_dir / "agent.stderr.txt").write_text(str(e) + "\n", encoding="utf-8")
        (logs_dir / "agent.exit_code.txt").write_text("setup_error\n", encoding="utf-8")
        print(f"Agent setup failed: {e}", file=sys.stderr)
        print(str(run_dir))
        return 1
    except subprocess.TimeoutExpired as e:
        (logs_dir / "agent.stdout.txt").write_text(
            _coerce_text(e.stdout), encoding="utf-8"
        )
        (logs_dir / "agent.stderr.txt").write_text(
            _coerce_text(e.stderr) + "\nTimed out\n", encoding="utf-8"
        )
        (logs_dir / "agent.exit_code.txt").write_text("timeout\n", encoding="utf-8")
        print(f"Timed out after {timeout_sec}s (agent)", file=sys.stderr)
        print(str(run_dir))
        return 1

    (logs_dir / "agent.stdout.txt").write_text(op.stdout, encoding="utf-8")
    (logs_dir / "agent.stderr.txt").write_text(op.stderr, encoding="utf-8")
    (logs_dir / "agent.exit_code.txt").write_text(
        str(op.returncode) + "\n", encoding="utf-8"
    )
    if op.returncode != 0:
        print(f"agent failed with exit code {op.returncode}", file=sys.stderr)
        print(f"Logs: {logs_dir}", file=sys.stderr)
        if op.stderr.strip():
            print(op.stderr.strip(), file=sys.stderr)
        print(str(run_dir))
        return 1

    # Evaluate the same workdir using the hidden harness.
    try:
        proc = _run_docker_eval(
            image=args.image,
            workdir=workdir,
            eval_dir=task.eval_dir,
            eval_cmd=eval_cmd,
            network=args.network,
            timeout_sec=timeout_sec,
            verbose=args.verbose,
            cmd_log_path=logs_dir / "eval.docker_cmd.txt",
        )
    except FileNotFoundError as e:
        print(f"Failed to run docker: {e}", file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired:
        (logs_dir / "eval.stdout.txt").write_text("", encoding="utf-8")
        (logs_dir / "eval.stderr.txt").write_text("Timed out\n", encoding="utf-8")
        print(f"Timed out after {timeout_sec}s", file=sys.stderr)
        return 1

    (logs_dir / "eval.stdout.txt").write_text(proc.stdout, encoding="utf-8")
    (logs_dir / "eval.stderr.txt").write_text(proc.stderr, encoding="utf-8")
    (logs_dir / "eval.exit_code.txt").write_text(
        str(proc.returncode) + "\n", encoding="utf-8"
    )

    final_rc = 0
    result_path = workdir / "result.json"
    if result_path.exists():
        shutil.copy2(result_path, run_dir / "result.json")
        try:
            result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
            status = result.get("status", "unknown")
            score = result.get("score", None)
            print(f"{suite}/{task_id}: status={status} score={score}")
            if status != "passed":
                final_rc = 1
        except Exception:
            print(f"{suite}/{task_id}: wrote result.json")
            final_rc = 1
    else:
        print(f"{suite}/{task_id}: eval completed (no result.json found)")
        final_rc = 1

    print(str(run_dir))
    return final_rc


def main(argv: list[str]) -> int:
    # Convenience form: `bench <agent.toml> <task> ...` means `bench run ...`.
    argv2 = list(argv)
    if argv2:
        if argv2[0].endswith(".toml"):
            argv2 = ["run"] + argv2
        elif argv2[0] == "--verbose" and len(argv2) > 1 and argv2[1].endswith(".toml"):
            argv2 = ["--verbose", "run"] + argv2[1:]

    p = argparse.ArgumentParser(prog="bench")
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Print internal runner actions to stderr",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List available tasks")
    p_list.set_defaults(fn=cmd_list)

    p_run = sub.add_parser("run", help="Run agent solve + eval")
    p_run.add_argument("agents", help="Path to single-agent TOML config")
    p_run.add_argument("task", help="Task in the form <suite>/<task_id>")
    p_run.add_argument(
        "--prompt",
        default="",
        help="Override the one-shot message (otherwise uses task.toml/default)",
    )
    p_run.add_argument("--image", default="scibench:0.1", help="Docker image tag")
    p_run.add_argument("--network", choices=["on", "off"], default="on")
    p_run.add_argument("--timeout-sec", type=int, default=600)
    p_run.add_argument("--run-id", default="")
    p_run.add_argument("--result-dir", default="")
    p_run.set_defaults(fn=cmd_run)

    p_eval = sub.add_parser("eval", help="Run eval-only on an existing workdir")
    p_eval.add_argument("task", help="Task in the form <suite>/<task_id>")
    p_eval.add_argument("--workdir", required=True)
    p_eval.add_argument("--image", default="scibench:0.1", help="Docker image tag")
    p_eval.add_argument("--network", choices=["on", "off"], default="on")
    p_eval.add_argument("--timeout-sec", type=int, default=600)
    p_eval.add_argument("--run-id", default="")
    p_eval.add_argument("--result-dir", default="")
    p_eval.set_defaults(fn=cmd_eval)

    p_prepare = sub.add_parser("prepare", help="Create an isolated run workspace")
    p_prepare.add_argument("agents", help="Path to single-agent TOML config")
    p_prepare.add_argument("task", help="Task in the form <suite>/<task_id>")
    p_prepare.add_argument("--run-id", default="")
    p_prepare.add_argument("--result-dir", default="")
    p_prepare.set_defaults(fn=cmd_prepare)

    p_shell = sub.add_parser(
        "shell", help="Open an interactive shell in the task workspace"
    )
    p_shell.add_argument("agents", help="Path to single-agent TOML config")
    p_shell.add_argument("task", help="Task in the form <suite>/<task_id>")
    p_shell.add_argument("--image", default="scibench:0.1", help="Docker image tag")
    p_shell.add_argument("--network", choices=["on", "off"], default="on")
    p_shell.add_argument("--run-id", default="")
    p_shell.add_argument("--result-dir", default="")
    p_shell.add_argument(
        "cmd",
        nargs="*",
        help="Command to run (use `--` before command flags)",
    )
    p_shell.set_defaults(fn=cmd_shell)

    args = p.parse_args(argv2)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
