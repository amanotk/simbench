# Simulation Coding Benchmark for LLM Agents

This repository provides a framework for simulation coding benchmarks targeting LLM agents.

## Requirements

- Python 3.10+
- Docker
- `uv` for host-side tooling (recommended)

Install host dev tools:

```bash
uv sync --extra dev
```

Notes:
- Runner supports Python 3.10+.
- For Python <3.11, `tomli` is installed from dev extras and used as TOML parser fallback.

## Supported Agents

Configured in `agents_default.toml` (with per-agent overrides under `sample/*.toml`):

- OpenCode (`opencode`)
- Claude Code (`claude`)
- Codex (`codex`)
- Github Copilot (`copilot`)

## Available Benchmarks
- Demo benchmark for Runge-Kutta 2 (RK2) midpoint method.
- 3D wave equation solver with finite difference method.

## Quick Start

By default, pull the published GHCR toolchain image for local use. This repo
publishes `ghcr.io/amanotk/simbench:develop` for the shared `develop`
toolchain. Build the image locally only if you need a custom toolchain or you
have changed `docker/Dockerfile` or `scripts/build_image.py`.

Published toolchain image:

```bash
docker pull ghcr.io/amanotk/simbench:develop
docker tag ghcr.io/amanotk/simbench:develop simbench:0.1
```

If the package is not publicly accessible to you, authenticate first:

```bash
docker login ghcr.io
```

Build locally only if needed:

```bash
python3 scripts/build_image.py
```

Direct Docker build (fallback):

```bash
docker build -t simbench:0.1 -f docker/Dockerfile .
```

List and validate tasks:

```bash
python3 runner/bench.py list
python3 runner/bench.py check
```

Run a task:

```bash
python3 runner/bench.py run sample/opencode.toml demo/py --image simbench:0.1
```

Run the tiny OpenCode smoke task:

```bash
python3 runner/bench.py run sample/opencode-smoke.toml smoke/py --image simbench:0.1
```

Runner smoke tests:

- `python3 -m unittest -q tests.test_runner_bench.TestOpenCodeSmoke`
- Set `SIMBENCH_SKIP_OPENCODE_SMOKE=1` to skip the live OpenCode smoke run.
- CI runs the live OpenCode smoke by default.
- CI pulls `ghcr.io/amanotk/simbench:<head-branch>` for PRs when available, falls back to `ghcr.io/amanotk/simbench:develop`, and otherwise builds locally.

Eval only:

```bash
python3 runner/bench.py eval demo/py --workdir /path/to/workdir --image simbench:0.1
```

## Repository Layout

- `benchmarks/<suite>`: benchmark suites
- `docs/`: documentation
- `runner/bench.py`: runner CLI
- `agents_default.toml`: default agent config
- `sample/*.toml`: sample per-agent overrides

## Documentation

- `docs/development.md`: developer workflow, branching, and CI policy
- `docs/toolchain.md`: default Docker toolchain and preinstalled libraries
- `docs/task-development.md`: task-author quickstart
- `docs/task-reference.md`: task format and contracts
- `docs/run-flow.md`: runtime and artifact flow
