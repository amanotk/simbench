# Scientific Coding Benchmark (LLM)

This repo hosts an agentic coding benchmark for scientific computing tasks.

Design goals:
- Isolated runs: fresh model session and fresh filesystem per task.
- Agentic: the model can run commands/tests while solving.
- Hidden eval: authoritative evaluation lives outside the agent workspace.

## Layout

- `benchmarks/<suite>/<task_id>/spec.md`: the problem statement shown to the model
- `benchmarks/<suite>/<task_id>/task.json`: minimal task metadata for the runner
- `benchmarks/<suite>/<task_id>/workspace/`: template workspace copied per run (model edits here)
- `benchmarks/<suite>/<task_id>/eval/`: evaluation harness (not mounted into the agent container)
- `runner/bench.py`: minimal CLI (list/run)
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

Run evaluation for a task (no model loop yet; just evaluates the workspace template):

```bash
python3 runner/bench.py run demo/py-add-001 --image scibench:0.1
```

Run a one-shot OpenCode solve + eval (requires OpenCode configured):

```bash
python3 runner/bench.py opencode demo/py-add-001 --image scibench:0.1 -m openai/gpt-5.3-codex
```

Generic agent form (configured via `agents.json`):

```bash
python3 runner/bench.py agent demo/py-add-001 --agent opencode --image scibench:0.1 -m openai/gpt-5.3-codex
```

You usually do not need `--prompt`; the runner uses a default message. You can also
set `prompt` or `prompt_file` in the task's `task.json`.

This runs the OpenCode one-shot session inside Docker by mounting:
- the task workdir at `/work`
- the run metadata (including `spec.md`) at `/run` (read-only)
- host agent binaries/configs as defined in `agents.json`

Open a shell in an isolated workspace (useful for manual task authoring/debugging):

```bash
python3 runner/bench.py shell demo/py-add-001 --image scibench:0.1
```

Run a command inside the workspace (use `--` before command flags):

```bash
python3 runner/bench.py shell demo/py-add-001 --image scibench:0.1 -- pytest -q
```

## Notes

- Network is configurable per run (`--network on|off`).
- The v0 runner executes `eval_cmd` inside Docker with the task workspace mounted at `/work` and the eval harness mounted at `/eval` (read-only).

## Docs

- `docs/run-flow.md`: what happens during a benchmark run
