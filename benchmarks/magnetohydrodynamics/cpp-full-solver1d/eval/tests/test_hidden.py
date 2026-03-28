import math
import os
import subprocess
from pathlib import Path

from mhd1d_shared import (
    CSV_HEADER,
    compare_mhd1d_csv_against_fixture,
    load_mhd1d_csv_profile,
)


SOLVER_TARGET = "cpp_full_solver1d"


def _build_solver(build_dir: Path) -> Path:
    subprocess.run(["cmake", "-S", ".", "-B", str(build_dir)], check=True)
    subprocess.run(
        ["cmake", "--build", str(build_dir), "--target", SOLVER_TARGET],
        check=True,
    )

    binary_name = f"{SOLVER_TARGET}.exe" if os.name == "nt" else SOLVER_TARGET
    solver_path = build_dir / "bin" / binary_name
    assert solver_path.exists()
    return solver_path


def test_hidden_brio_wu_cli_matches_fixture(tmp_path: Path) -> None:
    solver_path = _build_solver(tmp_path / "build")
    output_csv_path = tmp_path / "brio_wu.csv"

    completed = subprocess.run(
        [str(solver_path), "examples/brio_wu.toml"],
        check=True,
        capture_output=True,
        text=True,
    )
    output_csv_path.write_text(completed.stdout, encoding="utf-8")

    profile = load_mhd1d_csv_profile(output_csv_path)
    assert profile.header == CSV_HEADER

    comparison = compare_mhd1d_csv_against_fixture(output_csv_path)
    assert comparison.passed

    for column_name in ("v", "w", "bz"):
        for row in profile.rows:
            assert math.isfinite(row[column_name])
