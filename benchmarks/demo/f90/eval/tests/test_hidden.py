import subprocess
from pathlib import Path

from rk2_shared import assert_close_seq, load_cases, run_cli


def _build_exe() -> Path:
    subprocess.run(["make", "-s", "clean", "all"], check=True)
    exe = Path("bin/rk2_cli")
    assert exe.exists()
    return exe


def test_all_shared_cases():
    exe = _build_exe()
    for case in load_cases():
        actual = run_cli(
            exe,
            case["rhs"],
            case["y0"],
            case["t0"],
            case["h"],
            case["n_steps"],
        )
        assert_close_seq(actual, case["expected"], tol=1e-9)
