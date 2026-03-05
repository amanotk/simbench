# Demo Benchmarks

This suite contains benchmark tasks for demonstration purposes. Each task implements a simple RK2 midpoint method in a different language (Python, C++, Fortran).

## Directory layout

- `py/`: Python RK2 midpoint task.
- `cpp/`: C++ RK2 midpoint task.
- `f90/`: Fortran RK2 midpoint task.
- `shared/workspace/data/rk2_cases.json`: shared RK2 reference trajectories.
- `shared/eval/rk2_shared.py`: shared hidden-eval helpers.

## Shared assets

Tasks can opt in to shared assets with:

```toml
use_shared_workspace = true
use_shared_eval = true
```

in their `task.toml`.

With these enabled:

- `shared/workspace/` is copied into `/work` before task workspace overlay.
- `shared/eval/` is mounted at `/eval_shared` during eval.

## Prompt convention

Task prompts should reference the spec path explicitly:

- Spec: `/run/spec.md`
- Workdir: `/work`
