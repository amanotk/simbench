# Magnetohydrodynamics Shared Assets

This directory holds the shared reference implementations and the canonical
Brio-Wu fixtures used by the magnetohydrodynamics benchmarks.

## Build the shared reference solver

```bash
cmake -S benchmarks/magnetohydrodynamics/shared -B benchmarks/magnetohydrodynamics/shared/build
cmake --build benchmarks/magnetohydrodynamics/shared/build --target mhd1d_reference
```

## Run the shared reference solver

```bash
benchmarks/magnetohydrodynamics/shared/build/bin/mhd1d_reference > benchmarks/magnetohydrodynamics/shared/build/solution.csv
```

## Plot the output

Use the shared plot helper and write the image inside the repo:

```bash
python3 benchmarks/magnetohydrodynamics/shared/workspace/plot_solution.py \
  benchmarks/magnetohydrodynamics/shared/build/solution.csv \
  benchmarks/magnetohydrodynamics/shared/build/solution.png
```

## Run the shared test

```bash
python3 -m pytest -q benchmarks/magnetohydrodynamics/shared/tests/test_reference.py
```
