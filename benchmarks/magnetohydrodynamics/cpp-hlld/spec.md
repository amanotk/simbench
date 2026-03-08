# cpp-hlld

Implement the HLLD approximate Riemann solver for 1D ideal MHD in C++.

## Read first

- `/work/basic_equations.md`
- `/work/hlld.md`

## Task

Edit `src/hlld.cpp` so that these functions are implemented correctly:

- `hlld_flux_from_primitive(...)`
- `hlld_flux_from_conservative(...)`

The benchmark uses:

- primitive-state ordering: `[rho, u, v, w, p, By, Bz]`
- conservative-state ordering: `[rho, mx, my, mz, E, By, Bz]`
- flux ordering: `[F_rho, F_mx, F_my, F_mz, F_E, F_By, F_Bz]`
- Lorentz-Heaviside units
- `Bx` passed separately from the state vectors
- the test suite includes `Bx = 0` hydro and magnetized degenerate cases
- the test suite also includes a small-`Bx` near-degenerate case, so handle
  `Bx = 0`, small denominators in the starred-state formulas, and related
  square-root/discriminant edge cases carefully

Do not change the public function signatures in `src/hlld.hpp`.

## Standards

- C++17
- Use `std::array<double, 7>` for the public API

## Local dev

```bash
pytest -q
```
