# Task Reference (v0)

This document defines the required task layout and evaluation contract.


## Required layout

Each task must live at:

`benchmarks/<suite>/<task_id>/`

Required paths:

- `spec.md` (file)
- `task.toml` (file)
- `workspace/` (directory)
- `eval/` (directory)

Recommended additional paths:

- `workspace/tests/` (public/dev tests)
- `eval/tests/` (hidden tests)
- `eval/run.sh` (default eval entrypoint)


## `task.toml` schema

Required keys:

- `id` (string): must match `<task_id>` directory name
- `suite` (string): must match `<suite>` directory name
- `language` (string): one of `python`, `cpp`, `fortran`
- `time_limit_sec` (integer): positive timeout per phase
- `eval_cmd` (string): eval command, commonly `/eval/run.sh`

Optional keys:

- `prompt` (string): one-shot prompt for the solver
- `prompt_file` (string): path relative to task root
- `use_shared_workspace` (boolean): if true, copy `benchmarks/<suite>/shared/workspace/` into run workdir before overlaying task `workspace/`
- `use_shared_eval` (boolean): if true, mount `benchmarks/<suite>/shared/eval/` at `/eval_shared` during eval

Example:

```toml
id = "py-rk2-001"
suite = "demo"
language = "python"
time_limit_sec = 120
eval_cmd = "/eval/run.sh"
prompt = "Read the attached spec.md and solve the task."
use_shared_workspace = false
use_shared_eval = false
```


## `eval/run.sh` contract

When used with `eval_cmd = "/eval/run.sh"`:

- file should start with `#!/usr/bin/env bash`
- file should be executable (`chmod +x`)
- workspace is mounted at `/work` (read/write)
- eval harness is mounted at `/eval` (read-only)
- script must write `/work/result.json`
- script should exit `0` after writing result

If `use_shared_eval = true`, suite-level shared eval files are available at
`/eval_shared` in the eval container.


## Result format

Evaluator writes `/work/result.json`.

Minimum shape:

```json
{ "status": "passed|failed", "score": 0.0 }
```

Optional:

- `metrics` object with stable machine-readable keys/values

Runner-appended timing metrics (if available):

- `agent_inner_sec`
- `eval_inner_sec`


## Validation command

Use runner checks while authoring:

```bash
python3 runner/bench.py check
python3 runner/bench.py check <suite>/<task_id>
```

The checker validates required paths, key metadata fields, and common pitfalls
(missing `eval/run.sh`, non-executable evaluator, malformed structure).
