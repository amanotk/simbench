# Toolchain Reference

This document describes what is available by default in the benchmark Docker
image (`scibench:0.1`).

Build the image with:

```bash
python3 scripts/build_image.py
```

## Core Build Tools

- `g++`, `gfortran`
- `make`, `cmake`, `ninja`, `pkg-config`
- `clang-format`

## Numeric and HPC Libraries

- FFT: `libfftw3-dev`
- BLAS/LAPACK: `libopenblas-dev`, `liblapack-dev`
- MPI: `openmpi-bin`, `libopenmpi-dev`

## C++ Utility Libraries

- CLI parsing: `cxxopts` (`libcxxopts-dev`)
- Header-only math/array libs installed under `/usr/local/include`:
  - `experimental/mdspan` (ref: `mdspan-0.6.0`)
  - `xtl` (ref: `0.8.2`)
  - `xsimd` (ref: `14.0.0`)
  - `xtensor` (ref: `0.27.1`)

## Fortran Utility Libraries

FLAP is installed from release `v1.2.16` with dependencies FACE and PENF.
FACE/PENF are pinned to the exact revisions used by FLAP's `fpm.toml` for
deterministic builds.

- Modules/includes:
  - `/usr/local/include/FLAP`
  - `/usr/local/include/FACE`
  - `/usr/local/include/PENF`
- Libraries:
  - `/usr/local/lib/libFLAP.*`
  - `/usr/local/lib/libFACE.*`
  - `/usr/local/lib/libPENF.*`

Typical compile/link flags:

```bash
gfortran \
  -I/usr/local/include/FLAP -I/usr/local/include/FACE -I/usr/local/include/PENF \
  your_program.f90 \
  -L/usr/local/lib -lFLAP -lFACE -lPENF
```

## Python Packages

- `numpy`
- `scipy`
- `matplotlib`
- `pytest`

## Common Utilities

- `git`, `curl`, `wget`, `jq`, `time`, `unzip`, `zip`

## Notes

- The build script keeps version pins in one place (`scripts/build_image.py`).
- Use task-local dependencies only when a task explicitly evaluates setup/package
  work; otherwise prefer preinstalled toolchain features for reproducibility.
