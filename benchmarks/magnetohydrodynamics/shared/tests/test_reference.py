from __future__ import annotations

import csv
import os
import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.magnetohydrodynamics.shared.eval.mhd1d_shared import (
    TOLERANCE,
    assert_csv_rows_close,
)


SHARED_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_CSV_PATH = SHARED_ROOT / "eval" / "fixtures" / "mhd1d" / "brio_wu_reference.csv"


def _build_reference_solver() -> Path:
    build_dir = SHARED_ROOT / "build"
    subprocess.run(["cmake", "-S", str(SHARED_ROOT), "-B", str(build_dir)], check=True)
    subprocess.run(
        ["cmake", "--build", str(build_dir), "--target", "mhd1d_reference"],
        check=True,
    )

    binary_name = "mhd1d_reference.exe" if os.name == "nt" else "mhd1d_reference"
    binary_path = build_dir / "bin" / binary_name
    assert binary_path.exists()
    return binary_path


def test_shared_reference_solver_matches_fixture(tmp_path: Path) -> None:
    solver_path = _build_reference_solver()
    output_csv_path = tmp_path / "solution.csv"

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
        csv.reader(FIXTURE_CSV_PATH.read_text(encoding="utf-8").splitlines())
    )

    assert_csv_rows_close(output_rows, reference_rows, tolerance=TOLERANCE)
