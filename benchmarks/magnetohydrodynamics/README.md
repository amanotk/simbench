# Magnetohydrodynamics Benchmarks

This suite contains benchmark tasks for ideal magnetohydrodynamics solvers.

## Directory layout

- `shared/workspace/basic_equations.md`: suite-wide notation and flux conventions.
- `shared/workspace/hlld.md`: HLLD algorithm notes for solver tasks.
- `cpp-hlld/`: C++ HLLD approximate Riemann solver task.

## Notes

- Shared workspace files are visible to the agent during benchmark runs.
- Keep maintainer-only derivations, generators, and hidden fixtures outside the
  shared workspace.

## Reference credit

- The hidden HLLD reference implementation is adapted closely from  
  `https://github.com/chiba-aplab/cansplus`
