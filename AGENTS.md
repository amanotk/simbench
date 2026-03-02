# Agent Notes (Scientific Coding Benchmark)

This repo contains an agentic coding benchmark harness plus benchmark tasks.
Agents working here should keep runs isolated (fresh workdir per task) and keep
evaluation authoritative.

Cursor/Copilot rules:
- No `.cursor/rules/`, `.cursorrules`, or `.github/copilot-instructions.md` present.

Repo map (core):
- `benchmarks/<suite>/<task_id>/spec.md`: prompt shown to the model
- `benchmarks/<suite>/<task_id>/task.toml`: task metadata for the runner
- `benchmarks/<suite>/<task_id>/workspace/`: template copied into a fresh per-run workdir
- `benchmarks/<suite>/<task_id>/eval/`: evaluation harness (should be hidden from the model)
- `runner/bench.py`: CLI (list/prepare/shell/run/eval)
- `agents_default.toml`: default multi-agent config (opencode/codex/claude/copilot)
- `sample/*.toml`: sample single-agent overrides
- `docker/Dockerfile`: unified toolchain image (Python + C++ + Fortran)
- `runs/`: run artifacts (gitignored)


## Build / Lint / Test Commands

Build the unified Docker image:

```bash
docker build -t scibench:0.1 -f docker/Dockerfile .
```

Runner basics:

```bash
python3 runner/bench.py list
python3 runner/bench.py prepare sample/opencode.toml demo/py-add-001
python3 runner/bench.py shell sample/opencode.toml demo/py-add-001 --image scibench:0.1
python3 runner/bench.py run sample/opencode.toml demo/py-add-001 --image scibench:0.1
python3 runner/bench.py sample/opencode.toml demo/py-add-001 --image scibench:0.1
python3 runner/bench.py eval demo/py-add-001 --workdir /path/to/workdir --image scibench:0.1
```

Agent defaults:
- Model defaults come from merged config (`agents_default.toml` + override TOML).
- Agent enable uses per-agent env vars (opencode enabled by default), e.g.
  - `SCIBENCH_ENABLE_CLAUDE=1`
  - `SCIBENCH_ENABLE_CODEX=1`
  - `SCIBENCH_ENABLE_COPILOT=1`

Verbose runner output:

```bash
python3 runner/bench.py --verbose run sample/opencode.toml demo/py-add-001 --image scibench:0.1
```

Network tracks:

```bash
python3 runner/bench.py run sample/opencode.toml demo/py-add-001 --network on
python3 runner/bench.py run sample/opencode.toml demo/py-add-001 --network off
```

Public tests (inside an agent shell; these live under `workspace/tests/`):

```bash
pytest -q
```

Run tests via the runner's shell command (no need to manually `cd`):

```bash
python3 runner/bench.py shell --image scibench:0.1 sample/opencode.toml demo/py-add-001 -- pytest -q
```

Note: place shell options (like `--image`) before `agents task`, and use `--`
before a command that has flags (e.g. `-q`, `-k`).

Run a single test (preferred when iterating):

```bash
pytest -q tests/test_public.py::test_add_integers
```

Pytest keyword filter:

```bash
pytest -q -k float
```

Authoritative evaluation (hidden tests):

```bash
python3 runner/bench.py run sample/opencode.toml <suite>/<task_id>
python3 runner/bench.py eval <suite>/<task_id> --workdir /path/to/workdir
```

There is no "run one hidden test" CLI yet. While authoring tasks, you can
temporarily narrow evaluation by editing `benchmarks/<suite>/<task_id>/eval/run.sh`
or setting `eval_cmd` in `benchmarks/<suite>/<task_id>/task.toml`.

Lint (not enforced yet):

```bash
python3 -m py_compile runner/bench.py
```

Runner tests:

```bash
python3 -m unittest -q tests.test_runner_bench
```

Run a single test:

```bash
python3 -m unittest -q tests.test_runner_bench.TestBenchHelpers.test_expand_path
```

Timeouts:
- `--timeout-sec` is used as the per-phase timeout for both the agent one-shot and the eval harness.


## Common Workflows

Author a new task (manual, v0):
- Create `benchmarks/<suite>/<task_id>/` with `spec.md`, `task.toml`, `workspace/`, `eval/`.
- Ensure `eval/run.sh` is executable.
- Ensure `eval/run.sh` writes `/work/result.json`.

Debug a task locally: use `bench.py shell` to iterate, then `bench.py run` to score.


## Docker / Sandbox Notes

- The runner mounts the task workspace at `/work` (read/write).
- The runner mounts the eval harness at `/eval` (read-only) during `run`/`eval`.
- The `run`/`shell`/`prepare` commands use the selected agent TOML merged over `agents_default.toml`.
- Use `--network off` for an offline track (Docker `--network none`).
- Keep benchmark workspaces free of secrets; with network enabled, assume the agent can exfiltrate anything it can read.

Runner logs:
- `runs/.../logs/agent.docker_cmd.txt` or `runs/.../logs/agent.host_cmd.txt`: agent command line
- `runs/.../logs/eval.docker_cmd.txt`: eval command line


## Result Format (v0)

The eval harness writes `/work/result.json`, e.g. `{ "status": "passed", "score": 1.0 }`.
Add optional `metrics` fields as needed (keep it machine-readable and stable).


## Code Style Guidelines

General:
- ASCII by default; avoid new Unicode unless required.
- Prefer deterministic behavior (fixed seeds, tolerance-based numeric asserts).
- Keep the runner lightweight (stdlib-first).
- Text files: trailing newline.

Python (runner, `runner/`):
- Target Python 3.10+.
- Imports: stdlib only today; grouped and sorted.
- Formatting: PEP 8; keep lines ~88-100 chars; f-strings for messages.
- Types: annotate new/changed functions; prefer `Path` over string paths.
- Naming: `cmd_*` for CLI subcommands; `_helper` for internal helpers.
- Errors/exit codes: stderr for user-facing errors; `2` usage/config, `1` runtime, `0` OK.

Task metadata (`task.toml`):
- TOML, stable semantics.
- Suggested keys: `id`, `suite`, `language` (python|cpp|fortran), `time_limit_sec`, `eval_cmd`.
- Optional keys: `prompt` (string) or `prompt_file` (path relative to the task dir).

Task workspace (`workspace/`):
- Treat as a template; runner copies it to `runs/<run_id>/.../workdir/`.
- Put public/dev tests under `workspace/tests/` so the agent can run them.
- Keep scaffolds simple:
  - Python: `workspace/src/` + `pytest` tests.
  - C++: `CMakeLists.txt` or `Makefile` with one obvious target.
  - Fortran: `Makefile` with explicit targets.

Evaluation harness (`eval/`):
- In real benchmark runs, `eval/` should not be mounted into the agent container.
- `eval/run.sh` contract:
  - workspace mounted at `/work`, harness at `/eval` (read-only)
  - write `/work/result.json` (machine-readable)
  - avoid nondeterminism (thread env vars, stable tolerances)
  - exit `0` when evaluation completes; encode pass/fail in `result.json`

Shell scripts:
- `#!/usr/bin/env bash`
- Prefer `set -euo pipefail`; if you must capture failures, avoid `set -e` and
  handle exit codes explicitly.

Hygiene:
- Do not commit `runs/`.
