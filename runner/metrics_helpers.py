import os
import re
import subprocess
from pathlib import Path
from typing import Any

try:
    from runner import results_helpers as _results_helpers
except ModuleNotFoundError:  # pragma: no cover
    import results_helpers as _results_helpers  # type: ignore[no-redef]

_json_line_objects = _results_helpers._json_line_objects

_COPILOT_MODEL_BREAKDOWN_RE = re.compile(
    r"^\s*(?P<model>\S+)\s+"
    r"(?P<input>[0-9][0-9.,]*[kKmM]?)\s+in,\s+"
    r"(?P<output>[0-9][0-9.,]*[kKmM]?)\s+out,\s+"
    r"(?P<cached>[0-9][0-9.,]*[kKmM]?)\s+cached",
    re.MULTILINE,
)


def _usage_metrics_from_usage_dict(usage: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}

    if isinstance(usage.get("input_tokens"), int):
        metrics["agent_input_tokens"] = usage["input_tokens"]
    if isinstance(usage.get("output_tokens"), int):
        metrics["agent_output_tokens"] = usage["output_tokens"]

    cached = usage.get("cached_input_tokens")
    if not isinstance(cached, int):
        cached = usage.get("cache_read_input_tokens")
    if isinstance(cached, int):
        metrics["agent_cached_input_tokens"] = cached

    cache_create = usage.get("cache_creation_input_tokens")
    if isinstance(cache_create, int):
        metrics["agent_cache_creation_input_tokens"] = cache_create

    return metrics


def _parse_human_token_count(raw: str) -> int | None:
    s = raw.strip().lower().replace(",", "")
    mult = 1
    if s.endswith("k"):
        mult = 1000
        s = s[:-1]
    elif s.endswith("m"):
        mult = 1000000
        s = s[:-1]
    try:
        return int(round(float(s) * mult))
    except ValueError:
        return None


def _extract_copilot_usage_metrics(stderr: str) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    matches = list(_COPILOT_MODEL_BREAKDOWN_RE.finditer(stderr))
    if not matches:
        return metrics

    total_in = 0
    total_out = 0
    total_cached = 0
    model_names: list[str] = []
    for match in matches:
        model = match.group("model")
        input_tokens = _parse_human_token_count(match.group("input"))
        output_tokens = _parse_human_token_count(match.group("output"))
        cached_tokens = _parse_human_token_count(match.group("cached"))
        if input_tokens is None or output_tokens is None or cached_tokens is None:
            continue
        model_names.append(model)
        total_in += input_tokens
        total_out += output_tokens
        total_cached += cached_tokens

    if not model_names:
        return {}

    metrics["agent_input_tokens"] = total_in
    metrics["agent_output_tokens"] = total_out
    metrics["agent_cached_input_tokens"] = total_cached
    if len(model_names) == 1:
        metrics["agent_usage_model"] = model_names[0]
    else:
        metrics["agent_usage_model"] = ",".join(model_names)
    return metrics


_OPENCODE_STATS_VALUE_RE = re.compile(
    r"^[^0-9$]*\$?([0-9][0-9,]*(?:\.[0-9]+)?(?:[kKmM])?)"
)


def _extract_boxed_stat_value(text: str, label: str) -> str | None:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = line.strip("│").strip()
        if not line.startswith(label):
            continue
        rest = line[len(label) :].strip()
        match = _OPENCODE_STATS_VALUE_RE.match(rest)
        if match:
            return match.group(1)
    return None


def _extract_opencode_stats_metrics(stdout: str) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    input_raw = _extract_boxed_stat_value(stdout, "Input")
    output_raw = _extract_boxed_stat_value(stdout, "Output")
    cache_read_raw = _extract_boxed_stat_value(stdout, "Cache Read")
    cache_write_raw = _extract_boxed_stat_value(stdout, "Cache Write")

    if input_raw is not None:
        parsed = _parse_human_token_count(input_raw)
        if parsed is not None:
            metrics["agent_input_tokens"] = parsed
    if output_raw is not None:
        parsed = _parse_human_token_count(output_raw)
        if parsed is not None:
            metrics["agent_output_tokens"] = parsed
    if cache_read_raw is not None:
        parsed = _parse_human_token_count(cache_read_raw)
        if parsed is not None:
            metrics["agent_cached_input_tokens"] = parsed
    if cache_write_raw is not None:
        parsed = _parse_human_token_count(cache_write_raw)
        if parsed is not None:
            metrics["agent_cache_creation_input_tokens"] = parsed
    return metrics


def _opencode_state_dir(run_dir: Path) -> Path:
    return run_dir / ".opencode-data"


def _collect_opencode_usage_metrics(*, state_dir: Path) -> dict[str, Any]:
    env = dict(os.environ)
    env["HOME"] = str(state_dir)
    cmd = ["opencode", "stats", "--models", "1"]
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=env,
        )
    except FileNotFoundError:
        return {}
    if proc.returncode != 0:
        return {}
    return _extract_opencode_stats_metrics(proc.stdout)


def _extract_agent_usage_metrics(
    agent_name: str, stdout: str, stderr: str = ""
) -> dict[str, Any]:
    if agent_name == "copilot":
        return _extract_copilot_usage_metrics(stderr)

    if agent_name not in {"opencode", "claude", "codex"}:
        return {}

    objects = _json_line_objects(stdout)
    if not objects:
        return {}

    usage_obj: dict[str, Any] | None = None
    extra_metrics: dict[str, Any] = {}

    if agent_name in {"opencode", "claude"}:
        for obj in objects:
            if obj.get("type") != "result":
                continue
            usage = obj.get("usage")
            if isinstance(usage, dict):
                usage_obj = usage
        if usage_obj is None:
            for obj in objects:
                usage = obj.get("usage")
                if isinstance(usage, dict):
                    usage_obj = usage
    elif agent_name == "codex":
        for obj in objects:
            if obj.get("type") != "turn.completed":
                continue
            usage = obj.get("usage")
            if isinstance(usage, dict):
                usage_obj = usage

    if usage_obj is None:
        return {}

    metrics = _usage_metrics_from_usage_dict(usage_obj)
    metrics.update(extra_metrics)
    return metrics


def _merge_metric_dicts(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    merged.update(extra)
    return merged


def _fill_missing_metric_dicts(
    base: dict[str, Any], fallback: dict[str, Any]
) -> dict[str, Any]:
    merged = dict(base)
    for key, value in fallback.items():
        merged.setdefault(key, value)
    return merged


def _collect_postrun_agent_usage_metrics(
    *,
    agent_name: str,
    run_dir: Path,
    mode: str,
    workdir: Path,
) -> dict[str, Any]:
    if agent_name != "opencode":
        return {}
    return _collect_opencode_usage_metrics(state_dir=_opencode_state_dir(run_dir))
