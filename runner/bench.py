#!/usr/bin/env python3

import argparse
import datetime as _dt
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from typing import Any, Callable
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BENCH_ROOT = REPO_ROOT / "benchmarks"
TEST_TASK_ROOT = REPO_ROOT / "tests" / "test-tasks"
RUNS_ROOT = REPO_ROOT / "runs"
AGENTS_DEFAULT_PATH = REPO_ROOT / "agents_default.toml"


def _vprint(enabled: bool, msg: str) -> None:
    if enabled:
        print(msg, file=sys.stderr)


def _vsection(enabled: bool, title: str) -> None:
    if enabled:
        print(f"\n=== {title} ===", file=sys.stderr)


try:
    from runner import results_helpers as _results_helpers
except ModuleNotFoundError:  # pragma: no cover
    import results_helpers as _results_helpers  # type: ignore[no-redef]

try:
    from runner import execution_helpers as _execution_helpers
except ModuleNotFoundError:  # pragma: no cover
    import execution_helpers as _execution_helpers  # type: ignore[no-redef]

try:
    from runner import stream_pretty as _stream_pretty
except ModuleNotFoundError:  # pragma: no cover
    import stream_pretty as _stream_pretty  # type: ignore[no-redef]

try:
    from runner import metrics_helpers as _metrics_helpers
except ModuleNotFoundError:  # pragma: no cover
    import metrics_helpers as _metrics_helpers  # type: ignore[no-redef]

try:
    from runner import task_loading_helpers as _task_loading_helpers
except ModuleNotFoundError:  # pragma: no cover
    import task_loading_helpers as _task_loading_helpers  # type: ignore[no-redef]

try:
    from runner import config_helpers as _config_helpers
except ModuleNotFoundError:  # pragma: no cover
    import config_helpers as _config_helpers  # type: ignore[no-redef]

try:
    from runner import docker_runner_helpers as _docker_runner_helpers
except ModuleNotFoundError:  # pragma: no cover
    import docker_runner_helpers as _docker_runner_helpers  # type: ignore[no-redef]

try:
    from runner import execution_agent as _execution_agent
except ModuleNotFoundError:  # pragma: no cover
    import execution_agent as _execution_agent  # type: ignore[no-redef]

try:
    from runner import run_record_helpers as _run_record_helpers
except ModuleNotFoundError:  # pragma: no cover
    import run_record_helpers as _run_record_helpers  # type: ignore[no-redef]

try:
    from runner import publish_helpers as _publish_helpers
except ModuleNotFoundError:  # pragma: no cover
    import publish_helpers as _publish_helpers  # type: ignore[no-redef]

_append_metric = _results_helpers._append_metric
_annotate_result_metadata = _results_helpers._annotate_result_metadata
_format_kilotokens = _results_helpers._format_kilotokens
_format_summary_metric = _results_helpers._format_summary_metric
_json_line_objects = _results_helpers._json_line_objects
_merge_metrics = _results_helpers._merge_metrics
_print_result_summary = _results_helpers._print_result_summary
_run_started_at = _results_helpers._run_started_at
_set_metric_value = _results_helpers._set_metric_value
_write_failure_result = _results_helpers._write_failure_result

_usage_metrics_from_usage_dict = _metrics_helpers._usage_metrics_from_usage_dict
_COPILOT_MODEL_BREAKDOWN_RE = _metrics_helpers._COPILOT_MODEL_BREAKDOWN_RE
_OPENCODE_STATS_VALUE_RE = _metrics_helpers._OPENCODE_STATS_VALUE_RE
_parse_human_token_count = _metrics_helpers._parse_human_token_count
_extract_copilot_usage_metrics = _metrics_helpers._extract_copilot_usage_metrics
_extract_boxed_stat_value = _metrics_helpers._extract_boxed_stat_value
_extract_opencode_stats_metrics = _metrics_helpers._extract_opencode_stats_metrics
_collect_opencode_usage_metrics = _metrics_helpers._collect_opencode_usage_metrics
_extract_agent_usage_metrics = _metrics_helpers._extract_agent_usage_metrics
_merge_metric_dicts = _metrics_helpers._merge_metric_dicts
_fill_missing_metric_dicts = _metrics_helpers._fill_missing_metric_dicts
_collect_postrun_agent_usage_metrics = (
    _metrics_helpers._collect_postrun_agent_usage_metrics
)

_merge_run_provenance = _run_record_helpers.merge_run_provenance

