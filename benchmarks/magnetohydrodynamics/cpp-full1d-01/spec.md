# cpp-full1d-01

Implement a 1D ideal-MHD solver CLI in C++.

## Read first

- `/work/basic_equations.md`
- `/work/hlld.md`

## Task

The command-line entrypoint and the HLLD Riemann solver are already provided.
The CLI accepts an integer `nx` argument for the number of grid points, performs the Brio-Wu Riemann problem, and writes the solution to stdout in CSV format.
Your main task is to complete the solver implementation in `src/mhd1d.cpp`.

The CLI output must match the provided golden CSV for `nx=100` within numeric tolerance (`1.0e-12`).

## How to test

Run the public checks from the workspace:

```bash
python3 -m pytest -q tests/test_public.py
```

## Local dev

```bash
pytest -q
```

To build manually:

```bash
cmake -S . -B build
cmake --build build
./build/bin/cpp_full_solver1d
```

## Numerical Algorithm

- Riemann solver: HLLD
- Primitive variables reconstruction: piecewise linear with MC2 slope limiter
- Time integration: SSP-RK3
- Boundary condition: symmetric (zero-gradient)

## Files

- `src/main.cpp`: complete CLI (already done)
- `src/hlld.hpp`, `src/hlld.cpp`: complete HLLD implementation (already done)
- `src/mhd1d.hpp`: provides the workspace data structure and solver entrypoint declaration
- `src/mhd1d.cpp`: contains only an empty `evolve_ssp_rk3(...)` implementation to complete

## Functions to complete (in `src/mhd1d.cpp`)

- `evolve_ssp_rk3(SolverWorkspace& workspace, double dt, double t_final)`

All other helper functions and internal organization are up to you.

## Standards

- C++17
