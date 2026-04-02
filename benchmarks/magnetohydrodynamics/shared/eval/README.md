# Shared eval assets

This directory holds suite-wide hidden-eval documentation for
the full 1D MHD variants (starting with `cpp-full1d-00`).

## Hidden reference lifecycle

The full-solver task uses a shared hidden-eval contract anchored by these
paths:

- `benchmarks/magnetohydrodynamics/shared/eval/fixtures/mhd1d/`

Fixture files under `fixtures/mhd1d/` store the reference outputs needed to
keep scoring deterministic.

## Fixture contract

- CSV schema: `x,rho,u,v,w,p,by,bz`
- Scored variables: `rho`, `u`, `p`, `by`
- CSV headers use lowercase `by` and `bz`; the surrounding solver code and
  notation may still refer to the magnetic components as `By` and `Bz`.
- Comparison window: interior cells only, excluding two edge-adjacent cells on
  each side
- Regeneration: fixtures are regenerated from the hidden reference pipeline and
  must preserve the schema and windowing rule above unless the benchmark
  contract is intentionally revised

## Files

### `fixtures/mhd1d/`

- **`brio_wu_reference.csv`**: Reference solution for the canonical Brio-Wu problem (200 cells, `t_final=0.1`)

## Regenerating fixtures

To regenerate the reference CSV (maintainer only), run the shared reference
binary with `200` and write its output to
`benchmarks/magnetohydrodynamics/shared/eval/fixtures/mhd1d/brio_wu_reference.csv`.
