# cpp-full1d-00

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
- `src/mhd1d.hpp`, `src/mhd1d.cpp`: solver scaffolding to complete

## Functions to complete (in `src/mhd1d.cpp`)

The easiest path is to implement these functions first:

1. `primitive_to_conservative(...)`
2. `conservative_to_primitive(...)`
3. `compute_lr(...)`
4. `compute_rhs(...)`
5. `push_ssp_rk3(...)`
6. `evolve_ssp_rk3(...)`

Recommended implementation order:

1. Reconstruction (`compute_lr`)
2. Flux loop (`compute_flux_hlld` already calls provided HLLD)
3. RHS assembly (`compute_rhs`)
4. One RK3 step (`push_ssp_rk3`)
5. Time loop (`evolve_ssp_rk3`)

## Standards

- C++17
