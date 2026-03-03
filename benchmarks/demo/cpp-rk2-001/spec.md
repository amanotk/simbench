# cpp-rk2-001

Implement a simple second-order Runge-Kutta (midpoint) ODE solver in C++.

## Task

Edit `src/rk2.cpp` so that `solve_rk2_midpoint(...)`:

- Accepts `rhs` as a callable (`std::function<double(double, double)>`)
- Returns `n_steps + 1` values including the initial state
- Uses midpoint RK2:
  - `k1 = f(t_n, y_n)`
  - `k2 = f(t_n + h/2, y_n + h*k1/2)`
  - `y_{n+1} = y_n + h*k2`

Do not modify the executable interface in `src/main.cpp`.
`main.cpp` converts `rhs_name` to a callable and passes it to the solver.

Shared reference data is available at `data/rk2_cases.json`.

## Standards

- C++17

## Local dev

```bash
pytest -q
```
