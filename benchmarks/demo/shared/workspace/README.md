# Demo Shared Workspace Assets

This directory contains suite-level files reused by multiple `demo` tasks.

- `data/rk2_cases.json`: precomputed RK2 trajectories for common ODE cases.

Tasks opt in with:

```toml
use_shared_workspace = true
```