_build_publication_payload = _publish_helpers.build_publication_payload

_StreamPrettyState = _stream_pretty._StreamPrettyState
_format_agent_stream_event = _stream_pretty._format_agent_stream_event
_format_agent_plain_stream_line = _stream_pretty._format_agent_plain_stream_line
_phase_agent_name = _stream_pretty._phase_agent_name
flush_stream_state = _stream_pretty.flush_stream_state

Task = _task_loading_helpers.Task


def _run_capture_stream(
    cmd: list[str],
    *,
    timeout_sec: int,
    verbose: bool,
    phase: str,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    pretty_timeline: bool = False,
    timeout_cleanup: Callable[[], None] | None = None,
) -> subprocess.CompletedProcess:
    return _execution_helpers._run_capture_stream(
        cmd,
        timeout_sec=timeout_sec,
        verbose=verbose,
        phase=phase,
        cwd=cwd,
        env=env,
        pretty_timeline=pretty_timeline,
        timeout_cleanup=timeout_cleanup,
        subprocess_mod=subprocess,
    )


_normalize_model_options = _config_helpers._normalize_model_options
_model_options_to_args = _config_helpers._model_options_to_args
_model_options_env = _config_helpers._model_options_env
_inject_model_options_args = _config_helpers._inject_model_options_args


_timed_bash_script = _execution_helpers._timed_bash_script
_extract_inner_sec = _execution_helpers._extract_inner_sec


def _opencode_state_dir(run_dir: Path) -> Path:
    return run_dir / ".opencode-data"


_cmd_str = _execution_helpers._cmd_str


def _cleanup_docker_container(
    *, container_name: str, phase: str, verbose: bool
) -> None:
    _execution_helpers._cleanup_docker_container(
        container_name=container_name,
        phase=phase,
        verbose=verbose,
        subprocess_mod=subprocess,
    )


_expand_path = _config_helpers._expand_path


def _resolve_input_toml_path(path: Path) -> Path:
    return _config_helpers._resolve_input_toml_path(path, repo_root=REPO_ROOT)


def _load_toml(path: Path, *, kind: str) -> dict[str, Any]:
    return _config_helpers._load_toml(path, kind=kind, repo_root=REPO_ROOT)


_deep_merge = _config_helpers._deep_merge


def _load_agent_config(path: Path) -> dict[str, Any]:
    return _config_helpers._load_agent_config(
        path,
        defaults_path=AGENTS_DEFAULT_PATH,
        repo_root=REPO_ROOT,
    )


_resolve_host_executable = _config_helpers._resolve_host_executable


def _task_roots(*, include_test_tasks: bool) -> list[Path]:
    return _task_loading_helpers._task_roots(
        include_test_tasks=include_test_tasks,
        bench_root=BENCH_ROOT,
        test_task_root=TEST_TASK_ROOT,
    )


def _task_path(root: Path, suite: str, task_id: str) -> Path:
    return _task_loading_helpers._task_path(root, suite, task_id)


def _parse_task_ref(task_ref: str) -> tuple[Path | None, str, str]:
    return _task_loading_helpers._parse_task_ref(
        task_ref,
        bench_root=BENCH_ROOT,
        test_task_root=TEST_TASK_ROOT,
        repo_root=REPO_ROOT,
    )


def _task_meta_bool(task: Task, key: str) -> bool:
    return _task_loading_helpers._task_meta_bool(task, key)


def _suite_shared_workspace_dir(task: Task) -> Path:
    return _task_loading_helpers._suite_shared_workspace_dir(task)


def _suite_shared_eval_dir(task: Task) -> Path:
    return _task_loading_helpers._suite_shared_eval_dir(task)


def _shared_eval_mount_dir(task: Task) -> Path | None:
    use_shared_eval = _task_meta_bool(task, "use_shared_eval")
    if not use_shared_eval:
        return None
    shared_eval = _suite_shared_eval_dir(task)
    if not shared_eval.exists() or not shared_eval.is_dir():
        raise FileNotFoundError(
            "task.toml use_shared_eval=true but suite shared eval "
            f"directory is missing: {shared_eval}"
        )
    return shared_eval


