# cpp-fd3d

Implement a C++ finite-difference solver for the 3D wave equation.

Read `description.md` for the governing equation, discretization, boundary
conditions, initial condition, language-specific array mapping, and CLI output
order.

## Task

Edit `src/wave3d.cpp` so that `simulate_wave_3d(dt, dx, nx, ny, nz, n_steps)`:

- Returns storage representing `u(iz, iy, ix)`
- Uses `c = 1.0`
- Uses periodic boundaries in all three dimensions
- Uses the initial condition defined in `description.md`
- Advances for `n_steps` using the scheme in `description.md`

Do not change the CLI argument interface in `src/main.cpp`.
The executable must print the interior field in physical order (`ix`, `iy`, `iz`),
one value per line.

Shared reference data is in `data/fd3d_cases.json`.

## Standards

- C++17
- Use `std::mdspan` with default layout (`layout_right`)

## Local dev

```bash
pytest -q
```
