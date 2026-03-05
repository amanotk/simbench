# py

Implement a NumPy finite-difference solver for the 3D wave equation with
periodic boundary conditions.

Read `description.md` for the governing equation, discretization scheme,
boundary conditions, initial condition, and array conventions used across this
suite.

## Task

Edit `src/wave3d.py` so that both boundary and push kernels are implemented.

For `apply_periodic_ghosts(a, nx, ny, nz)`:
- Periodic ghost cells must be updated in all three dimensions

For `push_wave_3d(u, v, dt, dx, nx, ny, nz)`:

- It accepts state arrays as first arguments and updates them in place
- Uses arrays representing `u(iz, iy, ix)` and `v(iz, iy, ix)`
- Uses a one-cell ghost layer in each direction; if `nx` is given, x-size is `nx + 2`
- Uses periodic boundaries in all three dimensions
- Performs exactly one finite-difference push step with `c = 1.0`

Tests set initial condition and perform the time loop outside this function.

Shared reference data is in `data/fd3d_cases.json`.

## Constraints

- Python 3.10+
- Use NumPy (`numpy.ndarray`) for state arrays
- Do not use nested Python lists for the numerical state

## Local dev

```bash
pytest -q
```
