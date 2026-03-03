from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path


def load_cases() -> list[dict]:
    path = Path("/work/data/rk2_cases.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload["cases"])


def assert_close_seq(
    actual: list[float], expected: list[float], tol: float = 1e-10
) -> None:
    assert len(actual) == len(expected), (len(actual), len(expected))
    for i, (a, e) in enumerate(zip(actual, expected)):
        assert math.isclose(a, e, rel_tol=0.0, abs_tol=tol), (i, a, e)


def run_cli(
    exe: Path, rhs: str, y0: float, t0: float, h: float, n_steps: int
) -> list[float]:
    proc = subprocess.run(
        [str(exe), rhs, str(y0), str(t0), str(h), str(n_steps)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    out: list[float] = []
    for line in proc.stdout.splitlines():
        s = line.strip()
        if s:
            out.append(float(s))
    return out
