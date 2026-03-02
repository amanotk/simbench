#!/usr/bin/env python3

import argparse
import datetime as _dt
import json
import os
import secrets
import shutil
import subprocess
import sys
from typing import Any
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BENCH_ROOT = REPO_ROOT / "benchmarks"
RUNS_ROOT = REPO_ROOT / "runs"
AGENTS_CONFIG_DEFAULT = REPO_ROOT / "agents.json"


def _expand_path(s: str) -> str:
    return os.path.expandvars(os.path.expanduser(s))


def _load_agents_config(path: Path) -> dict[str, Any]:
    p = Path(_expand_path(str(path)))
    if not p.is_absolute():
        p = (REPO_ROOT / p).resolve()
    if not p.exists():
        raise FileNotFoundError(f"agents config not found: {p}")

    data = json.loads(p.read_text(encoding="utf-8"))
    if int(data.get("version", 0)) != 1:
        raise ValueError(f"Unsupported agents config version: {data.get('version')}")
    agents = data.get("agents")
    if not isinstance(agents, dict):
        raise ValueError("agents config missing top-level 'agents' object")
    return agents


def _get_agent_cfg(agents: dict[str, Any], name: str) -> dict[str, Any]:
    cfg = agents.get(name)
    if not isinstance(cfg, dict):
        raise KeyError(f"Unknown agent: {name}")
    if cfg.get("enabled", True) is False:
        raise ValueError(
            f"Agent {name!r} is disabled in agents.json; set enabled=true to use it"
        )
    return cfg


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
    task_json_path: Path
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
    task_json_path = task_path / "task.json"
    workspace_tpl = task_path / "workspace"
    eval_dir = task_path / "eval"

    missing = [
        p
        for p in [spec_path, task_json_path, workspace_tpl, eval_dir]
        if not p.exists()
    ]
    if missing:
        msg = "Task is missing required paths:\n" + "\n".join(f"- {p}" for p in missing)
        raise FileNotFoundError(msg)

    meta: dict[str, Any] = json.loads(task_json_path.read_text(encoding="utf-8"))
    return Task(
        suite=suite,
        task_id=task_id,
        path=task_path,
        spec_path=spec_path,
        task_json_path=task_json_path,
        workspace_tpl=workspace_tpl,
        eval_dir=eval_dir,
        meta=meta,
    )


def _iter_tasks():
    if not BENCH_ROOT.exists():
        return
    for suite_dir in sorted([p for p in BENCH_ROOT.iterdir() if p.is_dir()]):
        for task_dir in sorted([p for p in suite_dir.iterdir() if p.is_dir()]):
            if (task_dir / "spec.md").exists() and (task_dir / "task.json").exists():
                yield (suite_dir.name, task_dir.name)


def cmd_list(_args: argparse.Namespace) -> int:
    for suite, task_id in _iter_tasks():
        print(f"{suite}/{task_id}")
    return 0


