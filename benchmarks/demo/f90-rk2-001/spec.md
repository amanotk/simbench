# f90-rk2-001

Implement a simple second-order Runge-Kutta (midpoint) ODE solver in Fortran.

## Task

Edit `src/rk2_solver.f90` so that `solve_rk2_midpoint(...)`:

- Accepts `rhs` as a function argument with an explicit interface
- Writes `n_steps + 1` trajectory values (including the initial value)
- Uses midpoint RK2:
  - `k1 = f(t_n, y_n)`
  - `k2 = f(t_n + h/2, y_n + h*k1/2)`
  - `y_{n+1} = y_n + h*k2`

Do not change the command-line interface in `src/main.f90`.
`main.f90` maps `rhs_name` to a function and passes it into the solver.

Shared reference data is available at `data/rk2_cases.json`.

## Standards

- Fortran 90/95 style source (`.f90`)

## Local dev

```bash
pytest -q
```
