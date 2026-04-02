#!/usr/bin/env python3
"""Plot a Brio-Wu solver CSV and save an image.

Usage:
    python plot_solution.py [path/to/solution.csv] [path/to/output.png]

If no path is provided, the script looks for ``solution.csv`` in the current
working directory and writes ``solution.png`` there.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


EXPECTED_FIELDS = ["x", "rho", "u", "v", "w", "p", "by", "bz"]
DEFAULT_CSV = Path("solution.csv")
DEFAULT_OUTPUT = Path("solution.png")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot the Brio-Wu solver profiles from a CSV file.",
    )
    parser.add_argument(
        "csv_path",
        nargs="?",
        type=Path,
        default=DEFAULT_CSV,
        help="CSV file to plot (defaults to solution.csv in the current directory).",
    )
    parser.add_argument(
        "output_path",
        nargs="?",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output image path (defaults to solution.png in the current directory).",
    )
    return parser.parse_args()


def load_columns(csv_path: Path) -> dict[str, list[float]]:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        try:
            first_row = next(reader)
        except StopIteration as exc:
            raise ValueError(f"{csv_path} is empty") from exc

        if first_row == EXPECTED_FIELDS:
            rows = reader
        else:
            if len(first_row) != len(EXPECTED_FIELDS):
                raise ValueError(
                    f"expected {len(EXPECTED_FIELDS)} CSV columns; got {len(first_row)}"
                )
            rows = [first_row, *reader]

        columns: dict[str, list[float]] = {field: [] for field in EXPECTED_FIELDS}
        for raw_row in rows:
            if len(raw_row) != len(EXPECTED_FIELDS):
                raise ValueError(
                    f"expected {len(EXPECTED_FIELDS)} CSV columns; got {len(raw_row)}"
                )
            for field, raw_value in zip(EXPECTED_FIELDS, raw_row, strict=True):
                columns[field].append(float(raw_value))

    return columns


def main() -> int:
    args = parse_args()
    csv_path = args.csv_path
    output_path = args.output_path

    if not csv_path.is_file():
        print(f"error: CSV file not found: {csv_path}", file=sys.stderr)
        return 1

    try:
        columns = load_columns(csv_path)
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    x_values = columns["x"]

    fig, axes = plt.subplots(2, 2, figsize=(10, 7), sharex=True)
    plots = [
        (axes[0, 0], "rho", r"$\rho$"),
        (axes[0, 1], "u", r"$u$"),
        (axes[1, 0], "p", r"$p$"),
        (axes[1, 1], "by", r"$B_y$"),
    ]

    for axis, field, ylabel in plots:
        axis.plot(x_values, columns[field], linewidth=1.5)
        axis.set_ylabel(ylabel)
        axis.grid(True, alpha=0.3)

    for axis in axes[1, :]:
        axis.set_xlabel(r"$x$")

    fig.suptitle(r"Brio-Wu Problem at $t = 0.1$")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