def _coerce_text(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    return str(v)


def _write_run_record_json(run_dir: Path, result: dict[str, Any]) -> None:
    run_record = _merge_run_provenance(dict(result), REPO_ROOT)
    (run_dir / "run.json").write_text(
        json.dumps(run_record, indent=2) + "\n", encoding="utf-8"
    )


def _resolve_publish_run_dir(run_dir_text: str) -> Path:
    run_dir = Path(_expand_path(run_dir_text))
    if not run_dir.is_absolute():
        run_dir = (Path.cwd() / run_dir).resolve()
    return run_dir


def _load_task(suite: str, task_id: str, *, root: Path | None = None) -> Task:
    return _task_loading_helpers._load_task(
        suite,
        task_id,
        root=root,
        bench_root=BENCH_ROOT,
        test_task_root=TEST_TASK_ROOT,
        repo_root=REPO_ROOT,
    )


def _iter_tasks(*, include_test_tasks: bool = False):
    yield from _task_loading_helpers._iter_tasks(
        include_test_tasks=include_test_tasks,
        bench_root=BENCH_ROOT,
        test_task_root=TEST_TASK_ROOT,
    )


def cmd_list(_args: argparse.Namespace) -> int:
    for suite, task_id in _iter_tasks():
        print(f"{suite}/{task_id}")
    return 0


def _check_task(task: Task) -> tuple[list[str], list[str]]:
    return _task_loading_helpers._check_task(task)


def _print_publish_payload(run_dir: Path, payload: dict[str, Any]) -> None:
    print(f"[{run_dir}] Publication")
    print("payload:")
    payload_json = {key: value for key, value in payload.items() if key != "body"}
    print(json.dumps(payload_json, indent=2, ensure_ascii=False, sort_keys=True))
    print("body:")
    print(payload["body"], end="")


def cmd_publish(args: argparse.Namespace) -> int:
    run_dir = _resolve_publish_run_dir(str(args.run_dir))
    if not run_dir.exists() or not run_dir.is_dir():
        print(f"run directory not found or not a directory: {run_dir}", file=sys.stderr)
        return 2

    try:
        payload = _build_publication_payload(run_dir)
    except (
        FileNotFoundError,
        NotADirectoryError,
        json.JSONDecodeError,
        ValueError,
    ) as e:
        print(f"Failed to load publication payload: {e}", file=sys.stderr)
        return 2

    _print_publish_payload(run_dir, payload)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    task_refs: list[tuple[str, str]] = []
    task_root: Path | None = None

    if args.task:
        try:
            task_root, suite, task_id = _parse_task_ref(args.task)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 2
        task_refs.append((suite, task_id))
    else:
        task_refs.extend(_iter_tasks())

    if not task_refs:
        print("No tasks found under benchmarks/", file=sys.stderr)
        return 2

    had_errors = False

    for suite, task_id in task_refs:
        label = f"{suite}/{task_id}"
        try:
            task = _load_task(suite, task_id, root=task_root)
        except Exception as e:
            print(f"[{label}] FAIL")
            print(f"- error: {e}")
            had_errors = True
            continue

        errors, warnings = _check_task(task)
        if errors:
            had_errors = True
            print(f"[{label}] FAIL")
            for e in errors:
                print(f"- error: {e}")
        else:
            print(f"[{label}] PASS")

        for w in warnings:
            print(f"- warning: {w}")

    return 1 if had_errors else 0


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

    use_shared_workspace = _task_meta_bool(task, "use_shared_workspace")
    if use_shared_workspace:
        shared_workspace = _suite_shared_workspace_dir(task)
        if not shared_workspace.exists() or not shared_workspace.is_dir():
            raise FileNotFoundError(
                "task.toml use_shared_workspace=true but suite shared workspace "
                f"directory is missing: {shared_workspace}"
            )
        shutil.copytree(shared_workspace, workdir)
        shutil.copytree(task.workspace_tpl, workdir, dirs_exist_ok=True)
    else:
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
    shared_eval_dir: Path | None,
    timeout_sec: int,
    extra_env: dict[str, str] | None = None,
    verbose: bool = False,
    cmd_log_path: Path | None = None,
) -> tuple[subprocess.CompletedProcess, float | None]:
    return _docker_runner_helpers._run_docker_eval(
        image=image,
        workdir=workdir,
        eval_dir=eval_dir,
        eval_cmd=eval_cmd,
        shared_eval_dir=shared_eval_dir,
        timeout_sec=timeout_sec,
        extra_env=extra_env,
        verbose=verbose,
        cmd_log_path=cmd_log_path,
        run_capture_stream=_run_capture_stream,
        cleanup_docker_container=_cleanup_docker_container,
        cmd_str=_cmd_str,
        timed_bash_script=_timed_bash_script,
        extract_inner_sec=_extract_inner_sec,
        subprocess_mod=subprocess,
    )


