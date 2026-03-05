# Scientific Coding Benchmark for LLM Models

This repository provides a framework for scientific coding benchmarks targeting LLM-based agents.

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

Build image:

```bash
python3 scripts/build_image.py
```

Direct Docker build (fallback):

```bash
docker build -t scibench:0.1 -f docker/Dockerfile .
```

List and validate tasks:

```bash
python3 runner/bench.py list
python3 runner/bench.py check
```

Run a task:

```bash
python3 runner/bench.py run sample/opencode.toml demo/py --image scibench:0.1
```

Eval only:

```bash
python3 runner/bench.py eval demo/py --workdir /path/to/workdir --image scibench:0.1
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
