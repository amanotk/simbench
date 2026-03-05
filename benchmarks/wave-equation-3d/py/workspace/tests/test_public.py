import json
from pathlib import Path

import numpy as np

from src.wave3d import push_wave_3d


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


def _assert_case_metrics_from_zyx(u_zyx: np.ndarray, case: dict, tol: float = 1e-12):
    assert isinstance(u_zyx, np.ndarray)
    assert u_zyx.shape == (case["nz"], case["ny"], case["nx"])

    for probe in case["probes"]:
        ix, iy, iz = probe["ijk"]
        actual = float(u_zyx[iz, iy, ix])
        expected = float(probe["value"])
        assert np.isclose(actual, expected, rtol=0.0, atol=tol)

    assert np.isclose(float(np.mean(u_zyx)), case["mean"], rtol=0.0, atol=tol)


def _apply_periodic_ghosts(a: np.ndarray, nx: int, ny: int, nz: int) -> None:
    a[0, 1 : ny + 1, 1 : nx + 1] = a[nz, 1 : ny + 1, 1 : nx + 1]
    a[nz + 1, 1 : ny + 1, 1 : nx + 1] = a[1, 1 : ny + 1, 1 : nx + 1]
    a[1 : nz + 1, 0, 1 : nx + 1] = a[1 : nz + 1, ny, 1 : nx + 1]
    a[1 : nz + 1, ny + 1, 1 : nx + 1] = a[1 : nz + 1, 1, 1 : nx + 1]
    a[1 : nz + 1, 1 : ny + 1, 0] = a[1 : nz + 1, 1 : ny + 1, nx]
    a[1 : nz + 1, 1 : ny + 1, nx + 1] = a[1 : nz + 1, 1 : ny + 1, 1]


def _init_state_zyx(case: dict) -> tuple[np.ndarray, np.ndarray]:
    nx = case["nx"]
    ny = case["ny"]
    nz = case["nz"]
    sigma = 0.1

    u = np.zeros((nz + 2, ny + 2, nx + 2), dtype=np.float64)
    v = np.zeros_like(u)

    x = (np.arange(nx, dtype=np.float64) + 0.5) / float(nx)
    y = (np.arange(ny, dtype=np.float64) + 0.5) / float(ny)
    z = (np.arange(nz, dtype=np.float64) + 0.5) / float(nz)
    zz, yy, xx = np.meshgrid(z, y, x, indexing="ij")
    w = ((xx - 0.5) ** 2 + (yy - 0.5) ** 2 + (zz - 0.5) ** 2) / (2.0 * sigma * sigma)
    u[1 : nz + 1, 1 : ny + 1, 1 : nx + 1] = np.exp(-w)

    _apply_periodic_ghosts(u, nx, ny, nz)
    _apply_periodic_ghosts(v, nx, ny, nz)
    return u, v


def _run_case(case: dict) -> np.ndarray:
    u, v = _init_state_zyx(case)
    for _ in range(case["n_steps"]):
        push_wave_3d(u, v, case["dt"], case["dx"], case["nx"], case["ny"], case["nz"])
    return u[1 : case["nz"] + 1, 1 : case["ny"] + 1, 1 : case["nx"] + 1].copy()


def test_push_updates_state_with_expected_shape():
    case = _load_cases()[0]
    out = _run_case(case)
    assert isinstance(out, np.ndarray)
    assert out.shape == (case["nz"], case["ny"], case["nx"])


def test_public_reference_probes_and_moments():
    case = _load_cases()[0]
    out = _run_case(case)
    _assert_case_metrics_from_zyx(out, case, tol=1e-12)
