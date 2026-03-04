# f90-fd3d

Implement a Fortran finite-difference solver for the 3D wave equation.

Read `description.md` for the governing equation, discretization, boundary
conditions, initial condition, language-specific array mapping, and CLI output
order.

## Task

Edit `src/wave3d_solver.f90` so that `simulate_wave_3d(dt, dx, nx, ny, nz, n_steps, u_out)`:

- Writes `u_out(ix, iy, iz)` in Fortran representation
- Uses `c = 1.0`
- Uses periodic boundaries in all three dimensions
- Uses the initial condition defined in `description.md`
- Advances for `n_steps` using the scheme in `description.md`

Do not change the CLI argument interface in `src/main.f90`.
The executable must print the interior field in physical order (`ix`, `iy`, `iz`),
one value per line.

Shared reference data is in `data/fd3d_cases.json`.

## Standards

- Fortran 90/95 style source (`.f90`)

## Local dev

```bash
pytest -q
```
