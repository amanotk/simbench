# Shared eval assets

This directory holds suite-wide hidden-eval documentation and helpers for
`cpp-full-solver1d`.

## Hidden reference lifecycle

The full-solver task uses a shared hidden-eval contract anchored by these
paths:

- `benchmarks/magnetohydrodynamics/shared/eval/mhd1d_reference.py`
- `benchmarks/magnetohydrodynamics/shared/eval/mhd1d_shared.py`
- `benchmarks/magnetohydrodynamics/shared/eval/fixtures/mhd1d/`

`mhd1d_reference.py` owns the hidden reference generation and comparison
entry points. `mhd1d_shared.py` provides the shared geometry, CSV parsing,
and score-window helpers used by both the task evaluator and the maintainer
regeneration workflow. Fixture files under `fixtures/mhd1d/` store the
reference outputs and comparison metadata needed to keep scoring deterministic.

## Fixture contract

- CSV schema: `x,rho,u,v,w,p,by,bz`
- Scored variables: `rho`, `u`, `p`, `by`
- CSV headers use lowercase `by` and `bz`; the surrounding solver code and
  notation may still refer to the magnetic components as `By` and `Bz`.
- Comparison window: interior cells only, excluding two edge-adjacent cells on
  each side
- Stored tolerances: fixture metadata records `abs_l1` and `abs_linf`
- Regeneration: fixtures are regenerated from the hidden reference pipeline and
  must preserve the schema, windowing rule, and tolerances above unless the
  benchmark contract is intentionally revised

## Files

### `mhd1d_reference.py`

Maintainer-only hidden reference implementation. Provides:

- **Primitive/conservative conversion**: `primitive_to_conservative()`, `conservative_to_primitive()`
- **Cell geometry**: `cell_centers()`, `brio_wu_primitive_profile()`, `brio_wu_conservative_profile()`
- **Time evolution**: `evolve_brio_wu_reference_profile()`, `evolve_ssp_rk3_fixed_dt()`
- **Reconstruction**: `mc2_slopes()`, `reconstruct_mc2_interfaces()`
- **HLLD flux**: `hlld_flux_from_primitive()`, `hlld_flux_from_conservative()`
- **RHS computation**: `compute_semidiscrete_rhs()`, `brio_wu_semidiscrete_rhs()`
- **Fixture generation**: `write_brio_wu_reference_fixtures()`

### `mhd1d_shared.py`

Shared helpers for CSV loading and comparison:

- **`load_mhd1d_csv_profile(csv_path)`**: Load and validate a CSV profile
- **`load_mhd1d_fixture(fixture_path)`**: Load fixture metadata and reference CSV
- **`compare_mhd1d_csv_against_fixture(solver_csv_path, fixture)`**: Compare solver output against fixture
- **`interior_cell_window_bounds(row_count, exclude_edge_adjacents_per_side)`**: Compute comparison window

### `fixtures/mhd1d/`

- **`brio_wu_reference.csv`**: Reference solution for the canonical Brio-Wu problem (400 cells, `t_final=0.1`)
- **`brio_wu_fixture.json`**: Metadata including tolerances, schema, and scored variables

## Regenerating fixtures

To regenerate the reference fixtures (maintainer only):

```python
from mhd1d_reference import write_brio_wu_reference_fixtures
from pathlib import Path

output_dir = Path("benchmarks/magnetohydrodynamics/shared/eval/fixtures/mhd1d")
write_brio_wu_reference_fixtures(output_dir)
```

This writes both the reference CSV and the fixture JSON with updated tolerances.
