import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

try:
    import tomllib as _toml_lib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - fallback for Python <3.11
    try:
        import tomli as _toml_lib  # type: ignore[no-redef]
    except ModuleNotFoundError:  # pragma: no cover
        _toml_lib = None  # type: ignore[assignment]


@dataclass(frozen=True)
class Task:
    suite: str
    task_id: str
    path: Path
    spec_path: Path
    task_toml_path: Path
    workspace_tpl: Path
    eval_dir: Path
    meta: dict[str, Any]


def _task_roots(
    *, include_test_tasks: bool, bench_root: Path, test_task_root: Path
) -> list[Path]:
    roots = [bench_root]
    if include_test_tasks:
        roots.append(test_task_root)
    return roots


def _task_path(root: Path, suite: str, task_id: str) -> Path:
    return root / suite / task_id


def _task_root_label(root: Path, repo_root: Path) -> str:
    try:
        return root.relative_to(repo_root).as_posix() + "/"
    except ValueError:
        return str(root)


def _task_root_map(bench_root: Path, test_task_root: Path) -> dict[str, Path]:
    return {
        "bench": bench_root,
        "benchmark": bench_root,
        "test": test_task_root,
        "test-task": test_task_root,
        "test-tasks": test_task_root,
    }


def _parse_task_ref(
    task_ref: str,
    *,
    bench_root: Path,
    test_task_root: Path,
    repo_root: Path,
) -> tuple[Path | None, str, str]:
    raw = task_ref.strip()
    if not raw:
        raise ValueError("Task must be in the form <suite>/<task_id>")

    root: Path | None = None
    body = raw
    if ":" in raw:
        maybe_root, maybe_body = raw.split(":", 1)
        mapped = _task_root_map(bench_root, test_task_root).get(
            maybe_root.strip().lower()
        )
        if mapped is not None:
            root = mapped
            body = maybe_body.strip()

    if "/" not in body:
        raise ValueError("Task must be in the form <suite>/<task_id>")
    suite, task_id = body.split("/", 1)
    suite = suite.strip()
    task_id = task_id.strip()
    if not suite or not task_id:
        raise ValueError("Task must be in the form <suite>/<task_id>")
    return root, suite, task_id


def _task_meta_bool(task: Task, key: str) -> bool:
    if key not in task.meta:
        return False
    val = task.meta.get(key)
    if isinstance(val, bool):
        return val
    raise ValueError(f"task.toml {key} must be a boolean")


def _suite_shared_workspace_dir(task: Task) -> Path:
    return task.path.parent / "shared" / "workspace"


def _suite_shared_eval_dir(task: Task) -> Path:
    return task.path.parent / "shared" / "eval"


def _load_task(
    suite: str,
    task_id: str,
    *,
    root: Path | None = None,
    bench_root: Path,
    test_task_root: Path,
    repo_root: Path,
) -> Task:
    task_path: Path | None = None
    searched: list[str] = []
    roots = (
        [root]
        if root is not None
        else _task_roots(
            include_test_tasks=True,
            bench_root=bench_root,
            test_task_root=test_task_root,
        )
    )
    matches: list[Path] = []
    for candidate_root in roots:
        searched.append(_task_root_label(candidate_root, repo_root))
        candidate = _task_path(candidate_root, suite, task_id)
        if candidate.exists():
            matches.append(candidate)

    if len(matches) > 1:
        locations = ", ".join(str(p) for p in matches)
        raise FileNotFoundError(
            f"Task reference is ambiguous: {suite}/{task_id} (matches: {locations}). "
            "Use bench:<suite>/<task_id> or test:<suite>/<task_id>."
        )

    if matches:
        task_path = matches[0]

    if task_path is None:
        roots_text = ", ".join(searched)
        raise FileNotFoundError(
            f"Task not found: {suite}/{task_id} (searched: {roots_text})"
        )

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


def _iter_tasks(
    *,
    include_test_tasks: bool = False,
    bench_root: Path,
    test_task_root: Path,
) -> Iterator[tuple[str, str]]:
    for root in _task_roots(
        include_test_tasks=include_test_tasks,
        bench_root=bench_root,
        test_task_root=test_task_root,
    ):
        if not root.exists():
            continue
        for suite_dir in sorted([p for p in root.iterdir() if p.is_dir()]):
            for task_dir in sorted([p for p in suite_dir.iterdir() if p.is_dir()]):
                if (task_dir / "spec.md").exists() and (
                    task_dir / "task.toml"
                ).exists():
                    yield (suite_dir.name, task_dir.name)


