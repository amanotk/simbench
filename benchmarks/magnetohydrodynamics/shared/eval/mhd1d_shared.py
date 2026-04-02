from __future__ import annotations

from typing import Sequence


TOLERANCE = 1.0e-12


def assert_csv_rows_close(
    output_rows: Sequence[Sequence[str]],
    reference_rows: Sequence[Sequence[str]],
    *,
    tolerance: float = TOLERANCE,
    expected_header: Sequence[str] | None = None,
) -> None:
    if expected_header is not None:
        assert list(output_rows[0]) == list(expected_header)
        output_rows = output_rows[1:]

    assert len(output_rows) == len(reference_rows)

    for output_row, reference_row in zip(output_rows, reference_rows):
        assert len(output_row) == len(reference_row)
        for output_value, reference_value in zip(output_row, reference_row):
            output_float = float(output_value)
            reference_float = float(reference_value)
            assert abs(output_float - reference_float) <= tolerance
