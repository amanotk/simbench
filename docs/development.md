# Development Guide

This document is for developers maintaining the benchmark harness and task suite.

## Branching Model

- `main`: stable branch, updated via pull requests
- `develop`: primary integration branch for ongoing work
- `feature/<name>`: short-lived feature branches

Merge flow:

1. `feature/<name>` -> `develop`
2. `develop` -> `main`

## Feature Branch Naming

Use `feature/<name>` where `<name>` is descriptive and does not need to be a task id.

Examples:

- `feature/demo`
- `feature/rk2-suite`
- `feature/runner-check-updates`

For task-focused work, descriptive names are preferred, e.g. `feature/demo-py-rk2`.

## CI Policy

CI should run on both branches and PRs targeting them:

- push: `main`, `develop`
- pull_request target: `main`, `develop`

Current policy for CI jobs:

- Real OpenCode smoke tests run in CI by default.
- Keep the non-agent checks deterministic; treat live smoke as an integration
  check that depends on the published SimBench image and runner environment.

Recommended required checks:

- `python3 -m py_compile runner/bench.py`
- `python3 -m unittest -q discover -s tests -p 'test_runner_*.py'`
- `python3 runner/bench.py check`
- formatting checks for Python/C++/Fortran sources

Optional heavier check:

- `docker build -t simbench:0.1 -f docker/Dockerfile .`
- `python3 scripts/build_image.py`

Toolchain image publishing:

- GitHub Actions publishes `ghcr.io/amanotk/simbench:<branch>` on pushes to
  `develop` and `main`.
- CI pulls the published image for runner tests when the toolchain is unchanged.
- Pull request CI tries the head-branch image first, then `develop`, before
  rebuilding locally.
- If `docker/Dockerfile` or `scripts/build_image.py` changes in a branch, CI
  rebuilds `simbench:0.1` locally instead of pulling a stale registry image.

If a developer cannot pull the package directly, authenticate with
`docker login ghcr.io` before pulling from GHCR.

## Local Developer Workflow

Set up host tooling:

```bash
uv sync --extra dev
```

Run local checks before opening PR:

```bash
python3 -m py_compile runner/bench.py
python3 -m unittest -q discover -s tests -p 'test_runner_*.py'
python3 runner/bench.py check
uvx ruff format runner tests
uvx ruff check --fix runner tests
clang-format -i $(git ls-files "*.cpp" "*.hpp" ':!:benchmarks/common/include/**')
uvx fprettify -r benchmarks/demo/f90/workspace/src/*.f90
```

## Branch Protection Recommendations

Apply branch protection to `main` and `develop`:

- require pull requests before merge
- require required CI checks to pass
- optionally require at least one review
