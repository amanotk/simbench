import json
import math
import subprocess
from pathlib import Path

import numpy as np


def _load_cases():
    path = Path("data/fd3d_cases.json")
    if not path.exists():
        path = (
            Path(__file__).resolve().parents[3]
            / "shared"
            / "workspace"
            / "data"
            / "fd3d_cases.json"
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["cases"]


def _build_exe() -> Path:
    subprocess.run(["make", "-s", "clean", "all"], check=True)
    exe = Path("bin/fd3d_cli")
    assert exe.exists()
    return exe


def _parse_flat_memory_order(lines: list[str], nx: int, ny: int, nz: int) -> np.ndarray:
    vals = [float(line.strip()) for line in lines if line.strip()]
    assert len(vals) == nx * ny * nz
    out = np.empty((nx, ny, nz), dtype=np.float64)
    p = 0
    for iz in range(nz):
        for iy in range(ny):
            for ix in range(nx):
                out[ix, iy, iz] = vals[p]
                p += 1
    return out


def _run_case(exe: Path, case: dict) -> np.ndarray:
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
    return _parse_flat_memory_order(
        proc.stdout.splitlines(), case["nx"], case["ny"], case["nz"]
    )


def test_cli_output_shape_and_probe_case0():
    case = _load_cases()[0]
    exe = _build_exe()
    out = _run_case(exe, case)
    assert out.shape == (case["nx"], case["ny"], case["nz"])
    ix, iy, iz = case["probes"][1]["ijk"]
    assert math.isclose(
        out[ix, iy, iz], case["probes"][1]["value"], rel_tol=0.0, abs_tol=1e-12
    )


def test_cli_public_mean_case0():
    case = _load_cases()[0]
    exe = _build_exe()
    out = _run_case(exe, case)
    assert math.isclose(float(np.mean(out)), case["mean"], rel_tol=0.0, abs_tol=1e-12)