def _check_task(task: Task) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not task.spec_path.is_file():
        errors.append("spec.md must be a file")
    if not task.task_toml_path.is_file():
        errors.append("task.toml must be a file")
    if not task.workspace_tpl.is_dir():
        errors.append("workspace/ must be a directory")
    if not task.eval_dir.is_dir():
        errors.append("eval/ must be a directory")

    meta = task.meta
    required_keys = ["id", "suite", "language", "time_limit_sec", "eval_cmd"]
    for key in required_keys:
        if key not in meta:
            errors.append(f"task.toml missing required key: {key}")

    if str(meta.get("id", "")).strip() != task.task_id:
        errors.append(
            f"task.toml id must match directory name: expected {task.task_id!r}"
        )

    if str(meta.get("suite", "")).strip() != task.suite:
        errors.append(
            f"task.toml suite must match directory name: expected {task.suite!r}"
        )

    language = str(meta.get("language", "")).strip()
    if language and language not in {"python", "cpp", "fortran"}:
        errors.append("task.toml language must be one of: python, cpp, fortran")

    try:
        time_limit = int(meta.get("time_limit_sec", 0))
        if time_limit <= 0:
            errors.append("task.toml time_limit_sec must be a positive integer")
    except Exception:
        errors.append("task.toml time_limit_sec must be an integer")

    eval_cmd = str(meta.get("eval_cmd", "")).strip()
    if not eval_cmd:
        errors.append("task.toml eval_cmd must be a non-empty string")

    prompt_file = str(meta.get("prompt_file", "")).strip()
    if prompt_file:
        p = task.path / prompt_file
        if not p.exists() or not p.is_file():
            errors.append(f"prompt_file not found: {p}")

    use_shared_workspace = meta.get("use_shared_workspace", False)
    if not isinstance(use_shared_workspace, bool):
        errors.append("task.toml use_shared_workspace must be a boolean")
        use_shared_workspace = False

    use_shared_eval = meta.get("use_shared_eval", False)
    if not isinstance(use_shared_eval, bool):
        errors.append("task.toml use_shared_eval must be a boolean")
        use_shared_eval = False

    if use_shared_workspace:
        shared_workspace = _suite_shared_workspace_dir(task)
        if not shared_workspace.exists() or not shared_workspace.is_dir():
            errors.append(
                "task.toml use_shared_workspace=true but suite shared workspace "
                f"directory is missing: {shared_workspace}"
            )

    if use_shared_eval:
        shared_eval = _suite_shared_eval_dir(task)
        if not shared_eval.exists() or not shared_eval.is_dir():
            errors.append(
                "task.toml use_shared_eval=true but suite shared eval "
                f"directory is missing: {shared_eval}"
            )

    if task.spec_path.is_file():
        spec_text = task.spec_path.read_text(encoding="utf-8").strip()
        if not spec_text:
            errors.append("spec.md must not be empty")
        elif "#" not in spec_text.splitlines()[0]:
            warnings.append("spec.md first line is not a Markdown heading")

    if task.workspace_tpl.is_dir():
        if not any(task.workspace_tpl.iterdir()):
            warnings.append("workspace/ is empty")

    public_tests = task.workspace_tpl / "tests"
    if task.workspace_tpl.is_dir() and (
        not public_tests.exists() or not public_tests.is_dir()
    ):
        warnings.append("workspace/tests/ not found (no public tests)")

    run_sh = task.eval_dir / "run.sh"
    if eval_cmd == "/eval/run.sh" and not run_sh.exists():
        errors.append("eval_cmd points to /eval/run.sh but eval/run.sh is missing")
    if run_sh.exists():
        if not run_sh.is_file():
            errors.append("eval/run.sh exists but is not a file")
        elif not os.access(run_sh, os.X_OK):
            errors.append("eval/run.sh is not executable")

        run_text = run_sh.read_text(encoding="utf-8", errors="replace")
        if not run_text.startswith("#!/usr/bin/env bash"):
            warnings.append("eval/run.sh should start with '#!/usr/bin/env bash'")
        if "result.json" not in run_text:
            warnings.append("eval/run.sh does not appear to write result.json")
        if "/eval_shared" in run_text and not use_shared_eval:
            warnings.append(
                "eval/run.sh references /eval_shared but use_shared_eval is false"
            )

    return errors, warnings
