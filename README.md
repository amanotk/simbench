# Scientific Coding Benchmark (LLM)

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
- `runner/bench.py`: CLI (list/prepare/shell/run/eval)
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

Run full benchmark (agent solve + hidden eval):

```bash
python3 runner/bench.py run sample/opencode.toml demo/py-add-001 --image scibench:0.1
```

Shorthand (implicit `run`):

```bash
python3 runner/bench.py sample/opencode.toml demo/py-add-001 --image scibench:0.1
```

Prepare an isolated workspace (uses agent config and creates run artifacts):

```bash
python3 runner/bench.py prepare sample/opencode.toml demo/py-add-001
```

Open a shell in an isolated workspace:

```bash
python3 runner/bench.py shell --image scibench:0.1 sample/opencode.toml demo/py-add-001
```

For shell subcommands with flags, place shell options before `agents task` and
use `--` before command flags (for example, `-- pytest -q`).

Run eval-only on an existing workdir:

```bash
python3 runner/bench.py eval demo/py-add-001 --workdir /path/to/workdir --image scibench:0.1
```

Verbose run:

```bash
python3 runner/bench.py --verbose run sample/opencode.toml demo/py-add-001 --image scibench:0.1
```

Model/command/tool settings come from agent TOML. The selected TOML overrides
defaults from `agents_default.toml`.

Enable non-default agents via env vars:

```bash
SCIBENCH_ENABLE_CLAUDE=1 python3 runner/bench.py run sample/claude.toml demo/py-add-001 --image scibench:0.1
SCIBENCH_ENABLE_CODEX=1 python3 runner/bench.py run sample/codex.toml demo/py-add-001 --image scibench:0.1
SCIBENCH_ENABLE_COPILOT=1 python3 runner/bench.py run sample/copilot.toml demo/py-add-001 --image scibench:0.1
```

You usually do not need `--prompt`; the runner uses a default message. You can also
set `prompt` or `prompt_file` in the task's `task.toml`.

This runs the OpenCode one-shot session inside Docker by mounting:
- the task workdir at `/work`
- the run metadata (including `spec.md`) at `/run` (read-only)
- host agent binaries/configs as defined in merged config
- for OpenCode, optional host config `~/.config/opencode/opencode.json`

## Notes

- Network is configurable per run (`--network on|off`).
- Use `--result-dir` on `prepare/shell/run/eval` to control artifact location.

## Docs

- `docs/run-flow.md`: what happens during a benchmark run
