import numpy as np

from src.wave3d import simulate_wave_3d
from wave3d_shared import assert_case_metrics, load_cases


def _laplacian_periodic(u: np.ndarray, dx: float) -> np.ndarray:
    return (
        (np.roll(u, -1, axis=0) - 2.0 * u + np.roll(u, 1, axis=0)) / (dx * dx)
        + (np.roll(u, -1, axis=1) - 2.0 * u + np.roll(u, 1, axis=1)) / (dx * dx)
        + (np.roll(u, -1, axis=2) - 2.0 * u + np.roll(u, 1, axis=2)) / (dx * dx)
    )


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
        assert_case_metrics(out, case, tol=1e-12)


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
    lap = _laplacian_periodic(out, case["dx"])
    assert np.isclose(float(np.sum(lap)), 0.0, rtol=0.0, atol=1e-10)
