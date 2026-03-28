# Magnetohydrodynamics Benchmarks

This suite contains benchmark tasks for ideal magnetohydrodynamics solvers.

## Directory layout

- `shared/workspace/basic_equations.md`: suite-wide notation and flux conventions.
- `shared/workspace/hlld.md`: HLLD algorithm notes for solver tasks.
- `cpp-hlld/`: C++ HLLD approximate Riemann solver task.
- `cpp-full-solver1d/`: C++ full 1D ideal MHD solver (Brio-Wu benchmark).
- `shared/eval/README.md`: hidden-eval contract for shared MHD scoring assets.
- `shared/eval/mhd1d_reference.py`: hidden reference generator for the 1D
  full-solver task.
- `shared/eval/mhd1d_shared.py`: shared helpers for CSV loading, score
  windows, and comparison metadata.
- `shared/eval/fixtures/mhd1d/`: hidden fixtures for `cpp-full-solver1d`.

## Notes

- Shared workspace files are visible to the agent during benchmark runs.
- Keep maintainer-only derivations, generators, and hidden fixtures outside the
  shared workspace.
- `cpp-full-solver1d` scores only the interior cells, excluding two
  edge-adjacent cells on each side, against the variables `rho`, `u`, `p`, and
  `by` using fixture-recorded `abs_l1` and `abs_linf` tolerances. CSV fixture
  headers keep the magnetic fields lowercase (`by`, `bz`) even when the code
  and solver notation use `By` and `Bz`.

## Reference credit

- The hidden HLLD reference implementation is adapted closely from  
  `https://github.com/chiba-aplab/cansplus`
