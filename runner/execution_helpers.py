from __future__ import annotations

import decimal
import re
import shlex
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Callable

try:
    from runner.stream_pretty import (
        _StreamPrettyState,
        _format_agent_plain_stream_line,
        _format_agent_stream_event,
        _phase_agent_name,
        flush_stream_state,
    )
except ModuleNotFoundError:  # pragma: no cover
    from stream_pretty import (  # type: ignore[no-redef]
        _StreamPrettyState,
        _format_agent_plain_stream_line,
        _format_agent_stream_event,
        _phase_agent_name,
        flush_stream_state,
    )


_INNER_SEC_RE = re.compile(r"^__BENCH_INNER_SEC__=([0-9]+(?:\.[0-9]+)?)$", re.MULTILINE)
_TIMEPOINT_RE = re.compile(
    r"^__(BENCH_T0|BENCH_T1)__=([0-9]+(?:\.[0-9]+)?)$", re.MULTILINE
)


def _redacted_cmd(cmd: list[str]) -> list[str]:
    out: list[str] = []
    redact_next_env = False
    for tok in cmd:
        if redact_next_env:
            if "=" in tok:
                k, _v = tok.split("=", 1)
                out.append(f"{k}=<redacted>")
            else:
                out.append(tok)
            redact_next_env = False
            continue

        out.append(tok)
        if tok == "-e":
            redact_next_env = True
    return out


def _cmd_str(cmd: list[str]) -> str:
    return shlex.join(_redacted_cmd(cmd))


def _timed_bash_script(cmd: str) -> str:
    return (
        'if [ -n "${EPOCHREALTIME:-}" ]; then __bench_t0="$EPOCHREALTIME"; '
        'else __bench_t0="$(date +%s.%N 2>/dev/null || date +%s)"; fi; '
        f"({cmd}); __bench_rc=$?; "
        'if [ -n "${EPOCHREALTIME:-}" ]; then __bench_t1="$EPOCHREALTIME"; '
        'else __bench_t1="$(date +%s.%N 2>/dev/null || date +%s)"; fi; '
        'printf "__BENCH_T0__=%s\\n__BENCH_T1__=%s\\n" "$__bench_t0" "$__bench_t1"; '
        'exit "$__bench_rc"'
    )


def _extract_inner_sec(*texts: str) -> float | None:
    t0: decimal.Decimal | None = None
    t1: decimal.Decimal | None = None

    for text in texts:
        if not text:
            continue
        for kind, value in _TIMEPOINT_RE.findall(text):
            try:
                parsed = decimal.Decimal(value)
            except decimal.InvalidOperation:
                continue
            if kind == "BENCH_T0":
                t0 = parsed
            elif kind == "BENCH_T1":
                t1 = parsed

    if t0 is not None and t1 is not None:
        dt = t1 - t0
        if dt < 0:
            return 0.0
        return float(dt)

    for text in texts:
        if not text:
            continue
        m = _INNER_SEC_RE.search(text)
        if not m:
            continue
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def _cleanup_docker_container(
    *,
    container_name: str,
    phase: str,
    verbose: bool,
    subprocess_mod: Any = subprocess,
) -> None:
    kill_cmd = ["docker", "kill", container_name]
    rm_cmd = ["docker", "rm", "-f", container_name]
    if verbose:
        print(f"[{phase}] timeout cleanup: {_cmd_str(kill_cmd)}", file=sys.stderr)
    subprocess_mod.run(
        kill_cmd,
        text=True,
        stdout=subprocess_mod.PIPE,
        stderr=subprocess_mod.PIPE,
        check=False,
        timeout=10,
    )
    if verbose:
        print(f"[{phase}] timeout cleanup: {_cmd_str(rm_cmd)}", file=sys.stderr)
    subprocess_mod.run(
        rm_cmd,
        text=True,
        stdout=subprocess_mod.PIPE,
        stderr=subprocess_mod.PIPE,
        check=False,
        timeout=10,
    )


def _run_capture_stream(
    cmd: list[str],
    *,
    timeout_sec: int,
    verbose: bool,
    phase: str,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    pretty_timeline: bool = False,
    timeout_cleanup: Callable[[], None] | None = None,
    subprocess_mod: Any = subprocess,
) -> subprocess.CompletedProcess:
    proc = subprocess_mod.Popen(
        cmd,
        text=True,
        stdout=subprocess_mod.PIPE,
        stderr=subprocess_mod.PIPE,
        cwd=cwd,
        env=env,
    )

    out_parts: list[str] = []
    err_parts: list[str] = []
    stream_state = _StreamPrettyState(agent_name=_phase_agent_name(phase))

    def _drain(pipe: Any, sink: list[str], label: str) -> None:
        try:
            for line in iter(pipe.readline, ""):
                sink.append(line)
                if verbose:
                    if pretty_timeline and label == "stdout":
                        parsed, rendered, suppress_raw = _format_agent_stream_event(
                            phase,
                            line,
                            state=stream_state,
                        )
                        if parsed:
                            if rendered:
                                print(rendered, file=sys.stderr)
                                continue
                            if suppress_raw:
                                continue
                        parsed_plain, rendered_plain = _format_agent_plain_stream_line(
                            phase, line
                        )
                        if parsed_plain:
                            if rendered_plain:
                                print(rendered_plain, file=sys.stderr)
                                continue
                    if line.endswith("\n"):
                        print(f"[{phase}] {label}: {line}", end="", file=sys.stderr)
                    else:
                        print(f"[{phase}] {label}: {line}", file=sys.stderr)
        finally:
            if (
                verbose
                and pretty_timeline
                and label == "stdout"
                and stream_state.agent_name == "claude"
            ):
                flushed = flush_stream_state(phase, stream_state)
                if flushed:
                    print(flushed, file=sys.stderr)
            pipe.close()

    assert proc.stdout is not None
    assert proc.stderr is not None
    t_out = threading.Thread(
        target=_drain, args=(proc.stdout, out_parts, "stdout"), daemon=True
    )
    t_err = threading.Thread(
        target=_drain, args=(proc.stderr, err_parts, "stderr"), daemon=True
    )
    t_out.start()
    t_err.start()

    try:
        rc = proc.wait(timeout=timeout_sec)
    except subprocess_mod.TimeoutExpired as e:
        proc.kill()
        proc.wait()
        if timeout_cleanup is not None:
            try:
                timeout_cleanup()
            except Exception as cleanup_err:  # pragma: no cover
                err_parts.append(f"[runner] timeout cleanup failed: {cleanup_err}\n")
        t_out.join()
        t_err.join()
        raise subprocess_mod.TimeoutExpired(
            cmd=e.cmd,
            timeout=e.timeout,
            output="".join(out_parts),
            stderr="".join(err_parts),
        ) from None
    except KeyboardInterrupt:
        proc.kill()
        proc.wait()
        if timeout_cleanup is not None:
            try:
                timeout_cleanup()
            except Exception as cleanup_err:  # pragma: no cover
                err_parts.append(f"[runner] timeout cleanup failed: {cleanup_err}\n")
        t_out.join()
        t_err.join()
        raise

    t_out.join()
    t_err.join()
    return subprocess_mod.CompletedProcess(
        cmd,
        rc,
        stdout="".join(out_parts),
        stderr="".join(err_parts),
    )
