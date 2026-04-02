# cpp-hlld-01

Implement the HLLD approximate Riemann solver for 1D ideal MHD in C++.

## Read first

- `/work/basic_equations.md`
- `/work/hlld.md`

## Task

Edit `src/hlld.cpp` so that `hlld_flux_from_primitive(...)` is implemented correctly.

The benchmark uses:

- primitive-state ordering: `[rho, u, v, w, p, By, Bz]`
- flux ordering: `[F_rho, F_mx, F_my, F_mz, F_E, F_By, F_Bz]`

Do not change the public function signatures in `src/hlld.hpp`.

## Standards

- C++17

## Local dev

```bash
pytest -q
```
