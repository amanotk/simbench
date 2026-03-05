from rk2_shared import assert_close_seq, load_cases
from src.rk2 import solve_rk2_midpoint


def _rhs_from_name(name):
    if name == "exp_growth":
        return lambda t, y: y
    if name == "damped_forced":
        return lambda t, y: -2.0 * y + t
    raise ValueError(name)


def test_all_shared_cases():
    for case in load_cases():
        actual = solve_rk2_midpoint(
            _rhs_from_name(case["rhs"]),
            case["y0"],
            case["t0"],
            case["h"],
            case["n_steps"],
        )
        assert_close_seq(actual, case["expected"], tol=1e-12)
