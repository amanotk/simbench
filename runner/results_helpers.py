import datetime as _dt
import json
from pathlib import Path
from typing import Any

try:
    import tomllib as _toml_lib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - fallback for Python <3.11
    try:
        import tomli as _toml_lib  # type: ignore[no-redef]
    except ModuleNotFoundError:  # pragma: no cover
        _toml_lib = None  # type: ignore[assignment]


def _format_kilotokens(value: int | float) -> str:
    return f"{float(value) / 1000.0:.1f}k"


def _format_summary_metric(key: str, value: Any) -> Any:
    if isinstance(value, (int, float)) and (
        key == "tokens"
        or key == "token"
        or key.endswith("_tokens")
        or key.endswith("_token_count")
    ):
        return _format_kilotokens(value)
    return value


def _print_result_summary(task_ref: str, run_dir: Path, result: dict[str, Any]) -> None:
    status = result.get("status", "unknown")
    score = result.get("score", None)

    print(f"[{task_ref}] Result")
    print(f"- status: {status}")
    print(f"- score: {score}")
    run_id = result.get("run_id")
    if isinstance(run_id, str) and run_id.strip():
        print(f"- run_id: {run_id}")
    started_at = result.get("started_at")
    if isinstance(started_at, str) and started_at.strip():
        print(f"- started_at: {started_at}")
    task = result.get("task")
    if isinstance(task, str) and task.strip():
        print(f"- task: {task}")
    agent = result.get("agent")
    if isinstance(agent, str) and agent.strip():
        print(f"- agent: {agent}")
    model = result.get("model")
    if isinstance(model, str) and model.strip():
        print(f"- model: {model}")
    agent_exit_code = result.get("agent_exit_code")
    if agent_exit_code is not None:
        print(f"- agent_exit_code: {agent_exit_code}")
    eval_exit_code = result.get("eval_exit_code")
    if eval_exit_code is not None:
        print(f"- eval_exit_code: {eval_exit_code}")

    metrics = result.get("metrics")
    if isinstance(metrics, dict) and metrics:
        print("- metrics:")
        for key in sorted(metrics.keys()):
            print(f"  {key}: {_format_summary_metric(key, metrics[key])}")

    print(f"- run_dir: {run_dir}")

    agent_path = run_dir / "agent.toml"
    if agent_path.exists() and agent_path.is_file() and _toml_lib is not None:
        try:
            agent_cfg = _toml_lib.loads(agent_path.read_text(encoding="utf-8"))
        except Exception:
            agent_cfg = {}
        if isinstance(agent_cfg, dict):
            print("- agent")
            name = agent_cfg.get("name")
            if isinstance(name, str) and name.strip():
                print(f'  name: "{name}"')
            model = agent_cfg.get("model")
            if isinstance(model, str) and model.strip():
                print(f'  model: "{model}"')
            model_options = agent_cfg.get("model_options")
            if isinstance(model_options, dict) and model_options:
                for key in sorted(model_options.keys()):
                    val = model_options[key]
                    if isinstance(val, str):
                        rendered = f'"{val}"'
                    elif isinstance(val, bool):
                        rendered = "true" if val else "false"
                    elif isinstance(val, (int, float)):
                        rendered = str(val)
                    else:
                        rendered = json.dumps(
                            val, ensure_ascii=True, separators=(",", ":")
                        )
                    print(f"  {key}: {rendered}")


def _append_metric(result: dict[str, Any], key: str, value: float | None) -> None:
    if value is None:
        return
    metrics = result.get("metrics")
    if not isinstance(metrics, dict):
        metrics = {}
    metrics[key] = round(float(value), 6)
    result["metrics"] = metrics


def _set_metric_value(result: dict[str, Any], key: str, value: Any) -> None:
    metrics = result.get("metrics")
    if not isinstance(metrics, dict):
        metrics = {}
    metrics[key] = value
    result["metrics"] = metrics


def _json_line_objects(text: str) -> list[dict[str, Any]]:
    objs: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            objs.append(obj)
    return objs


def _merge_metrics(result: dict[str, Any], metrics: dict[str, Any]) -> None:
    for key, value in metrics.items():
        _set_metric_value(result, key, value)


def _write_failure_result(
    run_dir: Path,
    *,
    error: str,
    message: str,
    run_id: str,
    started_at: str,
    task_ref: str,
    agent_name: str | None = None,
    model: str | None = None,
    agent_exit_code: int | str | None = None,
    eval_exit_code: int | str | None = None,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "failed",
        "score": 0.0,
        "error": error,
        "message": message,
        "run_id": run_id,
        "started_at": started_at,
        "task": task_ref,
    }
    if agent_name:
        result["agent"] = agent_name
    if model:
        result["model"] = model
    if agent_exit_code is not None:
        result["agent_exit_code"] = agent_exit_code
    if eval_exit_code is not None:
        result["eval_exit_code"] = eval_exit_code
    if metrics:
        result["metrics"] = metrics
    (run_dir / "result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def _run_started_at() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _annotate_result_metadata(
    result: dict[str, Any],
    *,
    run_id: str,
    started_at: str,
    task_ref: str,
    agent_name: str | None = None,
    model: str | None = None,
    agent_exit_code: int | str | None = None,
    eval_exit_code: int | str | None = None,
) -> None:
    result["run_id"] = run_id
    result["started_at"] = started_at
    result["task"] = task_ref
    if agent_name:
        result["agent"] = agent_name
    if model:
        result["model"] = model
    if agent_exit_code is not None:
        result["agent_exit_code"] = agent_exit_code
    if eval_exit_code is not None:
        result["eval_exit_code"] = eval_exit_code
