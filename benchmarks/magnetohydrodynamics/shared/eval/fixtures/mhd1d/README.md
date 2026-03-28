# mhd1d hidden fixtures

This directory will store the hidden reference fixtures for
`cpp-full-solver1d`.

## Contents

- One or more CSV fixture files with the schema `x,rho,u,v,w,p,by,bz`
- Fixture metadata that records the comparison tolerances `abs_l1` and
  `abs_linf`
- Regeneration notes for maintainer use when updating the hidden reference

CSV fixture headers intentionally stay lowercase for the magnetic fields:
`by` and `bz`. That naming matches the on-disk schema, while the code-level
state and discussion in solver docs may still use `By` and `Bz`.

## Scoring contract

- Scored variables: `rho`, `u`, `p`, `by`
- Window: interior cells only, excluding two edge-adjacent cells per side
- Reference comparisons use the fixture-stored `abs_l1` and `abs_linf`
  tolerances

## Regeneration expectations

Fixtures must be regenerated from the hidden reference pipeline whenever the
benchmark contract changes. Regeneration must preserve the CSV schema, the
interior-cell window, and the stored tolerances unless the suite maintainers
explicitly revise the contract.
