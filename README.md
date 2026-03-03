# Scientific Coding Benchmark for LLM Models

This repo provides an agentic coding benchmark for scientific tasks.

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

- `opencode`
- `claude`
- `codex`
- `copilot`

## Quick Start

Build image:

```bash
docker build -t scibench:0.1 -f docker/Dockerfile .
```

List and validate tasks:

```bash
python3 runner/bench.py list
python3 runner/bench.py check
```

Run a task (explicit `run` subcommand):

```bash
python3 runner/bench.py run sample/opencode.toml demo/py-rk2-001 --image scibench:0.1
```

Eval only:

```bash
python3 runner/bench.py eval demo/py-rk2-001 --workdir /path/to/workdir --image scibench:0.1
```

## Repo Layout

- `benchmarks/<suite>/<task_id>/spec.md`: task statement
- `benchmarks/<suite>/<task_id>/task.toml`: task metadata
- `benchmarks/<suite>/<task_id>/workspace/`: template workspace
- `benchmarks/<suite>/<task_id>/eval/`: hidden evaluator
- `runner/bench.py`: runner CLI
- `agents_default.toml`: default agent config
- `sample/*.toml`: sample per-agent overrides

## Docs

- `docs/task-development.md`: task-author quickstart
- `docs/task-reference.md`: task format and contracts
- `docs/run-flow.md`: runtime and artifact flow
