# wave-equation-3d suite

This suite contains benchmark tasks for 3D wave-equation solvers.

## Directory layout

- `py-fd3d/`: Python task (`spec.md`, `task.toml`, `workspace/`, `eval/`).
- `shared/workspace/description.md`: shared implementation description for agents.
- `shared/workspace/data/fd3d_cases.json`: shared reference fixture data.
- `shared/eval/wave3d_shared.py`: shared hidden-eval helpers.
- `shared/scripts/wave3d_reference.py`: maintainer reference solver for fixture checks.

## Shared assets behavior

Tasks can opt in to shared files with:

```toml
use_shared_workspace = true
use_shared_eval = true
```

With these enabled:

- `shared/workspace/` is copied into `/work` before task workspace overlay.
- `shared/eval/` is mounted at `/eval_shared` during eval.

## Notes

- `description.md` is intended for agents and task implementation guidance.
- This `README.md` is intended for human maintainers.
