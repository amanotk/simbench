import numpy as np

from src.wave3d import simulate_wave_3d
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


def test_hidden_reference_cases():
    for case in load_cases()[1:]:
        out = simulate_wave_3d(
            case["dt"],
            case["dx"],
            case["nx"],
            case["ny"],
            case["nz"],
            case["n_steps"],
        )
        assert_case_metrics_from_zyx(out, case, tol=1e-12)


def test_periodic_laplacian_sum_near_zero():
    case = load_cases()[0]
    out = simulate_wave_3d(
        case["dt"],
        case["dx"],
        case["nx"],
        case["ny"],
        case["nz"],
        case["n_steps"],
    )
    out_phys = as_physical_from_zyx(out, case["nx"], case["ny"], case["nz"])
    lap = _laplacian_periodic(out_phys, case["dx"])
    assert np.isclose(float(np.sum(lap)), 0.0, rtol=0.0, atol=1e-10)
