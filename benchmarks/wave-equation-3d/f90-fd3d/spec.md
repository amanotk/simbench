# f90-fd3d

Implement a Fortran finite-difference solver for the 3D wave equation.

Read `description.md` for the governing equation, discretization, boundary
conditions, initial condition, language-specific array mapping, and CLI output
order.

## Task

Edit `src/wave3d_solver.f90` so that both boundary and push kernels are implemented.

For `apply_periodic_ghosts(a, nx, ny, nz)`:

- Periodic ghost cells must be updated in all three dimensions

For `push_wave_3d(u, v, dt, dx, nx, ny, nz)`:

- `u` and `v` are first arguments with `intent(inout)`
- Arrays use Fortran representation with ghost cells: `u(ix, iy, iz)` and `v(ix, iy, iz)`
- If `nx` is given, x-extent is `nx + 2` (same for `ny`, `nz`)
- Uses periodic boundaries in all three dimensions
- Uses `c = 1.0`

Do not change the CLI argument interface in `src/main.f90`.
`main.f90` is responsible for setting initial conditions and calling push for each step.
The executable must print the interior field in memory-layout order (`ix`, `iy`, `iz`),
one value per line.

Shared reference data is in `data/fd3d_cases.json`.

## Standards

- Fortran 90/95 style source (`.f90`)

## Local dev

```bash
pytest -q
```
