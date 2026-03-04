# Wave Equation 3D Shared Assets

This directory contains suite-level files reused by multiple
`wave-equation-3d` tasks.

- `workspace/data/fd3d_cases.json`: reference outputs for NumPy FD tasks.
- `workspace/description.md`: common model and discretization notes.
- `eval/wave3d_shared.py`: shared helpers for hidden evaluation tests.

Tasks opt in with:

```toml
use_shared_workspace = true
use_shared_eval = true
```
