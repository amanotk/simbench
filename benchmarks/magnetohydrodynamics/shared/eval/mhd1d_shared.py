"""Shared hidden-eval helpers for the canonical 1D Brio-Wu benchmark."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


CSV_HEADER = ("x", "rho", "u", "v", "w", "p", "by", "bz")
SCORING_VARIABLES = ("rho", "u", "p", "by")
DEFAULT_EXCLUDE_EDGE_ADJACENTS_PER_SIDE = 2
DEFAULT_FIXTURE_NAME = "brio_wu_fixture.json"


@dataclass(frozen=True)
class MHD1DCSVProfile:
    """Parsed CSV profile with schema validation already applied."""

    csv_path: Path
    header: tuple[str, ...]
    rows: list[dict[str, float]]


@dataclass(frozen=True)
class MHD1DFixture:
    """Loaded Brio-Wu fixture metadata plus the reference CSV profile."""

    fixture_path: Path
    reference_csv_path: Path
    schema: tuple[str, ...]
    scored_variables: tuple[str, ...]
    abs_l1: dict[str, float]
    abs_linf: dict[str, float]
    interior_cell_window_exclude_edge_adjacents_per_side: int
    metadata: dict[str, object]
    reference_profile: MHD1DCSVProfile


@dataclass(frozen=True)
class VariableComparison:
    """Per-variable error summary for a solver profile."""

    variable: str
    l1: float
    linf: float
    abs_l1_tolerance: float
    abs_linf_tolerance: float

    @property
    def passed(self) -> bool:
        return self.l1 <= self.abs_l1_tolerance and self.linf <= self.abs_linf_tolerance


@dataclass(frozen=True)
class MHD1DComparison:
    """Comparison outcome for a solver CSV against the Brio-Wu fixture."""

    solver_csv_path: Path
    fixture: MHD1DFixture
    compared_row_start: int
    compared_row_stop: int
    compared_row_count: int
    variable_comparisons: dict[str, VariableComparison]

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.variable_comparisons.values())


def _default_fixture_path() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "mhd1d" / DEFAULT_FIXTURE_NAME


def _require_exact_header(header: Sequence[str], *, source: Path) -> None:
    actual = tuple(header)
    if actual != CSV_HEADER:
        raise ValueError(
            f"{source} must use the exact CSV header {','.join(CSV_HEADER)}"
        )


def _parse_float_cell(
    raw_value: str, *, source: Path, row_number: int, column_name: str
) -> float:
    try:
        return float(raw_value)
    except ValueError as exc:
        raise ValueError(
            f"{source} row {row_number} column {column_name} must be a floating-point value"
        ) from exc


def load_mhd1d_csv_profile(csv_path: str | Path) -> MHD1DCSVProfile:
    """Load and validate a Brio-Wu-style CSV profile."""

    path = Path(csv_path)
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.reader(csv_file)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError(f"{path} is empty") from exc

        _require_exact_header(header, source=path)

        rows: list[dict[str, float]] = []
        for row_number, raw_row in enumerate(reader, start=2):
            if len(raw_row) != len(CSV_HEADER):
                raise ValueError(
                    f"{path} row {row_number} must have exactly {len(CSV_HEADER)} columns"
                )
            parsed_row: dict[str, float] = {}
            for column_name, raw_value in zip(CSV_HEADER, raw_row, strict=True):
                parsed_row[column_name] = _parse_float_cell(
                    raw_value,
                    source=path,
                    row_number=row_number,
                    column_name=column_name,
                )
            rows.append(parsed_row)

    return MHD1DCSVProfile(csv_path=path, header=tuple(header), rows=rows)


def _validate_fixture_metadata(
    fixture_payload: Mapping[str, object], *, source: Path
) -> None:
    schema = fixture_payload.get("schema")
    if tuple(schema or ()) != CSV_HEADER:
        raise ValueError(
            f"{source} must declare the exact schema {','.join(CSV_HEADER)}"
        )

    scored_variables = fixture_payload.get("scored_variables")
    if tuple(scored_variables or ()) != SCORING_VARIABLES:
        raise ValueError(
            f"{source} must declare scored_variables {','.join(SCORING_VARIABLES)}"
        )

    window = fixture_payload.get("interior_cell_window")
    if not isinstance(window, Mapping):
        raise ValueError(f"{source} must define interior_cell_window metadata")

    exclude = window.get("exclude_edge_adjacents_per_side")
    if exclude != DEFAULT_EXCLUDE_EDGE_ADJACENTS_PER_SIDE:
        raise ValueError(
            f"{source} must exclude {DEFAULT_EXCLUDE_EDGE_ADJACENTS_PER_SIDE} edge-adjacent cells per side"
        )

    for key_name in ("abs_l1", "abs_linf"):
        tolerances = fixture_payload.get(key_name)
        if not isinstance(tolerances, Mapping):
            raise ValueError(f"{source} must define {key_name} tolerances")
        for variable_name in SCORING_VARIABLES:
            if variable_name not in tolerances:
                raise ValueError(f"{source} must define {key_name}.{variable_name}")


def load_mhd1d_fixture(fixture_path: str | Path | None = None) -> MHD1DFixture:
    """Load the canonical Brio-Wu hidden fixture and its reference CSV profile."""

    path = Path(fixture_path) if fixture_path is not None else _default_fixture_path()
    with path.open("r", encoding="utf-8") as fixture_file:
        payload = json.load(fixture_file)

    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")

    _validate_fixture_metadata(payload, source=path)

    reference_csv_name = payload.get("reference_csv")
    if not isinstance(reference_csv_name, str) or not reference_csv_name:
        raise ValueError(f"{path} must declare a reference_csv file name")

    reference_csv_path = (path.parent / reference_csv_name).resolve()
    reference_profile = load_mhd1d_csv_profile(reference_csv_path)

    return MHD1DFixture(
        fixture_path=path,
        reference_csv_path=reference_csv_path,
        schema=tuple(payload["schema"]),
        scored_variables=tuple(payload["scored_variables"]),
        abs_l1={
            variable: float(value) for variable, value in payload["abs_l1"].items()
        },
        abs_linf={
            variable: float(value) for variable, value in payload["abs_linf"].items()
        },
        interior_cell_window_exclude_edge_adjacents_per_side=int(
            payload["interior_cell_window"]["exclude_edge_adjacents_per_side"]
        ),
        metadata=payload,
        reference_profile=reference_profile,
    )


def interior_cell_window_bounds(
    row_count: int,
    exclude_edge_adjacents_per_side: int = DEFAULT_EXCLUDE_EDGE_ADJACENTS_PER_SIDE,
) -> tuple[int, int]:
    """Return the inclusive-start/exclusive-stop comparison window for a profile."""

    if row_count <= 0:
        raise ValueError("row_count must be positive")
    if exclude_edge_adjacents_per_side < 0:
        raise ValueError("exclude_edge_adjacents_per_side must be non-negative")
    if row_count <= 2 * exclude_edge_adjacents_per_side:
        raise ValueError("row_count is too small for the requested interior window")
    return exclude_edge_adjacents_per_side, row_count - exclude_edge_adjacents_per_side


def _compare_variable(
    solver_rows: Sequence[Mapping[str, float]],
    reference_rows: Sequence[Mapping[str, float]],
    variable_name: str,
    row_start: int,
    row_stop: int,
    *,
    abs_l1_tolerance: float,
    abs_linf_tolerance: float,
) -> VariableComparison:
    l1_error = 0.0
    linf_error = 0.0
    for row_index in range(row_start, row_stop):
        delta = abs(
            float(solver_rows[row_index][variable_name])
            - float(reference_rows[row_index][variable_name])
        )
        l1_error += delta
        if delta > linf_error:
            linf_error = delta

    return VariableComparison(
        variable=variable_name,
        l1=l1_error,
        linf=linf_error,
        abs_l1_tolerance=abs_l1_tolerance,
        abs_linf_tolerance=abs_linf_tolerance,
    )


def compare_mhd1d_csv_against_fixture(
    solver_csv_path: str | Path,
    fixture: MHD1DFixture | None = None,
) -> MHD1DComparison:
    """Compare a solver-produced CSV profile against the canonical Brio-Wu fixture."""

    loaded_fixture = fixture if fixture is not None else load_mhd1d_fixture()
    solver_profile = load_mhd1d_csv_profile(solver_csv_path)

    if solver_profile.header != loaded_fixture.schema:
        raise ValueError("solver CSV header does not match the fixture schema")

    reference_rows = loaded_fixture.reference_profile.rows
    solver_rows = solver_profile.rows
    if len(solver_rows) != len(reference_rows):
        raise ValueError(
            "solver CSV row count does not match the fixture reference profile"
        )

    row_start, row_stop = interior_cell_window_bounds(
        len(reference_rows),
        loaded_fixture.interior_cell_window_exclude_edge_adjacents_per_side,
    )

    variable_comparisons: dict[str, VariableComparison] = {}
    for variable_name in loaded_fixture.scored_variables:
        variable_comparisons[variable_name] = _compare_variable(
            solver_rows,
            reference_rows,
            variable_name,
            row_start,
            row_stop,
            abs_l1_tolerance=loaded_fixture.abs_l1[variable_name],
            abs_linf_tolerance=loaded_fixture.abs_linf[variable_name],
        )

    return MHD1DComparison(
        solver_csv_path=solver_profile.csv_path,
        fixture=loaded_fixture,
        compared_row_start=row_start,
        compared_row_stop=row_stop,
        compared_row_count=row_stop - row_start,
        variable_comparisons=variable_comparisons,
    )


__all__ = [
    "CSV_HEADER",
    "SCORING_VARIABLES",
    "DEFAULT_EXCLUDE_EDGE_ADJACENTS_PER_SIDE",
    "MHD1DCSVProfile",
    "MHD1DFixture",
    "VariableComparison",
    "MHD1DComparison",
    "compare_mhd1d_csv_against_fixture",
    "interior_cell_window_bounds",
    "load_mhd1d_csv_profile",
    "load_mhd1d_fixture",
]
