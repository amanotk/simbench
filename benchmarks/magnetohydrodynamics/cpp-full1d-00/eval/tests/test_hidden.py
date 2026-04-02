import csv
import os
import subprocess
from pathlib import Path

from mhd1d_shared import TOLERANCE, assert_csv_rows_close

SOLVER_TARGET = "cpp_full_solver1d"
WORKSPACE_ROOT = Path(__file__).resolve().parents[2] / "workspace"
REFERENCE_CSV_PATH = (
    Path(__file__).resolve().parents[3]
    / "shared"
    / "eval"
    / "fixtures"
    / "mhd1d"
    / "brio_wu_reference.csv"
)


def _build_solver(build_dir: Path) -> Path:
    subprocess.run(
        ["cmake", "-S", ".", "-B", str(build_dir)], check=True, cwd=WORKSPACE_ROOT
    )
    subprocess.run(
        ["cmake", "--build", str(build_dir), "--target", SOLVER_TARGET],
        check=True,
        cwd=WORKSPACE_ROOT,
    )

    binary_name = f"{SOLVER_TARGET}.exe" if os.name == "nt" else SOLVER_TARGET
    solver_path = build_dir / "bin" / binary_name
    assert solver_path.exists()
    return solver_path


def test_hidden_brio_wu_cli_matches_fixture(tmp_path: Path) -> None:
    solver_path = _build_solver(tmp_path / "build")
    output_csv_path = tmp_path / "brio_wu.csv"

    completed = subprocess.run(
        [str(solver_path), "200"],
        check=True,
        capture_output=True,
        text=True,
    )
    output_csv_path.write_text(completed.stdout, encoding="utf-8")

    output_rows = list(
        csv.reader(output_csv_path.read_text(encoding="utf-8").splitlines())
    )
    reference_rows = list(
        csv.reader(REFERENCE_CSV_PATH.read_text(encoding="utf-8").splitlines())
    )

    assert_csv_rows_close(
        output_rows,
        reference_rows,
        tolerance=TOLERANCE,
        expected_header=["x", "rho", "u", "v", "w", "p", "by", "bz"],
    )
