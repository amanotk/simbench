# Benchmark Run Flow

This document describes what happens when you run a benchmark task using the
current v0 runner.


## Goals

- Isolation: each run uses a fresh work directory copied from the task template.
- Agentic: the solver can run commands/tests while working.
- Hidden eval: authoritative evaluation is not exposed to the solver.
- Docker-first: toolchains are provided by a single unified Docker image.


## Task Layout (v0)

A task lives under `benchmarks/<suite>/<task_id>/`:

- `spec.md`: problem statement shown to the model
- `task.json`: metadata (e.g. `eval_cmd`, `time_limit_sec`, optional `prompt`)
- `workspace/`: template copied into a per-run workdir (solver edits here)
- `eval/`: evaluation harness (treated as hidden from the solver)
  - `eval/run.sh`: entrypoint; writes `/work/result.json`
  - `eval/tests/`: hidden tests for scoring


## Runner Outputs

Each run creates a directory under `runs/<run_id>/<suite>/<task_id>/`:

- `workdir/`: the isolated workspace copy that is edited and evaluated
- `logs/`: captured stdout/stderr/exit codes
- `spec.md`, `task.json`: copies of the task inputs used for traceability
- `result.json`: the evaluation result (copied from `workdir/result.json`)

`runs/` is gitignored.


## Phase Overview

There are two Docker phases for a benchmark run:

1) Agent phase: model/agent modifies `workdir/` and can execute commands.
2) Eval phase: hidden harness evaluates `workdir/` and writes `result.json`.

The key property is that `benchmarks/.../eval/` is never mounted into the agent
container.


## `bench.py run` (eval-only)

Command:

```bash
python3 runner/bench.py run <suite>/<task_id> --image scibench:0.1
```

What happens:

- A fresh `workdir/` is created by copying `benchmarks/.../workspace/`.
- A Docker container is started from `--image`.
- The runner mounts:
  - `workdir/` to `/work` (read/write)
  - `benchmarks/.../eval/` to `/eval` (read-only)
- The runner executes `eval_cmd` from `task.json` (working directory `/work`).
- The harness writes `/work/result.json` and the runner copies it to `runs/.../result.json`.

This command does not run any model; it only evaluates the template workspace.


## `bench.py opencode` (one-shot agent + eval)

Command:

```bash
python3 runner/bench.py opencode <suite>/<task_id> --image scibench:0.1 -m openai/gpt-5.3-codex
```

What happens:

- A fresh `workdir/` is created.
- The one-shot message is resolved in this order:
  1) CLI `--prompt`
  2) `task.json` `prompt_file`
  3) `task.json` `prompt`
  4) runner default prompt
- The resolved message is written to `runs/.../prompt.txt`.

Agent phase (Docker):

- A Docker container is started from `--image`.
- The runner loads `agents.json` and uses the `opencode` entry to decide what
  host binaries/config files to mount and what command to run.
- The runner always mounts:
  - `workdir/` to `/work` (read/write)
  - `runs/.../` to `/run` (read-only; contains `spec.md` and `prompt.txt`)
- Then the configured `opencode` command is executed inside the container.

Eval phase (Docker):

- A separate Docker container runs the hidden harness (`eval/run.sh`).
- `result.json` is copied into `runs/.../result.json`.


## `bench.py agent` (config-driven agent + eval)

Command:

```bash
python3 runner/bench.py agent <suite>/<task_id> --agent opencode --image scibench:0.1 -m openai/gpt-5.3-codex
```

This is the generic form of the same flow. The runner uses `agents.json` to:

- decide which host binaries/config files to mount into the agent container
- decide what command to run for that agent

To enable additional agents (e.g. `claude-code`, `codex`, `gh-copilot`), edit
`agents.json` and set `enabled: true` for the agent entry.


## Network Modes

`--network on|off` controls the Docker network mode for both the agent and eval
containers:

- `on`: default Docker networking
- `off`: `docker run --network none`


## Secrets / Credentials

The runner never stores credentials in the repo. Credentials must be provided at
runtime from your host environment.

### How credentials get into the agent container

The `bench.py opencode` command supports two mechanisms:

1) OpenCode auth file (recommended for local dev)

- If `~/.local/share/opencode/auth.json` exists on the host, the runner bind-mounts
  it into the container and copies it into:

  - `$HOME/.local/share/opencode/auth.json`

This is created by:

```bash
opencode auth login
```

2) Provider environment variables (useful for CI)

- If the following env vars exist on the host, the runner forwards them into the
  agent container:

  - `OPENAI_API_KEY`
  - `ANTHROPIC_API_KEY`
  - `OPENROUTER_API_KEY`
  - `GITHUB_TOKEN`
  - `AZURE_OPENAI_API_KEY`
  - `AZURE_OPENAI_ENDPOINT`
  - `AZURE_OPENAI_API_VERSION`

The forwarded keys are printed to stderr and recorded in:

- `runs/.../logs/agent.forwarded_env.txt`

With network enabled, assume anything readable in the container can be exfiltrated.
The runner keeps `runs/` free of credentials by design (do not write secrets into
`workdir/` and do not print secrets into logs).


## Result Format (v0)

The eval harness writes `/work/result.json`.

Minimum fields:

```json
{ "status": "passed|failed", "score": 0.0 }
```

Optional `metrics` may be added for timings, accuracy, etc.
