# Scientific Coding Benchmark for LLM Models

This repo hosts an agentic coding benchmark for scientific computing tasks.

Design goals:
- Isolated runs: fresh model session and fresh filesystem per task.
- Agentic: the model can run commands/tests while solving.
- Hidden eval: authoritative evaluation lives outside the agent workspace.

## Layout

- `benchmarks/<suite>/<task_id>/spec.md`: the problem statement shown to the model
- `benchmarks/<suite>/<task_id>/task.toml`: minimal task metadata for the runner
- `benchmarks/<suite>/<task_id>/workspace/`: template workspace copied per run (model edits here)
- `benchmarks/<suite>/<task_id>/eval/`: evaluation harness (not mounted into the agent container)
- `runner/bench.py`: CLI (list/check/prepare/shell/run/eval)
- `agents_default.toml`: default multi-agent settings (opencode/codex/claude/copilot)
- `sample/opencode.toml`: sample single-agent configuration file
- `docker/Dockerfile`: unified image for Python/C++/Fortran tasks
- `runs/`: local run artifacts (gitignored)

## Quick start (local)

Prereqs: Docker installed and `docker` available on PATH.

Build the unified image:

```bash
docker build -t scibench:0.1 -f docker/Dockerfile .
```

List tasks:

```bash
python3 runner/bench.py list
```

Validate task layout/metadata:

```bash
python3 runner/bench.py check
python3 runner/bench.py check demo/py-rk2-001
```

Run full benchmark (agent solve + hidden eval):

```bash
python3 runner/bench.py run sample/opencode.toml demo/py-rk2-001 --image scibench:0.1
```

Shorthand (implicit `run`):

```bash
python3 runner/bench.py sample/opencode.toml demo/py-rk2-001 --image scibench:0.1
```

Prepare an isolated workspace (uses agent config and creates run artifacts):

```bash
python3 runner/bench.py prepare sample/opencode.toml demo/py-rk2-001
```

Open a shell in an isolated workspace:

```bash
python3 runner/bench.py shell --image scibench:0.1 sample/opencode.toml demo/py-rk2-001
```

For shell subcommands with flags, place shell options before `agents task` and
use `--` before command flags (for example, `-- pytest -q`).

Run eval-only on an existing workdir:

```bash
python3 runner/bench.py eval demo/py-rk2-001 --workdir /path/to/workdir --image scibench:0.1
```

Verbose run:

```bash
python3 runner/bench.py --verbose run sample/opencode.toml demo/py-rk2-001 --image scibench:0.1
```

In verbose mode, the runner streams full agent/eval `stdout` and `stderr`
in real time to stderr with phase labels (for example
`[agent:opencode] stdout: ...`, `[eval] stderr: ...`).
It also separates logs into readable sections like `RUN SETUP`,
`AGENT PHASE`, and `EVAL PHASE`.

Model/command/tool settings come from agent TOML. The selected TOML overrides
defaults from `agents_default.toml`.

You can set model-level options in agent TOML via `model_options`.
These are exposed to agent commands as:

- `BENCH_MODEL_OPTIONS_JSON` (JSON object)
- `$BENCH_MODEL_OPTIONS_ARGS` placeholder in `cmd` is replaced by the runner with
  shell-escaped CLI flags (e.g. `--reasoning-effort high`)

Run different agents by selecting their TOML config:

```bash
python3 runner/bench.py run sample/claude.toml demo/py-rk2-001 --image scibench:0.1
python3 runner/bench.py run sample/codex.toml demo/py-rk2-001 --image scibench:0.1
python3 runner/bench.py run sample/copilot.toml demo/py-rk2-001 --image scibench:0.1
```

You usually do not need `--prompt`; the runner uses a default message. You can also
set `prompt` or `prompt_file` in the task's `task.toml`.

For suite-level reuse, tasks can opt in to shared directories in `task.toml`:

- `use_shared_workspace = true` copies `benchmarks/<suite>/shared/workspace/`
  into `/work` before task workspace files are overlaid.
- `use_shared_eval = true` mounts `benchmarks/<suite>/shared/eval/` as
  `/eval_shared` during evaluation.

This runs agent sessions in Docker by mounting:
- the task workdir at `/work`
- the run metadata (including `spec.md`) at `/run` (read-only)
- optional host agent config files as defined in merged config
- for OpenCode, optional host config `~/.config/opencode/opencode.json` or `~/.config/opencode/opencode.jsonc`
- for Claude, optional `~/.claude/settings.json`
- for Codex, optional `~/.codex/auth.json`
- for Copilot, optional `~/.copilot/config.json`

## Notes

- Network is configurable per run (`--network on|off`).
- Use `--result-dir` on `prepare/shell/run/eval` to control artifact location.
- Final console output includes a compact result summary (status, score,
  optional metrics, and run directory).

## Docs

- `docs/task-development.md`: quickstart for creating new tasks
- `docs/task-reference.md`: task format and evaluation contract details
- `docs/run-flow.md`: runtime flow (prepare/run/eval internals)
