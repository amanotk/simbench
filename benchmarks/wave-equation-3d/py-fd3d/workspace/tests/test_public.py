import json
from pathlib import Path

import numpy as np

from src.wave3d import simulate_wave_3d


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


def test_returns_numpy_array_with_expected_shape():
    case = _load_cases()[0]
    out = simulate_wave_3d(
        case["dt"],
        case["dx"],
        case["nx"],
        case["ny"],
        case["nz"],
        case["n_steps"],
    )
    assert isinstance(out, np.ndarray)
    assert out.shape == (case["nz"], case["ny"], case["nx"])


def test_public_reference_probes_and_moments():
    case = _load_cases()[0]
    out = simulate_wave_3d(
        case["dt"],
        case["dx"],
        case["nx"],
        case["ny"],
        case["nz"],
        case["n_steps"],
    )
    _assert_case_metrics_from_zyx(out, case, tol=1e-12)
