# cpp-hlld-00

Implement the HLLD approximate Riemann solver for 1D ideal MHD in C++.

## Read first

- `/work/basic_equations.md`
- `/work/hlld.md`

## Task

Edit `src/hlld.cpp` so that `hlld_flux_from_primitive(...)` is implemented correctly.

The benchmark uses:

- primitive-state ordering: `[rho, u, v, w, p, By, Bz]`
- flux ordering: `[F_rho, F_mx, F_my, F_mz, F_E, F_By, F_Bz]`
- the test suite includes `Bx = 0` hydro and magnetized degenerate cases
- the test suite also includes a small-`Bx` near-degenerate case, so handle
  `Bx = 0`, small denominators in the starred-state formulas, and related
  square-root/discriminant edge cases carefully

Do not change the public function signatures in `src/hlld.hpp`.

## Implementation hints

- This benchmark follows one specific HLLD implementation convention rather than
  an arbitrary mathematically equivalent variant.
- Small starred-state denominator (`D_alpha`): if `|D_alpha|` is extremely
  small, avoid dividing by it and fall back to unchanged transverse starred
  values (`v* = v`, `w* = w`, `By* = By`, `Bz* = Bz`).
- Small `Bx`: when `Bx = 0`, rotational waves collapse and double-star states
  are unnecessary; do not use double-star states in flux selection in that
  case.
- For this benchmark, a merely small nonzero `|Bx|` is still nondegenerate
  unless another guarded quantity (such as `D_alpha`) becomes numerically
  singular.
- Assume all benchmark inputs are admissible physical states.

## Standards

- C++17

## Local dev

```bash
pytest -q
```
