import subprocess
from pathlib import Path

import numpy as np

from wave3d_shared import assert_case_metrics, load_cases


def _build_exe() -> Path:
    subprocess.run(["make", "-s", "clean", "all"], check=True)
    exe = Path("bin/fd3d_cli")
    assert exe.exists()
    return exe


def _parse_flat_memory_order(lines: list[str], nx: int, ny: int, nz: int) -> np.ndarray:
    values = [float(s.strip()) for s in lines if s.strip()]
    expected_n = nx * ny * nz
    assert len(values) == expected_n, (len(values), expected_n)

    out = np.empty((nx, ny, nz), dtype=np.float64)
    p = 0
    for iz in range(nz):
        for iy in range(ny):
            for ix in range(nx):
                out[ix, iy, iz] = values[p]
                p += 1
    return out


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
        out_phys = _parse_flat_memory_order(
            proc.stdout.splitlines(), case["nx"], case["ny"], case["nz"]
        )
        assert_case_metrics(out_phys, case, tol=1e-12)
