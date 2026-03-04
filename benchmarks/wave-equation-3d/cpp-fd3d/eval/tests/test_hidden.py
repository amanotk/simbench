import subprocess
from pathlib import Path

from wave3d_shared import assert_case_metrics, load_cases, parse_flat_physical


def _build_exe() -> Path:
    subprocess.run(["make", "-s", "clean", "all"], check=True)
    exe = Path("bin/fd3d_cli")
    assert exe.exists()
    return exe


def test_all_shared_cases():
    exe = _build_exe()
    for case in load_cases():
        proc = subprocess.run(
            [
                str(exe),
                str(case["dt"]),
                str(case["dx"]),
                str(case["nx"]),
                str(case["ny"]),
                str(case["nz"]),
                str(case["n_steps"]),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        out_phys = parse_flat_physical(
            proc.stdout.splitlines(), case["nx"], case["ny"], case["nz"]
        )
        assert_case_metrics(out_phys, case, tol=1e-12)
