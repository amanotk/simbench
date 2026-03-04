# py-fd3d

Implement a NumPy finite-difference solver for the 3D wave equation with
periodic boundary conditions.

Read `description.md` for the governing equation, discretization scheme,
boundary conditions, initial condition, and array conventions used across this
suite.

## Task

Edit `src/wave3d.py` so that `simulate_wave_3d(dt, dx, nx, ny, nz, n_steps)`:

- Returns a `numpy.ndarray` of shape `(nx, ny, nz)`
- Uses `c = 1.0`
- Uses periodic boundaries in all three dimensions
- Uses the initial condition defined in `description.md`
- Advances the field for `n_steps` using the scheme in `description.md`

Shared reference data is in `data/fd3d_cases.json`.

## Constraints

- Python 3.10+
- Use NumPy (`numpy.ndarray`) for state arrays
- Do not use nested Python lists for the numerical state

## Local dev

```bash
pytest -q
```
