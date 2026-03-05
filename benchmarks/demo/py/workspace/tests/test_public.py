import json
import math
from pathlib import Path

from src.rk2 import solve_rk2_midpoint


def _cases():
    path = Path("data/rk2_cases.json")
    if not path.exists():
        path = (
            Path(__file__).resolve().parents[3]
            / "shared"
            / "workspace"
            / "data"
            / "rk2_cases.json"
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["cases"]


def _rhs_from_name(name):
    if name == "exp_growth":
        return lambda t, y: y
    if name == "damped_forced":
        return lambda t, y: -2.0 * y + t
    raise ValueError(name)


def test_first_reference_case():
    case = _cases()[0]
    actual = solve_rk2_midpoint(
        _rhs_from_name(case["rhs"]),
        case["y0"],
        case["t0"],
        case["h"],
        case["n_steps"],
    )
    expected = case["expected"]
    assert len(actual) == len(expected)
    assert math.isclose(actual[-1], expected[-1], rel_tol=0.0, abs_tol=1e-12)


def test_zero_steps_returns_initial_value_only():
    out = solve_rk2_midpoint(lambda t, y: y, 3.2, 0.0, 0.1, 0)
    assert out == [3.2]
