# Task Development Guide

This guide is for benchmark authors who want to create new tasks.


## 10-minute quickstart

1) Create the task directory:

```bash
mkdir -p benchmarks/<suite>/<task_id>/{workspace,eval}
```

2) Add required files:

- `benchmarks/<suite>/<task_id>/spec.md`
- `benchmarks/<suite>/<task_id>/task.toml`
- `benchmarks/<suite>/<task_id>/workspace/` (template project)
- `benchmarks/<suite>/<task_id>/eval/run.sh` (hidden evaluator)

3) Validate scaffolding:

```bash
python3 runner/bench.py check <suite>/<task_id>
```

4) Iterate locally:

```bash
python3 runner/bench.py shell --image scibench:0.1 sample/opencode.toml <suite>/<task_id>
python3 runner/bench.py run sample/opencode.toml <suite>/<task_id> --image scibench:0.1
```


## Minimal templates

`spec.md`:

```md
# <Task title>

Implement <function/module> in `workspace/...`.
Constraints:
- <constraint 1>
- <constraint 2>
```

`task.toml`:

```toml
id = "<task_id>"
suite = "<suite>"
language = "python"
time_limit_sec = 120
eval_cmd = "/eval/run.sh"
prompt = "Read /run/spec.md and solve the task in /work."
use_shared_workspace = false
use_shared_eval = false
```

Optional suite-level shared directories (opt-in per task):

- `benchmarks/<suite>/shared/workspace/` (copied into `/work` before task workspace)
- `benchmarks/<suite>/shared/eval/` (mounted read-only at `/eval_shared` during eval)

Enable them in task `task.toml`:

```toml
use_shared_workspace = true
use_shared_eval = true
```

`eval/run.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

cd /work
pytest -q /eval/tests

python3 - <<'PY'
import json
print(json.dumps({"status": "passed", "score": 1.0}))
PY > /work/result.json
```

Make evaluator executable:

```bash
chmod +x benchmarks/<suite>/<task_id>/eval/run.sh
```


## Public tests vs hidden eval

- Put developer-facing tests in `workspace/tests/` so agents can run them.
- Put authoritative checks in `eval/tests/` and call them from `eval/run.sh`.
- The agent container gets `workspace` at `/work`, but not `/eval`.


## Python array convention

For Python numerical tasks, use `numpy.ndarray` as the solver state type.
Do not use nested Python lists for numerical state in task APIs or tests.

If a task needs this convention, state it explicitly in `spec.md`.

For C++ numerical tasks, prefer `std::mdspan` with default C-style layout
(`layout_right`) for multidimensional state unless the task says otherwise.


## Authoring workflow

Use this loop while building tasks:

1) Write scaffold (`spec.md`, `task.toml`, `workspace`, `eval`).
2) Run `python3 runner/bench.py check <suite>/<task_id>`.
3) Use `bench.py shell` to test the workspace quickly.
4) Run `bench.py run` to verify end-to-end scoring.
5) Tune hidden tests for robustness and determinism.


## Checklist before publishing

- `spec.md` is unambiguous and self-contained.
- `task.toml` has correct `id`, `suite`, `language`, `time_limit_sec`, `eval_cmd`.
- `eval/run.sh` is executable and writes `/work/result.json`.
- Hidden eval is deterministic (fixed seeds, stable tolerances, pinned threads).
- `python3 runner/bench.py check <suite>/<task_id>` passes.


## Related docs

- `docs/task-reference.md` for field-level contracts.
- `docs/run-flow.md` for runner internals and artifact layout.
