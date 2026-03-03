# py-rk2-001

Implement a simple second-order Runge-Kutta (midpoint) ODE solver in Python.

## Task

Edit `src/rk2.py` so that `solve_rk2_midpoint(rhs, y0, t0, h, n_steps)`:

- Accepts `rhs` as a function with signature `rhs(t, y)`
- Returns `n_steps + 1` values (including the initial value)
- Uses the midpoint RK2 update:
  - `k1 = f(t_n, y_n)`
  - `k2 = f(t_n + h/2, y_n + h*k1/2)`
  - `y_{n+1} = y_n + h*k2`

Shared reference cases are available at `data/rk2_cases.json`.

## Standards

- Python 3.10+

## Local dev

Run public tests:

```bash
pytest -q
```