def _prepare_run_dir(*, task: Task, run_id: str) -> tuple[Path, Path, Path]:
    run_dir = RUNS_ROOT / run_id / task.suite / task.task_id
    workdir = run_dir / "workdir"
    logs_dir = run_dir / "logs"

    workdir.parent.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    if workdir.exists():
        shutil.rmtree(workdir)
    shutil.copytree(task.workspace_tpl, workdir)

    (run_dir / "spec.md").write_text(
        task.spec_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (run_dir / "task.json").write_text(
        task.task_json_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return run_dir, workdir, logs_dir


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
        "-it",
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
    for part in pre:
        inner_parts.append(str(part))
    inner_parts.append(cmd)
    docker_cmd += [image, "bash", "-lc", " && ".join(inner_parts)]

    return subprocess.run(
        docker_cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_sec,
    )


def cmd_run(args: argparse.Namespace) -> int:
    if "/" not in args.task:
        print("Task must be in the form <suite>/<task_id>", file=sys.stderr)
        return 2

    suite, task_id = args.task.split("/", 1)
    task = _load_task(suite, task_id)

    eval_cmd = str(task.meta.get("eval_cmd", ""))
    if not eval_cmd:
        print(f"Missing eval_cmd in {task.task_json_path}", file=sys.stderr)
        return 2

    timeout_sec = int(task.meta.get("time_limit_sec", args.timeout_sec))

    run_id = args.run_id or _gen_run_id()
    run_dir, workdir, logs_dir = _prepare_run_dir(task=task, run_id=run_id)

    try:
        proc = _run_docker_eval(
            image=args.image,
            workdir=workdir,
            eval_dir=task.eval_dir,
            eval_cmd=eval_cmd,
            network=args.network,
            timeout_sec=timeout_sec,
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
    run_id = args.run_id or _gen_run_id()
    run_dir, workdir, _logs_dir = _prepare_run_dir(task=task, run_id=run_id)
    print(str(workdir))
    print(str(run_dir))
    return 0


def cmd_shell(args: argparse.Namespace) -> int:
    if "/" not in args.task:
        print("Task must be in the form <suite>/<task_id>", file=sys.stderr)
        return 2
    suite, task_id = args.task.split("/", 1)
    task = _load_task(suite, task_id)
    run_id = args.run_id or _gen_run_id()
    _run_dir, workdir, _logs_dir = _prepare_run_dir(task=task, run_id=run_id)

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


def cmd_opencode(args: argparse.Namespace) -> int:
    # Back-compat alias for `bench agent --agent opencode`.
    return _cmd_agent_common(args=args, agent_name="opencode")


def cmd_agent(args: argparse.Namespace) -> int:
    return _cmd_agent_common(args=args, agent_name=args.agent)


def _cmd_agent_common(*, args: argparse.Namespace, agent_name: str) -> int:
    if "/" not in args.task:
        print("Task must be in the form <suite>/<task_id>", file=sys.stderr)
        return 2

    suite, task_id = args.task.split("/", 1)
    task = _load_task(suite, task_id)

    eval_cmd = str(task.meta.get("eval_cmd", ""))
    if not eval_cmd:
        print(f"Missing eval_cmd in {task.task_json_path}", file=sys.stderr)
        return 2

    timeout_sec = int(task.meta.get("time_limit_sec", args.timeout_sec))
    run_id = args.run_id or _gen_run_id()
    run_dir, workdir, logs_dir = _prepare_run_dir(task=task, run_id=run_id)

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

    # Persist the prompt so the container doesn't need to receive it via env.
    (run_dir / "prompt.txt").write_text(prompt + "\n", encoding="utf-8")

    agents_config_path = Path(
        getattr(args, "agents_config", "") or AGENTS_CONFIG_DEFAULT
    )
    try:
        agents = _load_agents_config(agents_config_path)
        agent_cfg = _get_agent_cfg(agents, agent_name)
    except Exception as e:
        print(f"Failed to load agent config: {e}", file=sys.stderr)
        return 2

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

    # Run agent in Docker so the session is sandboxed similarly to eval.
    try:
        op = _run_agent_in_docker(
            image=args.image,
            workdir=workdir,
            run_dir=run_dir,
            agent_name=agent_name,
            agent_cfg=agent_cfg,
            model=args.model,
            network=args.network,
            timeout_sec=timeout_sec,
            extra_env=extra_env,
        )
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
    p = argparse.ArgumentParser(prog="bench")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List available tasks")
    p_list.set_defaults(fn=cmd_list)

    p_run = sub.add_parser("run", help="Run a task eval in Docker")
    p_run.add_argument("task", help="Task in the form <suite>/<task_id>")
    p_run.add_argument("--image", default="scibench:0.1", help="Docker image tag")
    p_run.add_argument("--network", choices=["on", "off"], default="on")
    p_run.add_argument("--timeout-sec", type=int, default=600)
    p_run.add_argument("--run-id", default="")
    p_run.set_defaults(fn=cmd_run)

    p_prepare = sub.add_parser("prepare", help="Create an isolated run workspace")
    p_prepare.add_argument("task", help="Task in the form <suite>/<task_id>")
    p_prepare.add_argument("--run-id", default="")
    p_prepare.set_defaults(fn=cmd_prepare)

    p_shell = sub.add_parser(
        "shell", help="Open an interactive shell in the task workspace"
    )
    p_shell.add_argument("task", help="Task in the form <suite>/<task_id>")
    p_shell.add_argument("--image", default="scibench:0.1", help="Docker image tag")
    p_shell.add_argument("--network", choices=["on", "off"], default="on")
    p_shell.add_argument("--run-id", default="")
    p_shell.add_argument(
        "cmd",
        nargs="*",
        help="Command to run (use `--` before command flags)",
    )
    p_shell.set_defaults(fn=cmd_shell)

    p_agent = sub.add_parser(
        "agent",
        help="Prepare workdir, run an agent one-shot, then eval",
    )
    p_agent.add_argument("task", help="Task in the form <suite>/<task_id>")
    p_agent.add_argument(
        "--agent",
        default="opencode",
        help="Agent key from agents.json (e.g. opencode)",
    )
    p_agent.add_argument("--agents-config", default=str(AGENTS_CONFIG_DEFAULT))
    p_agent.add_argument("--model", "-m", default="openai/gpt-5.3-codex")
    p_agent.add_argument(
        "--prompt",
        default="",
        help="Override the one-shot message (otherwise uses task.json/default)",
    )
    p_agent.add_argument("--image", default="scibench:0.1", help="Docker image tag")
    p_agent.add_argument("--network", choices=["on", "off"], default="on")
    p_agent.add_argument("--timeout-sec", type=int, default=600)
    p_agent.add_argument("--run-id", default="")
    p_agent.set_defaults(fn=cmd_agent)

    p_op = sub.add_parser(
        "opencode",
        help="Prepare workdir, run OpenCode one-shot, then eval",
    )
    p_op.add_argument("task", help="Task in the form <suite>/<task_id>")
    p_op.add_argument("--model", "-m", default="openai/gpt-5.3-codex")
    p_op.add_argument(
        "--prompt",
        default="",
        help="Override the one-shot message (otherwise uses task.json/default)",
    )
    p_op.add_argument("--agents-config", default=str(AGENTS_CONFIG_DEFAULT))
    p_op.add_argument("--image", default="scibench:0.1", help="Docker image tag")
    p_op.add_argument("--network", choices=["on", "off"], default="on")
    p_op.add_argument("--timeout-sec", type=int, default=600)
    p_op.add_argument("--run-id", default="")
    p_op.set_defaults(fn=cmd_opencode)

    args = p.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
