from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np


def load_cases() -> list[dict]:
    path = Path("/work/data/fd3d_cases.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload["cases"])


def assert_case_metrics(u_out: np.ndarray, case: dict, tol: float = 1e-12) -> None:
    assert isinstance(u_out, np.ndarray)
    assert tuple(u_out.shape) == (case["nx"], case["ny"], case["nz"])

    for probe in case["probes"]:
        i, j, k = probe["ijk"]
        expected = float(probe["value"])
        actual = float(u_out[i, j, k])
        assert math.isclose(actual, expected, rel_tol=0.0, abs_tol=tol), (
            (i, j, k),
            actual,
            expected,
        )

    mean_actual = float(np.mean(u_out))
    l2_actual = float(np.sqrt(np.mean(u_out * u_out)))
    max_abs_actual = float(np.max(np.abs(u_out)))

    assert math.isclose(mean_actual, float(case["mean"]), rel_tol=0.0, abs_tol=tol)
    assert math.isclose(l2_actual, float(case["l2"]), rel_tol=0.0, abs_tol=tol)
    assert math.isclose(
        max_abs_actual, float(case["max_abs"]), rel_tol=0.0, abs_tol=tol
    )
