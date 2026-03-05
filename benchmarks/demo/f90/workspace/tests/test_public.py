import json
import math
import subprocess
from pathlib import Path


def _load_cases():
    path = Path("data/rk2_cases.json")
    if not path.exists():
        path = (
            Path(__file__).resolve().parents[3]
            / "shared"
            / "workspace"
            / "data"
            / "rk2_cases.json"
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["cases"]


def _build_exe():
    subprocess.run(["make", "-s", "clean", "all"], check=True)
    exe = Path("bin/rk2_cli")
    assert exe.exists()
    return exe


def _run_case(exe: Path, case: dict):
    proc = subprocess.run(
        [
            str(exe),
            case["rhs"],
            str(case["y0"]),
            str(case["t0"]),
            str(case["h"]),
            str(case["n_steps"]),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return [float(line.strip()) for line in proc.stdout.splitlines() if line.strip()]


def test_cli_first_reference_case():
    exe = _build_exe()
    case = _load_cases()[0]
    actual = _run_case(exe, case)
    expected = case["expected"]
    assert len(actual) == len(expected)
    assert math.isclose(actual[-1], expected[-1], rel_tol=0.0, abs_tol=1e-9)
