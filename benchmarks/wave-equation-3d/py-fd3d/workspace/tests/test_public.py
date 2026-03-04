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
    assert out.shape == (case["nx"], case["ny"], case["nz"])


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
    for probe in case["probes"]:
        i, j, k = probe["ijk"]
        assert np.isclose(out[i, j, k], probe["value"], rtol=0.0, atol=1e-12)
    assert np.isclose(float(np.mean(out)), case["mean"], rtol=0.0, atol=1e-12)
