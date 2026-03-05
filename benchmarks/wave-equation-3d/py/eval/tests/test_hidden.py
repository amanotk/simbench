import numpy as np

from src.wave3d import push_wave_3d
from wave3d_shared import as_physical_from_zyx, assert_case_metrics_from_zyx, load_cases


def _laplacian_periodic(u: np.ndarray, dx: float) -> np.ndarray:
    nx, ny, nz = u.shape
    out = np.empty_like(u)
    inv_dx2 = 1.0 / (dx * dx)

    for i in range(nx):
        i_minus = (i - 1) % nx
        i_plus = (i + 1) % nx
        for j in range(ny):
            j_minus = (j - 1) % ny
            j_plus = (j + 1) % ny
            for k in range(nz):
                k_minus = (k - 1) % nz
                k_plus = (k + 1) % nz
                out[i, j, k] = (
                    (u[i_plus, j, k] - 2.0 * u[i, j, k] + u[i_minus, j, k])
                    + (u[i, j_plus, k] - 2.0 * u[i, j, k] + u[i, j_minus, k])
                    + (u[i, j, k_plus] - 2.0 * u[i, j, k] + u[i, j, k_minus])
                ) * inv_dx2

    return out


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
    assert u.shape == (case["nz"] + 2, case["ny"] + 2, case["nx"] + 2)
    assert v.shape == (case["nz"] + 2, case["ny"] + 2, case["nx"] + 2)
    for _ in range(case["n_steps"]):
        push_wave_3d(u, v, case["dt"], case["dx"], case["nx"], case["ny"], case["nz"])
    return u[1 : case["nz"] + 1, 1 : case["ny"] + 1, 1 : case["nx"] + 1].copy()


def test_hidden_reference_cases():
    for case in load_cases()[1:]:
        out = _run_case(case)
        assert_case_metrics_from_zyx(out, case, tol=1e-12)


def test_periodic_laplacian_sum_near_zero():
    case = load_cases()[0]
    out = _run_case(case)
    out_phys = as_physical_from_zyx(out, case["nx"], case["ny"], case["nz"])
    lap = _laplacian_periodic(out_phys, case["dx"])
    assert np.isclose(float(np.sum(lap)), 0.0, rtol=0.0, atol=1e-10)
