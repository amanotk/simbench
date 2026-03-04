# demo suite

This suite contains compact reference tasks used to validate runner behavior
and baseline agent workflows.

## Directory layout

- `py-rk2-001/`: Python RK2 midpoint task.
- `cpp-rk2-001/`: C++ RK2 midpoint task.
- `f90-rk2-001/`: Fortran RK2 midpoint task.
- `shared/workspace/data/rk2_cases.json`: shared RK2 reference trajectories.
- `shared/eval/rk2_shared.py`: shared hidden-eval helpers.

## Shared assets behavior

Tasks can opt in with:

```toml
use_shared_workspace = true
use_shared_eval = true
```

With these enabled:

- `shared/workspace/` is copied into `/work` before task workspace overlay.
- `shared/eval/` is mounted at `/eval_shared` during eval.

## Prompt convention

Task prompts should reference the spec path explicitly:

- Spec: `/run/spec.md`
- Workdir: `/work`
