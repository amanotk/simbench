import csv
import math
import os
import subprocess
from pathlib import Path


PUBLIC_TEST_TARGET = "cpp_full_solver1d_public_tests"


def _build_public_tests() -> Path:
    subprocess.run(["cmake", "-S", ".", "-B", "build"], check=True)
    subprocess.run(
        ["cmake", "--build", "build", "--target", PUBLIC_TEST_TARGET],
        check=True,
    )

    binary_name = f"{PUBLIC_TEST_TARGET}.exe" if os.name == "nt" else PUBLIC_TEST_TARGET
    executable_path = Path("build/tests") / binary_name
    assert executable_path.exists()
    return executable_path


def test_public_catch2_target_builds() -> None:
    _build_public_tests()


def test_public_brio_wu_cli_matches_reference_grid() -> None:
    _build_public_tests()

    solver_name = "cpp_full_solver1d.exe" if os.name == "nt" else "cpp_full_solver1d"
    solver_path = Path("build/bin") / solver_name
    assert solver_path.exists()

    completed = subprocess.run(
        [str(solver_path), "examples/brio_wu.toml"],
        check=True,
        capture_output=True,
        text=True,
    )

    rows = list(csv.reader(completed.stdout.splitlines()))
    assert rows[0] == ["x", "rho", "u", "v", "w", "p", "by", "bz"]
    assert len(rows) - 1 == 400

    dx = (1.0 - 0.0) / 400.0
    for index, row in enumerate(rows[1:]):
        assert len(row) == 8

        x_value = float(row[0])
        expected_x = 0.0 + (index + 0.5) * dx
        assert x_value == expected_x

        numeric_values = [float(component) for component in row[1:]]
        assert all(math.isfinite(component) for component in [x_value, *numeric_values])
        assert numeric_values[0] > 0.0
        assert numeric_values[4] > 0.0
