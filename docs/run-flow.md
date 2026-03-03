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
- `task.toml`: metadata (e.g. `eval_cmd`, `time_limit_sec`, optional `prompt`)
- `workspace/`: template copied into a per-run workdir (solver edits here)
- `eval/`: evaluation harness (treated as hidden from the solver)
  - `eval/run.sh`: entrypoint; writes `/work/result.json`
  - `eval/tests/`: hidden tests for scoring


## Runner Outputs

Each run creates a directory under `runs/<run_id>/<suite>/<task_id>/`:

- `workdir/`: the isolated workspace copy that is edited and evaluated
- `logs/`: captured stdout/stderr/exit codes
- `logs/agent.docker_cmd.txt` or `logs/agent.host_cmd.txt`: the agent command line
- `logs/eval.docker_cmd.txt`: the eval command line
- `spec.md`, `task.toml`: copies of the task inputs used for traceability
- `result.json`: the evaluation result (copied from `workdir/result.json`)

`runs/` is gitignored.


## Phase Overview

There are two phases for a benchmark run:

1) Agent phase: model/agent modifies `workdir/` and can execute commands.
2) Eval phase: hidden harness evaluates `workdir/` and writes `result.json`.

The agent phase may run in Docker or on the host depending on the selected
agents TOML (`mode = "docker"` or `"host"`).

The key property is that `benchmarks/.../eval/` is never mounted into the agent
container.


## `bench.py run` (agent solve + eval)

Command:

```bash
python3 runner/bench.py run sample/opencode.toml <suite>/<task_id> --image scibench:0.1
```

What happens:

- A fresh `workdir/` is created by copying `benchmarks/.../workspace/`.
- The runner loads and merges agent settings from:
  - positional single-agent override TOML, and
  - `agents_default.toml`.
- Agent phase runs first (Docker or host mode according to merged config).
- Eval phase then runs in Docker using hidden harness mounted at `/eval`.
- The harness writes `/work/result.json` and the runner copies it to `runs/.../result.json`.


The runner uses the selected TOML to:

- decide which optional host config files to mount into the agent container
- decide what command to run for that agent
- choose `model`

Optional model tuning can be passed through agent TOML `model_options`.
The runner exposes these to agent commands as:

- `BENCH_MODEL_OPTIONS_JSON` (JSON)
- `$BENCH_MODEL_OPTIONS_ARGS` placeholder in agent `cmd` (runner-injected,
  shell-escaped CLI flags)

To run different agents, prepare different TOML files and pass one as the first
positional argument.

Agents can run in two modes:

- `mode: "docker"` (default): runner executes agent CLIs in the image and can mount optional host config files
- `mode: "host"`: runner executes the agent on the host (still evaluates in Docker)


## `bench.py eval` (eval-only)

Command:

```bash
python3 runner/bench.py eval <suite>/<task_id> --workdir /path/to/workdir --image scibench:0.1
```

What happens:

- No agent is run.
- The runner evaluates the provided `--workdir` using hidden harness for task.
- Results and logs are still written to a fresh run directory.


## Network Modes

`--network on|off` controls the Docker network mode for both the agent and eval
containers:

- `on`: default Docker networking
- `off`: `docker run --network none`


## Secrets / Credentials

The runner never stores credentials in the repo. Credentials must be provided at
runtime from your host environment.

### How credentials get into the agent container

For the sample OpenCode config (`sample/opencode.toml`), credential handling uses:

1) OpenCode auth file (recommended for local dev)

- If `~/.local/share/opencode/auth.json` exists on the host, the runner bind-mounts
  it into the container and copies it into:

  - `$HOME/.local/share/opencode/auth.json`

This is created by:

```bash
opencode auth login
```

OpenCode config file (optional):

- If `~/.config/opencode/opencode.json` exists, it is mounted into the agent
  container and `OPENCODE_CONFIG` points to it.
- Otherwise, if `~/.config/opencode/opencode.jsonc` exists, it is mounted and
  `OPENCODE_CONFIG` points to that file.

Other agent local files (sample defaults):

- Claude: if `~/.claude/settings.json` exists, it is mounted and copied to
  `$HOME/.claude/settings.json` inside the agent container.
- Codex: if `~/.codex/auth.json` exists, it is mounted and copied to
  `$HOME/.codex/auth.json` inside the agent container.
- Copilot: if `~/.copilot/config.json` exists, it is mounted and copied to
  `$HOME/.copilot/config.json` inside the agent container.

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

Runner-added timing metrics:

- `agent_inner_sec`: agent command runtime inside the container (excludes Docker startup)
- `eval_inner_sec`: eval command runtime inside the container (excludes Docker startup)

The runner prints a compact terminal summary after evaluation:

- `status`
- `score`
- optional `metrics`
- `run_dir`


## Verbose Mode

Pass `--verbose` to print internal runner actions (run paths, resolved commands)
to stderr:

```bash
python3 runner/bench.py --verbose run sample/opencode.toml <suite>/<task_id>
```

Verbose mode also streams full process output in real time for both phases,
with phase+stream prefixes:

- `[agent:<name>] stdout: ...` and `[agent:<name>] stderr: ...`
- `[eval] stdout: ...` and `[eval] stderr: ...`

Verbose logs are grouped into sections to improve readability:

- `RUN SETUP`
- `AGENT PHASE`
- `EVAL PHASE`