def _run_docker_shell(*, image: str, workdir: Path, cmd: list[str]) -> int:
    return _docker_runner_helpers._run_docker_shell(
        image=image,
        workdir=workdir,
        cmd=cmd,
        subprocess_mod=subprocess,
    )


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
) -> tuple[subprocess.CompletedProcess, float | None]:
    # Keep bench.py as the stable compatibility seam for agent execution.
    return _execution_agent._run_agent_in_docker(
        image=image,
        workdir=workdir,
        run_dir=run_dir,
        agent_name=agent_name,
        agent_cfg=agent_cfg,
        model=model,
        timeout_sec=timeout_sec,
        extra_env=extra_env,
        verbose=verbose,
        cmd_log_path=cmd_log_path,
        run_capture_stream=_run_capture_stream,
        cleanup_docker_container=_cleanup_docker_container,
        cmd_str=_cmd_str,
        timed_bash_script=_timed_bash_script,
        extract_inner_sec=_extract_inner_sec,
        normalize_model_options=_normalize_model_options,
        model_options_env=_model_options_env,
        inject_model_options_args=_inject_model_options_args,
        resolve_host_executable=_resolve_host_executable,
        expand_path=_expand_path,
        vprint=_vprint,
        vsection=_vsection,
        subprocess_mod=subprocess,
        os_mod=os,
        secrets_mod=secrets,
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
) -> tuple[subprocess.CompletedProcess, float | None]:
    # Keep bench.py as the stable compatibility seam for agent execution.
    return _execution_agent._run_agent_on_host(
        workdir=workdir,
        run_dir=run_dir,
        agent_name=agent_name,
        agent_cfg=agent_cfg,
        model=model,
        timeout_sec=timeout_sec,
        extra_env=extra_env,
        verbose=verbose,
        cmd_log_path=cmd_log_path,
        run_capture_stream=_run_capture_stream,
        normalize_model_options=_normalize_model_options,
        model_options_env=_model_options_env,
        inject_model_options_args=_inject_model_options_args,
        resolve_host_executable=_resolve_host_executable,
        vprint=_vprint,
        vsection=_vsection,
        subprocess_mod=subprocess,
        os_mod=os,
        time_mod=time,
    )


def cmd_run(args: argparse.Namespace) -> int:
    # Full benchmark run: agent solve + authoritative eval.
    return _cmd_agent_common(args=args)


