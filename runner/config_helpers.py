import json
import os
import shlex
import shutil
from pathlib import Path
from typing import Any

try:
    import tomllib as _toml_lib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - fallback for Python <3.11
    try:
        import tomli as _toml_lib  # type: ignore[no-redef]
    except ModuleNotFoundError:  # pragma: no cover
        _toml_lib = None  # type: ignore[assignment]


REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DEFAULT_PATH = REPO_ROOT / "agents_default.toml"


def _expand_path(s: str) -> str:
    return os.path.expandvars(os.path.expanduser(s))


def _resolve_input_toml_path(path: Path, *, repo_root: Path | None = None) -> Path:
    root = repo_root if repo_root is not None else REPO_ROOT
    resolved = Path(_expand_path(str(path)))
    if not resolved.is_absolute():
        resolved = (root / resolved).resolve()
    return resolved


def _load_toml(
    path: Path,
    *,
    kind: str,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    resolved = _resolve_input_toml_path(path, repo_root=repo_root)
    if not resolved.exists():
        raise FileNotFoundError(f"{kind} not found: {resolved}")

    if resolved.suffix.lower() != ".toml":
        raise ValueError(f"{kind} must be TOML: {resolved}")

    if _toml_lib is None:
        raise RuntimeError(
            "TOML parser unavailable (need Python 3.11+ or install tomli)"
        )

    data = _toml_lib.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{kind} root must be a table")
    return data


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_agent_config(
    path: Path,
    *,
    defaults_path: Path | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    override = _load_toml(path, kind="agent config", repo_root=repo_root)
    if int(override.get("version", 0)) != 1:
        raise ValueError(f"Unsupported agent config version: {override.get('version')}")

    name = str(override.get("name", "")).strip()
    if not name:
        raise ValueError("agent config missing required 'name'")

    resolved_defaults_path = (
        defaults_path if defaults_path is not None else AGENTS_DEFAULT_PATH
    )
    defaults = _load_toml(
        resolved_defaults_path,
        kind="agents default config",
        repo_root=repo_root,
    )
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

    filtered = {
        key: value for key, value in override.items() if key not in {"version", "name"}
    }
    merged = _deep_merge(base, filtered)
    merged["name"] = name
    return merged


def _resolve_host_executable(spec: str) -> Path:
    expanded = _expand_path(spec)
    if "/" in expanded or expanded.startswith("."):
        resolved = Path(expanded)
        if resolved.exists():
            return resolved.resolve()
        raise FileNotFoundError(f"Executable not found: {resolved}")

    found = shutil.which(expanded)
    if not found:
        raise FileNotFoundError(f"Executable not found on PATH: {expanded}")
    return Path(found).resolve()


def _normalize_model_options(
    agent_name: str, agent_cfg: dict[str, Any]
) -> dict[str, Any]:
    raw = agent_cfg.get("model_options", {})
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"Agent {agent_name!r} model_options must be an object")
    return dict(raw)


def _model_options_to_args(options: dict[str, Any]) -> str:
    tokens: list[str] = []
    for key in sorted(options.keys()):
        value = options[key]
        if value is None:
            continue
        flag = f"--{str(key).replace('_', '-')}"
        if isinstance(value, bool):
            tokens.append(flag)
            tokens.append("true" if value else "false")
        elif isinstance(value, (int, float, str)):
            tokens.append(flag)
            tokens.append(str(value))
        else:
            tokens.append(flag)
            tokens.append(json.dumps(value, separators=(",", ":"), sort_keys=True))
    return " ".join(shlex.quote(token) for token in tokens)


def _model_options_env(options: dict[str, Any]) -> dict[str, str]:
    env: dict[str, str] = {
        "BENCH_MODEL_OPTIONS_JSON": json.dumps(
            options, separators=(",", ":"), sort_keys=True
        ),
        "BENCH_MODEL_OPTIONS_ARGS": _model_options_to_args(options),
    }
    for key, value in options.items():
        env_key = (
            "BENCH_MODEL_OPT_"
            + "".join(ch if ch.isalnum() else "_" for ch in str(key)).upper()
        )
        if value is None:
            continue
        if isinstance(value, (dict, list)):
            env[env_key] = json.dumps(value, separators=(",", ":"), sort_keys=True)
        elif isinstance(value, bool):
            env[env_key] = "true" if value else "false"
        else:
            env[env_key] = str(value)
    return env


def _inject_model_options_args(cmd: str, options: dict[str, Any]) -> str:
    rendered = _model_options_to_args(options)
    return cmd.replace("${BENCH_MODEL_OPTIONS_ARGS}", rendered).replace(
        "$BENCH_MODEL_OPTIONS_ARGS", rendered
    )
