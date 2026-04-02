import csv
import os
import subprocess
from pathlib import Path

PUBLIC_TEST_TARGET = "cpp_full_solver1d_public_tests"
GOLDEN_CSV_PATH = Path(__file__).resolve().parents[1] / "tests/data/brio_wu_golden.csv"
TOLERANCE = 1.0e-12
WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


def assert_csv_rows_close(
    output_rows: list[list[str]],
    reference_rows: list[list[str]],
    *,
    tolerance: float = TOLERANCE,
    expected_header: list[str] | None = None,
) -> None:
    if expected_header is not None:
        assert output_rows[0] == expected_header
        output_rows = output_rows[1:]

    assert len(output_rows) == len(reference_rows)

    for output_row, reference_row in zip(output_rows, reference_rows):
        assert len(output_row) == len(reference_row)
        for output_value, reference_value in zip(output_row, reference_row):
            assert abs(float(output_value) - float(reference_value)) <= tolerance


def _build_public_tests() -> Path:
    build_dir = "build"
    subprocess.run(["cmake", "-S", ".", "-B", build_dir], check=True, cwd=WORKSPACE_ROOT)
    subprocess.run(
        [
            "cmake",
            "--build",
            build_dir,
            "--target",
            "cpp_full_solver1d",
            PUBLIC_TEST_TARGET,
        ],
        check=True,
        cwd=WORKSPACE_ROOT,
    )

    binary_name = f"{PUBLIC_TEST_TARGET}.exe" if os.name == "nt" else PUBLIC_TEST_TARGET
    executable_path = WORKSPACE_ROOT / build_dir / "tests" / binary_name
    assert executable_path.exists()
    return executable_path


def test_public_catch2_target_builds() -> None:
    _build_public_tests()


def test_public_brio_wu_cli_matches_reference_grid() -> None:
    _build_public_tests()

    solver_name = "cpp_full_solver1d.exe" if os.name == "nt" else "cpp_full_solver1d"
    solver_path = WORKSPACE_ROOT / "build/bin" / solver_name
    assert solver_path.exists()

    completed = subprocess.run(
        [str(solver_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    rows = list(csv.reader(completed.stdout.splitlines()))
    golden_rows = list(csv.reader(GOLDEN_CSV_PATH.read_text(encoding="utf-8").splitlines()))

    assert golden_rows[0] == ["x", "rho", "u", "v", "w", "p", "by", "bz"]

    assert_csv_rows_close(
        rows,
        golden_rows[1:],
        tolerance=TOLERANCE,
        expected_header=["x", "rho", "u", "v", "w", "p", "by", "bz"],
    )