def cmd_eval(args: argparse.Namespace) -> int:
    verbose = not bool(args.quiet)

    try:
        task_root, suite, task_id = _parse_task_ref(args.task)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    task = _load_task(suite, task_id, root=task_root)

    eval_cmd = str(task.meta.get("eval_cmd", ""))
    if not eval_cmd:
        print(f"Missing eval_cmd in {task.task_toml_path}", file=sys.stderr)
        return 2

    timeout_sec = int(task.meta.get("time_limit_sec", args.timeout_sec))
    try:
        shared_eval_dir = _shared_eval_mount_dir(task)
    except (FileNotFoundError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 2

    run_id = args.run_id or _gen_run_id()
    started_at = _run_started_at()
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

    _vsection(verbose, "RUN SETUP")
    _vprint(verbose, f"run_id={run_id}")
    _vprint(verbose, f"run_dir={run_dir}")
    _vprint(verbose, f"workdir={workdir}")
    _vprint(verbose, f"task={suite}/{task_id}")
    _vprint(
        verbose,
        f"image={args.image} timeout_sec={timeout_sec}",
    )

    try:
        proc, eval_inner_sec = _run_docker_eval(
            image=args.image,
            workdir=workdir,
            eval_dir=task.eval_dir,
            eval_cmd=eval_cmd,
            shared_eval_dir=shared_eval_dir,
            timeout_sec=timeout_sec,
            verbose=verbose,
            cmd_log_path=logs_dir / "eval.docker_cmd.txt",
        )
    except FileNotFoundError as e:
        print(f"Failed to run docker: {e}", file=sys.stderr)
        result = _write_failure_result(
            run_dir,
            error="eval_setup",
            message=str(e),
            run_id=run_id,
            started_at=started_at,
            task_ref=f"{suite}/{task_id}",
            eval_exit_code="setup_error",
        )
        _write_run_record_json(run_dir, result)
        return 1
    except subprocess.TimeoutExpired:
        (logs_dir / "eval.stdout.txt").write_text("", encoding="utf-8")
        (logs_dir / "eval.stderr.txt").write_text("Timed out\n", encoding="utf-8")
        result = _write_failure_result(
            run_dir,
            error="eval_timeout",
            message=f"Timed out after {timeout_sec}s during eval phase",
            run_id=run_id,
            started_at=started_at,
            task_ref=f"{suite}/{task_id}",
            eval_exit_code="timeout",
        )
        _write_run_record_json(run_dir, result)
        print(f"Timed out after {timeout_sec}s during eval phase", file=sys.stderr)
        _print_result_summary(f"{suite}/{task_id}", run_dir, result)
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
            _annotate_result_metadata(
                result,
                run_id=run_id,
                started_at=started_at,
                task_ref=f"{suite}/{task_id}",
                eval_exit_code=proc.returncode,
            )
            _append_metric(result, "eval_inner_sec", eval_inner_sec)
            (run_dir / "result.json").write_text(
                json.dumps(result, indent=2) + "\n", encoding="utf-8"
            )
            _write_run_record_json(run_dir, result)
            status = result.get("status", "unknown")
            _print_result_summary(f"{suite}/{task_id}", run_dir, result)
            if status != "passed":
                final_rc = 1
        except Exception:
            failure_result = _write_failure_result(
                run_dir,
                error="result_parse_error",
                message="Eval completed but result.json could not be parsed",
                run_id=run_id,
                started_at=started_at,
                task_ref=f"{suite}/{task_id}",
                eval_exit_code=proc.returncode,
            )
            _write_run_record_json(run_dir, failure_result)
            print(f"{suite}/{task_id}: wrote result.json")
    else:
        print(f"{suite}/{task_id}: eval completed (no result.json found)")
        result = _write_failure_result(
            run_dir,
            error="missing_result",
            message="Eval completed but did not produce result.json",
            run_id=run_id,
            started_at=started_at,
            task_ref=f"{suite}/{task_id}",
            eval_exit_code=proc.returncode,
        )
        _write_run_record_json(run_dir, result)
        _print_result_summary(f"{suite}/{task_id}", run_dir, result)
        final_rc = 1

    return final_rc


def cmd_prepare(args: argparse.Namespace) -> int:
    try:
        task_root, suite, task_id = _parse_task_ref(args.task)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    task = _load_task(suite, task_id, root=task_root)

    try:
        _load_agent_config(Path(str(args.agents)))
    except Exception as e:
        print(f"Failed to load agent config: {e}", file=sys.stderr)
        return 2

    run_id = args.run_id or _gen_run_id()
    try:
        run_dir, workdir, _logs_dir = _prepare_run_dir(
            task=task,
            run_id=run_id,
            result_dir=args.result_dir,
        )
    except (FileExistsError, FileNotFoundError, ValueError) as e:
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
    try:
        task_root, suite, task_id = _parse_task_ref(args.task)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    task = _load_task(suite, task_id, root=task_root)

    try:
        _load_agent_config(Path(str(args.agents)))
    except Exception as e:
        print(f"Failed to load agent config: {e}", file=sys.stderr)
        return 2

    run_id = args.run_id or _gen_run_id()
    try:
        run_dir, workdir, _logs_dir = _prepare_run_dir(
            task=task,
            run_id=run_id,
            result_dir=args.result_dir,
        )
    except (FileExistsError, FileNotFoundError, ValueError) as e:
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
            cmd=cmd,
        )
    except FileNotFoundError as e:
        print(f"Failed to run docker: {e}", file=sys.stderr)
        return 1


