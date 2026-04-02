# Magnetohydrodynamics Benchmarks

This suite contains benchmark tasks for ideal magnetohydrodynamics solvers.

## Directory layout

- `shared/workspace/basic_equations.md`: suite-wide notation and flux conventions.
- `shared/workspace/hlld.md`: HLLD algorithm notes for solver tasks.
- `cpp-hlld-00/`: default C++ HLLD task with detailed solver guidance in spec.
- `cpp-hlld-01/`: variant C++ HLLD task with reduced guidance but same test intent.
- `cpp-full1d-00/`: easiest C++ full 1D ideal MHD variant (main+HLLD provided, solver scaffolded).
- `cpp-full1d-01/`: reduced-guidance full 1D variant with only `evolve_ssp_rk3(...)` exposed.
- `shared/eval/README.md`: hidden-eval contract for shared MHD scoring assets.
- `shared/eval/mhd1d_shared.py`: shared helpers for CSV loading, score
  windows, and comparison metadata.
- `shared/eval/fixtures/mhd1d/`: hidden fixtures for full 1D variants.

## Notes

- Shared workspace files are visible to the agent during benchmark runs.
- Keep maintainer-only derivations, generators, and hidden fixtures outside the
  shared workspace.
- `cpp-hlld-00` and `cpp-hlld-01` expose only
  `hlld_flux_from_primitive(...)` in the public task API.
- `cpp-hlld-00` and `cpp-hlld-01` keep public/hidden test intent aligned;
  the main difference is prompt detail level.
- `cpp-full1d-00` public tests compare solver CSV output against a golden file
  with numeric tolerance (`1.0e-12`), and hidden tests use `nx=200` against a
  hidden reference CSV with the same numeric policy.
- Full 1D tasks score interior cells and emit CSV with lowercase magnetic-field
  headers (`by`, `bz`).

## Reference credit

- The hidden HLLD reference implementation is adapted closely from  
  `https://github.com/chiba-aplab/cansplus`
