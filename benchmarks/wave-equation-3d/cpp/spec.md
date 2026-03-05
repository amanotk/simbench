# cpp

Implement a C++ finite-difference solver for the 3D wave equation.

Read `description.md` for the governing equation, discretization, boundary
conditions, initial condition, language-specific array mapping, and CLI output
order.

## Task

Edit `src/wave3d.cpp` so that both boundary and push kernels are implemented.

For `apply_periodic_ghosts(a, nx, ny, nz)`:

- Periodic ghost cells must be updated in all three dimensions

For `push_wave_3d(u, v, dt, dx, nx, ny, nz)`:

- `u` and `v` are the first arguments and are updated in place
- Storage represents `u(iz, iy, ix)` / `v(iz, iy, ix)` with ghost cells
- If `nx` is given, the x-extent of each array is `nx + 2` (same rule for `ny`, `nz`)
- Uses periodic boundaries in all three dimensions
- Uses `c = 1.0`

Do not change the CLI argument interface in `src/main.cpp`.
`main.cpp` is responsible for setting initial conditions and calling push for each step.
The executable must print the interior field in memory-layout order (`iz`, `iy`, `ix`),
one value per line.

Shared reference data is in `data/fd3d_cases.json`.

## Standards

- C++17
- Use `std::mdspan` with default layout (`layout_right`)

## Local dev

```bash
pytest -q
```