def _cmd_agent_common(*, args: argparse.Namespace) -> int:
    verbose = not bool(args.quiet)

    try:
        task_root, suite, task_id = _parse_task_ref(args.task)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    task = _load_task(suite, task_id, root=task_root)

    eval_cmd = str(task.meta.get("eval_cmd", ""))
    if not eval_cmd:
        print(f"Missing eval_cmd in {task.task_toml_path}", file=sys.stderr)
        return 2

    timeout_sec = int(task.meta.get("time_limit_sec", args.timeout_sec))
    try:
        shared_eval_dir = _shared_eval_mount_dir(task)
    except (FileNotFoundError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 2
    run_id = args.run_id or _gen_run_id()
    started_at = _run_started_at()
    try:
        run_dir, workdir, logs_dir = _prepare_run_dir(
            task=task,
            run_id=run_id,
            result_dir=args.result_dir,
        )
    except (FileExistsError, FileNotFoundError, ValueError) as e:
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

    agent_name = configured_name

    agent_cfg_path = _resolve_input_toml_path(Path(str(args.agents)))
    (run_dir / "agent.toml").write_text(
        agent_cfg_path.read_text(encoding="utf-8"), encoding="utf-8"
    )

    mode = str(agent_cfg.get("mode", "docker")).strip()
    if mode not in ("docker", "host"):
        print(f"Unknown agent mode: {mode!r} (expected docker|host)", file=sys.stderr)
        return 2

    model_source = "model"
    model = str(agent_cfg.get("model", "")).strip()
    if not model:
        model = str(agent_cfg.get("default_model", "")).strip()
        model_source = "default_model"
    if model:
        _vprint(verbose, f"using {model_source} from agents config: {model}")
    if not model:
        print(
            f"No model configured. Set model for agent {agent_name!r} in agents config",
            file=sys.stderr,
        )
        return 2
    if agent_name == "opencode" and "/" not in model:
        before = model
        model = f"openai/{model}"
        _vprint(verbose, f"normalized model for opencode: {before} -> {model}")

    _vsection(verbose, "RUN SETUP")
    _vprint(verbose, f"run_id={run_id}")
    _vprint(verbose, f"run_dir={run_dir}")
    _vprint(verbose, f"workdir={workdir}")
    _vprint(verbose, f"agent={agent_name} mode={mode}")
    _vprint(verbose, f"agents_config={agents_config_path}")

    default_prompt = (
        "Solve the attached spec. Edit files in the working directory. "
        "Run the public tests while working and make them pass. "
        "If you need a toolchain, run commands via Docker using the image "
        f"{args.image!r}. Example: "
        f'docker run --rm -v "$PWD":/work -w /work {args.image} bash -lc "pytest -q"'
    )

    prompt = ""
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
            op, agent_inner_sec = _run_agent_in_docker(
                image=args.image,
                workdir=workdir,
                run_dir=run_dir,
                agent_name=agent_name,
                agent_cfg=agent_cfg,
                model=model,
                timeout_sec=timeout_sec,
                extra_env=extra_env,
                verbose=verbose,
                cmd_log_path=logs_dir / "agent.docker_cmd.txt",
            )
        elif mode == "host":
            op, agent_inner_sec = _run_agent_on_host(
                workdir=workdir,
                run_dir=run_dir,
                agent_name=agent_name,
                agent_cfg=agent_cfg,
                model=model,
                timeout_sec=timeout_sec,
                extra_env=extra_env,
                verbose=verbose,
                cmd_log_path=logs_dir / "agent.host_cmd.txt",
            )
        else:
            raise ValueError(f"Unknown agent mode: {mode!r} (expected docker|host)")
    except (FileNotFoundError, ValueError) as e:
        (logs_dir / "agent.stderr.txt").write_text(str(e) + "\n", encoding="utf-8")
        (logs_dir / "agent.exit_code.txt").write_text("setup_error\n", encoding="utf-8")
        result = _write_failure_result(
            run_dir,
            error="agent_setup",
            message=str(e),
            run_id=run_id,
            started_at=started_at,
            task_ref=f"{suite}/{task_id}",
            agent_name=agent_name,
            model=model,
            agent_exit_code="setup_error",
        )
        _write_run_record_json(run_dir, result)
        print(f"Agent setup failed: {e}", file=sys.stderr)
        _print_result_summary(f"{suite}/{task_id}", run_dir, result)
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
        metrics = _extract_agent_usage_metrics(
            agent_name,
            _coerce_text(e.stdout),
            _coerce_text(e.stderr),
        )
        metrics = _fill_missing_metric_dicts(
            metrics,
            _collect_postrun_agent_usage_metrics(
                agent_name=agent_name,
                run_dir=run_dir,
                mode=mode,
                workdir=workdir,
            ),
        )
        result = _write_failure_result(
            run_dir,
            error="agent_timeout",
            message=f"Timed out after {timeout_sec}s during agent phase",
            run_id=run_id,
            started_at=started_at,
            task_ref=f"{suite}/{task_id}",
            agent_name=agent_name,
            model=model,
            agent_exit_code="timeout",
            metrics=metrics or None,
        )
        _write_run_record_json(run_dir, result)
        print(f"Timed out after {timeout_sec}s during agent phase", file=sys.stderr)
        _print_result_summary(f"{suite}/{task_id}", run_dir, result)
        print(str(run_dir))
        return 1

    (logs_dir / "agent.stdout.txt").write_text(op.stdout, encoding="utf-8")
    (logs_dir / "agent.stderr.txt").write_text(op.stderr, encoding="utf-8")
    (logs_dir / "agent.exit_code.txt").write_text(
        str(op.returncode) + "\n", encoding="utf-8"
    )
    agent_usage_metrics = _extract_agent_usage_metrics(agent_name, op.stdout, op.stderr)
    agent_usage_metrics = _fill_missing_metric_dicts(
        agent_usage_metrics,
        _collect_postrun_agent_usage_metrics(
            agent_name=agent_name,
            run_dir=run_dir,
            mode=mode,
            workdir=workdir,
        ),
    )
    if op.returncode != 0:
        metrics = dict(agent_usage_metrics)
        if agent_inner_sec is not None:
            metrics["agent_inner_sec"] = round(float(agent_inner_sec), 6)
        result = _write_failure_result(
            run_dir,
            error="agent_failed",
            message=f"Agent exited with code {op.returncode}",
            run_id=run_id,
            started_at=started_at,
            task_ref=f"{suite}/{task_id}",
            agent_name=agent_name,
            model=model,
            agent_exit_code=op.returncode,
            metrics=metrics or None,
        )
        _write_run_record_json(run_dir, result)
        print(f"agent failed with exit code {op.returncode}", file=sys.stderr)
        print(f"Logs: {logs_dir}", file=sys.stderr)
        if op.stderr.strip():
            print(op.stderr.strip(), file=sys.stderr)
        _print_result_summary(f"{suite}/{task_id}", run_dir, result)
        print(str(run_dir))
        return 1

    # Evaluate the same workdir using the hidden harness.
    # Keep eval harness output hidden in default run UX to avoid exposing
    # hidden test details via streamed stdout/stderr.
    try:
        proc, eval_inner_sec = _run_docker_eval(
            image=args.image,
            workdir=workdir,
            eval_dir=task.eval_dir,
            eval_cmd=eval_cmd,
            shared_eval_dir=shared_eval_dir,
            timeout_sec=timeout_sec,
            verbose=False,
            cmd_log_path=logs_dir / "eval.docker_cmd.txt",
        )
    except FileNotFoundError as e:
        print(f"Failed to run docker: {e}", file=sys.stderr)
        result = _write_failure_result(
            run_dir,
            error="eval_setup",
            message=str(e),
            run_id=run_id,
            started_at=started_at,
            task_ref=f"{suite}/{task_id}",
            agent_name=agent_name,
            model=model,
            agent_exit_code=op.returncode,
            eval_exit_code="setup_error",
            metrics=agent_usage_metrics or None,
        )
        _write_run_record_json(run_dir, result)
        return 1
    except subprocess.TimeoutExpired:
        (logs_dir / "eval.stdout.txt").write_text("", encoding="utf-8")
        (logs_dir / "eval.stderr.txt").write_text("Timed out\n", encoding="utf-8")
        metrics = dict(agent_usage_metrics)
        if agent_inner_sec is not None:
            metrics["agent_inner_sec"] = round(float(agent_inner_sec), 6)
        result = _write_failure_result(
            run_dir,
            error="eval_timeout",
            message=f"Timed out after {timeout_sec}s during eval phase",
            run_id=run_id,
            started_at=started_at,
            task_ref=f"{suite}/{task_id}",
            agent_name=agent_name,
            model=model,
            agent_exit_code=op.returncode,
            eval_exit_code="timeout",
            metrics=metrics or None,
        )
        _write_run_record_json(run_dir, result)
        print(f"Timed out after {timeout_sec}s during eval phase", file=sys.stderr)
        _print_result_summary(f"{suite}/{task_id}", run_dir, result)
        print(str(run_dir))
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
            _annotate_result_metadata(
                result,
                run_id=run_id,
                started_at=started_at,
                task_ref=f"{suite}/{task_id}",
                agent_name=agent_name,
                model=model,
                agent_exit_code=op.returncode,
                eval_exit_code=proc.returncode,
            )
            _append_metric(result, "agent_inner_sec", agent_inner_sec)
            _append_metric(result, "eval_inner_sec", eval_inner_sec)
            _merge_metrics(result, agent_usage_metrics)
            (run_dir / "result.json").write_text(
                json.dumps(result, indent=2) + "\n", encoding="utf-8"
            )
            _write_run_record_json(run_dir, result)
            status = result.get("status", "unknown")
            _print_result_summary(f"{suite}/{task_id}", run_dir, result)
            if status != "passed":
                final_rc = 1
        except Exception:
            failure_result = _write_failure_result(
                run_dir,
                error="result_parse_error",
                message="Eval completed but result.json could not be parsed",
                run_id=run_id,
                started_at=started_at,
                task_ref=f"{suite}/{task_id}",
                agent_name=agent_name,
                model=model,
                agent_exit_code=op.returncode,
                eval_exit_code=proc.returncode,
                metrics=agent_usage_metrics or None,
            )
            _write_run_record_json(run_dir, failure_result)
            print(f"{suite}/{task_id}: wrote result.json")
            final_rc = 1
    else:
        print(f"{suite}/{task_id}: eval completed (no result.json found)")
        result = _write_failure_result(
            run_dir,
            error="missing_result",
            message="Eval completed but did not produce result.json",
            run_id=run_id,
            started_at=started_at,
            task_ref=f"{suite}/{task_id}",
            agent_name=agent_name,
            model=model,
            agent_exit_code=op.returncode,
            eval_exit_code=proc.returncode,
            metrics=agent_usage_metrics or None,
        )
        _write_run_record_json(run_dir, result)
        _print_result_summary(f"{suite}/{task_id}", run_dir, result)
        final_rc = 1

    return final_rc


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="bench")
    p.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress internal runner action logs",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List available tasks")
    p_list.set_defaults(fn=cmd_list)

    p_check = sub.add_parser("check", help="Validate task spec/layout")
    p_check.add_argument(
        "task",
        nargs="?",
        default="",
        help="Optional task in the form [bench:|test:]<suite>/<task_id> (defaults to listed benchmark tasks)",
    )
    p_check.set_defaults(fn=cmd_check)

    p_run = sub.add_parser("run", help="Run agent solve + eval")
    p_run.add_argument("agents", help="Path to single-agent TOML config")
    p_run.add_argument("task", help="Task in the form [bench:|test:]<suite>/<task_id>")
    p_run.add_argument("--image", default="simbench:0.1", help="Docker image tag")
    p_run.add_argument("--timeout-sec", type=int, default=600)
    p_run.add_argument("--run-id", default="")
    p_run.add_argument("--result-dir", default="")
    p_run.set_defaults(fn=cmd_run)

    p_eval = sub.add_parser("eval", help="Run eval-only on an existing workdir")
    p_eval.add_argument("task", help="Task in the form [bench:|test:]<suite>/<task_id>")
    p_eval.add_argument("--workdir", required=True)
    p_eval.add_argument("--image", default="simbench:0.1", help="Docker image tag")
    p_eval.add_argument("--timeout-sec", type=int, default=600)
    p_eval.add_argument("--run-id", default="")
    p_eval.add_argument("--result-dir", default="")
    p_eval.set_defaults(fn=cmd_eval)

    p_publish = sub.add_parser(
        "publish", help="Render a publication payload for a completed run"
    )
    p_publish.add_argument("run_dir", help="Path to a completed run directory")
    p_publish.set_defaults(fn=cmd_publish)

    p_prepare = sub.add_parser("prepare", help="Create an isolated run workspace")
    p_prepare.add_argument("agents", help="Path to single-agent TOML config")
    p_prepare.add_argument(
        "task", help="Task in the form [bench:|test:]<suite>/<task_id>"
    )
    p_prepare.add_argument("--run-id", default="")
    p_prepare.add_argument("--result-dir", default="")
    p_prepare.set_defaults(fn=cmd_prepare)

    p_shell = sub.add_parser(
        "shell", help="Open an interactive shell in the task workspace"
    )
    p_shell.add_argument("agents", help="Path to single-agent TOML config")
    p_shell.add_argument(
        "task", help="Task in the form [bench:|test:]<suite>/<task_id>"
    )
    p_shell.add_argument("--image", default="simbench:0.1", help="Docker image tag")
    p_shell.add_argument("--run-id", default="")
    p_shell.add_argument("--result-dir", default="")
    p_shell.add_argument(
        "cmd",
        nargs="*",
        help="Command to run (use `--` before command flags)",
    )
    p_shell.set_defaults(fn=cmd_shell)

    args = p.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
