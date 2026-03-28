"""Maintainer-only hidden reference helpers for 1D Brio-Wu MHD."""

from __future__ import annotations

import math
import csv
import json
from pathlib import Path

import numpy as np


STATE_WIDTH = 7
DOMAIN_LEFT = 0.0
DOMAIN_RIGHT = 1.0
DISCONTINUITY_X = 0.5
DEFAULT_GAMMA = 2.0
DEFAULT_BX = 0.75
DEFAULT_GHOST_WIDTH = 2
BRIO_WU_REFERENCE_NX = 400
BRIO_WU_REFERENCE_T_FINAL = 0.1
BRIO_WU_REFERENCE_DT = 5.0e-4
BRIO_WU_REFERENCE_CSV_NAME = "brio_wu_reference.csv"
BRIO_WU_FIXTURE_JSON_NAME = "brio_wu_fixture.json"
BRIO_WU_REFERENCE_HEADER = ("x", "rho", "u", "v", "w", "p", "by", "bz")
BRIO_WU_SCORING_VARIABLES = ("rho", "u", "p", "by")
BRIO_WU_INNER_WINDOW_EXCLUDE = 2

PRIMITIVE_ORDER = ("rho", "u", "v", "w", "p", "By", "Bz")
CONSERVATIVE_ORDER = ("rho", "mx", "my", "mz", "E", "By", "Bz")

BRIO_WU_LEFT_PRIMITIVE = np.array([1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0], dtype=np.float64)
BRIO_WU_RIGHT_PRIMITIVE = np.array(
    [0.125, 0.0, 0.0, 0.0, 0.1, -1.0, 0.0], dtype=np.float64
)


def _require_state_width(state: np.ndarray, *, name: str) -> np.ndarray:
    array = np.asarray(state, dtype=np.float64)
    if array.shape[-1] != STATE_WIDTH:
        raise ValueError(f"{name} must have last dimension {STATE_WIDTH}")
    return array


def _sign_unit(number: float) -> float:
    return 1.0 if number >= 0.0 else -1.0


def primitive_to_conservative(
    primitive_state: np.ndarray,
    bx: float = DEFAULT_BX,
    gamma: float = DEFAULT_GAMMA,
) -> np.ndarray:
    primitive = _require_state_width(primitive_state, name="primitive_state")

    rho = primitive[..., 0]
    u = primitive[..., 1]
    v = primitive[..., 2]
    w = primitive[..., 3]
    pressure = primitive[..., 4]
    by = primitive[..., 5]
    bz = primitive[..., 6]

    conservative = np.empty_like(primitive, dtype=np.float64)
    conservative[..., 0] = rho
    conservative[..., 1] = rho * u
    conservative[..., 2] = rho * v
    conservative[..., 3] = rho * w
    conservative[..., 4] = pressure / (gamma - 1.0) + 0.5 * rho * (
        u * u + v * v + w * w
    )
    conservative[..., 4] += 0.5 * (bx * bx + by * by + bz * bz)
    conservative[..., 5] = by
    conservative[..., 6] = bz
    return conservative


def conservative_to_primitive(
    conservative_state: np.ndarray,
    bx: float = DEFAULT_BX,
    gamma: float = DEFAULT_GAMMA,
) -> np.ndarray:
    conservative = _require_state_width(conservative_state, name="conservative_state")

    rho = conservative[..., 0]
    mx = conservative[..., 1]
    my = conservative[..., 2]
    mz = conservative[..., 3]
    energy = conservative[..., 4]
    by = conservative[..., 5]
    bz = conservative[..., 6]

    u = mx / rho
    v = my / rho
    w = mz / rho
    kinetic_energy = 0.5 * rho * (u * u + v * v + w * w)
    magnetic_energy = 0.5 * (bx * bx + by * by + bz * bz)
    pressure = (gamma - 1.0) * (energy - kinetic_energy - magnetic_energy)

    primitive = np.empty_like(conservative, dtype=np.float64)
    primitive[..., 0] = rho
    primitive[..., 1] = u
    primitive[..., 2] = v
    primitive[..., 3] = w
    primitive[..., 4] = pressure
    primitive[..., 5] = by
    primitive[..., 6] = bz
    return primitive


def cell_centers(
    nx: int,
    x_left: float = DOMAIN_LEFT,
    x_right: float = DOMAIN_RIGHT,
) -> np.ndarray:
    if nx <= 0:
        raise ValueError("nx must be positive")
    if x_right <= x_left:
        raise ValueError("x_right must be greater than x_left")

    dx = (x_right - x_left) / float(nx)
    centers = x_left + (np.arange(nx, dtype=np.float64) + 0.5) * dx
    return centers


def brio_wu_primitive_profile(
    nx: int,
    x_left: float = DOMAIN_LEFT,
    x_right: float = DOMAIN_RIGHT,
    discontinuity_x: float = DISCONTINUITY_X,
) -> np.ndarray:
    centers = cell_centers(nx, x_left=x_left, x_right=x_right)
    primitive_profile = np.empty((nx, STATE_WIDTH), dtype=np.float64)
    left_cells = centers < discontinuity_x
    primitive_profile[left_cells] = BRIO_WU_LEFT_PRIMITIVE
    primitive_profile[~left_cells] = BRIO_WU_RIGHT_PRIMITIVE
    return primitive_profile


def brio_wu_conservative_profile(
    nx: int,
    x_left: float = DOMAIN_LEFT,
    x_right: float = DOMAIN_RIGHT,
    discontinuity_x: float = DISCONTINUITY_X,
    bx: float = DEFAULT_BX,
    gamma: float = DEFAULT_GAMMA,
) -> np.ndarray:
    primitive_profile = brio_wu_primitive_profile(
        nx,
        x_left=x_left,
        x_right=x_right,
        discontinuity_x=discontinuity_x,
    )
    return primitive_to_conservative(primitive_profile, bx=bx, gamma=gamma)


def evolve_brio_wu_reference_profile(
    nx: int = BRIO_WU_REFERENCE_NX,
    t_final: float = BRIO_WU_REFERENCE_T_FINAL,
    dt: float = BRIO_WU_REFERENCE_DT,
    bx: float = DEFAULT_BX,
    gamma: float = DEFAULT_GAMMA,
) -> np.ndarray:
    conservative_profile = brio_wu_conservative_profile(nx, bx=bx, gamma=gamma)
    evolved_conservative = evolve_ssp_rk3_fixed_dt(
        conservative_profile,
        t_final=t_final,
        dt=dt,
        bx=bx,
        gamma=gamma,
    )
    return conservative_to_primitive(evolved_conservative, bx=bx, gamma=gamma)


def write_brio_wu_reference_fixtures(output_directory: str | Path) -> dict[str, Path]:
    output_path = Path(output_directory)
    output_path.mkdir(parents=True, exist_ok=True)

    reference_profile = evolve_brio_wu_reference_profile()
    center_positions = cell_centers(reference_profile.shape[0])

    csv_path = output_path / BRIO_WU_REFERENCE_CSV_NAME
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(BRIO_WU_REFERENCE_HEADER)
        for position, primitive_state in zip(
            center_positions, reference_profile, strict=True
        ):
            writer.writerow(
                [
                    f"{float(position):.17g}",
                    f"{float(primitive_state[0]):.17g}",
                    f"{float(primitive_state[1]):.17g}",
                    f"{float(primitive_state[2]):.17g}",
                    f"{float(primitive_state[3]):.17g}",
                    f"{float(primitive_state[4]):.17g}",
                    f"{float(primitive_state[5]):.17g}",
                    f"{float(primitive_state[6]):.17g}",
                ]
            )

    tolerance_template = {variable: 0.0 for variable in BRIO_WU_SCORING_VARIABLES}
    metadata = {
        "name": "brio_wu",
        "domain": [DOMAIN_LEFT, DOMAIN_RIGHT],
        "discontinuity_x": DISCONTINUITY_X,
        "gamma": DEFAULT_GAMMA,
        "bx": DEFAULT_BX,
        "nx": reference_profile.shape[0],
        "t_final": BRIO_WU_REFERENCE_T_FINAL,
        "dt": BRIO_WU_REFERENCE_DT,
        "schema": list(BRIO_WU_REFERENCE_HEADER),
        "scored_variables": list(BRIO_WU_SCORING_VARIABLES),
        "interior_cell_window": {
            "exclude_edge_adjacents_per_side": BRIO_WU_INNER_WINDOW_EXCLUDE,
        },
        "abs_l1": tolerance_template,
        "abs_linf": tolerance_template.copy(),
        "reference_csv": BRIO_WU_REFERENCE_CSV_NAME,
    }

    json_path = output_path / BRIO_WU_FIXTURE_JSON_NAME
    with json_path.open("w", encoding="utf-8") as json_file:
        json.dump(metadata, json_file, indent=2, sort_keys=True)
        json_file.write("\n")

    return {"csv": csv_path, "json": json_path}


def fill_zero_gradient_ghost_cells(
    cell_state: np.ndarray,
    ghost_width: int = DEFAULT_GHOST_WIDTH,
) -> np.ndarray:
    if ghost_width < 0:
        raise ValueError("ghost_width must be non-negative")

    interior_state = _require_state_width(cell_state, name="cell_state")
    if interior_state.ndim != 2:
        raise ValueError("cell_state must be a 2D array with shape (nx, 7)")
    if interior_state.shape[0] == 0:
        raise ValueError("cell_state must contain at least one cell")

    padded_width = interior_state.shape[0] + 2 * ghost_width
    padded_state = np.empty((padded_width, STATE_WIDTH), dtype=np.float64)
    padded_state[ghost_width : ghost_width + interior_state.shape[0]] = interior_state
    padded_state[:ghost_width] = interior_state[0]
    padded_state[ghost_width + interior_state.shape[0] :] = interior_state[-1]
    return padded_state


def _minmod3(
    first_slope: np.ndarray, second_slope: np.ndarray, third_slope: np.ndarray
) -> np.ndarray:
    same_sign = (first_slope * second_slope > 0.0) & (first_slope * third_slope > 0.0)
    limited = np.sign(first_slope) * np.minimum(
        np.minimum(np.abs(first_slope), np.abs(second_slope)), np.abs(third_slope)
    )
    return np.where(same_sign, limited, 0.0)


def mc2_slopes(primitive_cells: np.ndarray) -> np.ndarray:
    primitive = _require_state_width(primitive_cells, name="primitive_cells")
    if primitive.ndim != 2:
        raise ValueError("primitive_cells must be a 2D array with shape (n, 7)")
    if primitive.shape[0] < 3:
        raise ValueError("primitive_cells must contain at least three cells")

    slopes = np.zeros_like(primitive, dtype=np.float64)
    left_difference = primitive[1:-1] - primitive[:-2]
    right_difference = primitive[2:] - primitive[1:-1]
    centered_difference = 0.5 * (primitive[2:] - primitive[:-2])
    slopes[1:-1] = _minmod3(
        2.0 * left_difference,
        centered_difference,
        2.0 * right_difference,
    )
    return slopes


def reconstruct_mc2_interfaces(
    primitive_cells: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    primitive = _require_state_width(primitive_cells, name="primitive_cells")
    if primitive.ndim != 2:
        raise ValueError("primitive_cells must be a 2D array with shape (n, 7)")

    slopes = mc2_slopes(primitive)
    left_states = primitive[:-1] + 0.5 * slopes[:-1]
    right_states = primitive[1:] - 0.5 * slopes[1:]
    return left_states, right_states


def _physical_flux_from_primitive(
    primitive_state: np.ndarray,
    bx: float,
    gamma: float,
) -> np.ndarray:
    density = float(primitive_state[0])
    velocity_x = float(primitive_state[1])
    velocity_y = float(primitive_state[2])
    velocity_z = float(primitive_state[3])
    pressure = float(primitive_state[4])
    by = float(primitive_state[5])
    bz = float(primitive_state[6])

    magnetic_pressure = 0.5 * (bx * bx + by * by + bz * bz)
    total_pressure = pressure + magnetic_pressure

    momentum_x = density * velocity_x
    momentum_y = density * velocity_y
    momentum_z = density * velocity_z
    energy = pressure / (gamma - 1.0)
    energy += 0.5 * (
        momentum_x * velocity_x + momentum_y * velocity_y + momentum_z * velocity_z
    )
    energy += magnetic_pressure

    return np.array(
        [
            momentum_x,
            momentum_x * velocity_x + total_pressure - bx * bx,
            momentum_x * velocity_y - bx * by,
            momentum_x * velocity_z - bx * bz,
            velocity_x * (energy + total_pressure - bx * bx)
            - bx * (velocity_y * by + velocity_z * bz),
            by * velocity_x - bx * velocity_y,
            bz * velocity_x - bx * velocity_z,
        ],
        dtype=np.float64,
    )


def _fast_magnetosonic_speed(
    density: float,
    pressure: float,
    by: float,
    bz: float,
    bx: float,
    gamma: float,
) -> float:
    magnetic_pressure = 0.5 * (bx * bx + by * by + bz * bz)
    gamma_pressure = gamma * pressure
    gamma_plus_magnetic = gamma_pressure + 2.0 * magnetic_pressure
    discriminant = math.sqrt(
        (gamma_pressure - 2.0 * magnetic_pressure)
        * (gamma_pressure - 2.0 * magnetic_pressure)
        + 4.0 * gamma_pressure * (by * by + bz * bz)
    )
    return math.sqrt((gamma_plus_magnetic + discriminant) * 0.5 / density)


def hlld_flux_from_primitive(
    left_state: np.ndarray,
    right_state: np.ndarray,
    bx: float = DEFAULT_BX,
    gamma: float = DEFAULT_GAMMA,
) -> np.ndarray:
    left = _require_state_width(left_state, name="left_state")
    right = _require_state_width(right_state, name="right_state")
    if left.ndim != 1 or right.ndim != 1:
        raise ValueError(
            "left_state and right_state must be one-dimensional state vectors"
        )

    density_left = float(left[0])
    velocity_x_left = float(left[1])
    velocity_y_left = float(left[2])
    velocity_z_left = float(left[3])
    pressure_left = float(left[4])
    by_left = float(left[5])
    bz_left = float(left[6])

    density_right = float(right[0])
    velocity_x_right = float(right[1])
    velocity_y_right = float(right[2])
    velocity_z_right = float(right[3])
    pressure_right = float(right[4])
    by_right = float(right[5])
    bz_right = float(right[6])

    inverse_gamma_minus_one = 1.0 / (gamma - 1.0)
    bx_square = bx * bx

    magnetic_pressure_left = 0.5 * (bx_square + by_left * by_left + bz_left * bz_left)
    magnetic_pressure_right = 0.5 * (
        bx_square + by_right * by_right + bz_right * bz_right
    )
    total_pressure_left = pressure_left + magnetic_pressure_left
    total_pressure_right = pressure_right + magnetic_pressure_right

    momentum_x_left = density_left * velocity_x_left
    momentum_y_left = density_left * velocity_y_left
    momentum_z_left = density_left * velocity_z_left
    momentum_x_right = density_right * velocity_x_right
    momentum_y_right = density_right * velocity_y_right
    momentum_z_right = density_right * velocity_z_right

    energy_left = (
        pressure_left * inverse_gamma_minus_one
        + 0.5
        * (
            momentum_x_left * velocity_x_left
            + momentum_y_left * velocity_y_left
            + momentum_z_left * velocity_z_left
        )
        + magnetic_pressure_left
    )
    energy_right = (
        pressure_right * inverse_gamma_minus_one
        + 0.5
        * (
            momentum_x_right * velocity_x_right
            + momentum_y_right * velocity_y_right
            + momentum_z_right * velocity_z_right
        )
        + magnetic_pressure_right
    )

    left_fast_speed = _fast_magnetosonic_speed(
        density_left,
        pressure_left,
        by_left,
        bz_left,
        bx,
        gamma,
    )
    right_fast_speed = _fast_magnetosonic_speed(
        density_right,
        pressure_right,
        by_right,
        bz_right,
        bx,
        gamma,
    )

    outer_left_speed = min(velocity_x_left, velocity_x_right) - max(
        left_fast_speed, right_fast_speed
    )
    outer_right_speed = max(velocity_x_left, velocity_x_right) + max(
        left_fast_speed, right_fast_speed
    )

    left_flux = _physical_flux_from_primitive(left, bx=bx, gamma=gamma)
    right_flux = _physical_flux_from_primitive(right, bx=bx, gamma=gamma)

    left_speed_gap = outer_left_speed - velocity_x_left
    right_speed_gap = outer_right_speed - velocity_x_right
    left_speed_factor = density_left * left_speed_gap
    right_speed_factor = density_right * right_speed_gap
    denominator = right_speed_factor - left_speed_factor
    contact_speed = (
        right_speed_factor * velocity_x_right
        - left_speed_factor * velocity_x_left
        - total_pressure_right
        + total_pressure_left
    ) / denominator
    left_contact_gap = outer_left_speed - contact_speed
    right_contact_gap = outer_right_speed - contact_speed
    star_total_pressure = (
        right_speed_factor * total_pressure_left
        - left_speed_factor * total_pressure_right
        + left_speed_factor * right_speed_factor * (velocity_x_right - velocity_x_left)
    ) / denominator

    def build_star_state(
        density: float,
        velocity_x: float,
        velocity_y: float,
        velocity_z: float,
        by: float,
        bz: float,
        total_pressure: float,
        energy: float,
        speed_gap: float,
        contact_gap: float,
    ) -> tuple[np.ndarray, float, float, float]:
        epsilon = 1.0e-40

        gap_times_density = density * speed_gap
        raw_transverse_denom = gap_times_density * contact_gap - bx_square
        denominator_sign = _sign_unit(abs(raw_transverse_denom) - epsilon)
        positive_branch = max(0.0, denominator_sign)
        negative_branch = min(0.0, denominator_sign)
        inverse_transverse_denom = 1.0 / (raw_transverse_denom + negative_branch)
        inverse_contact_gap = 1.0 / contact_gap

        transverse_velocity_scale = (
            bx * (speed_gap - contact_gap) * inverse_transverse_denom
        )
        density_star = (
            positive_branch * (gap_times_density * inverse_contact_gap)
            - negative_branch * density
        )
        velocity_x_star = positive_branch * contact_speed - negative_branch * velocity_x
        momentum_x_star = density_star * velocity_x_star
        velocity_y_star = (
            positive_branch * (velocity_y - by * transverse_velocity_scale)
            - negative_branch * velocity_y
        )
        momentum_y_star = density_star * velocity_y_star
        velocity_z_star = (
            positive_branch * (velocity_z - bz * transverse_velocity_scale)
            - negative_branch * velocity_z
        )
        momentum_z_star = density_star * velocity_z_star
        by_scale = (
            gap_times_density * speed_gap - bx_square
        ) * inverse_transverse_denom
        by_star = positive_branch * (by * by_scale) - negative_branch * by
        bz_star = positive_branch * (bz * by_scale) - negative_branch * bz
        velocity_dot_b_star = (
            velocity_x_star * bx + velocity_y_star * by_star + velocity_z_star * bz_star
        )
        velocity_dot_b_original = velocity_x * bx + velocity_y * by + velocity_z * bz
        starred_energy = (
            positive_branch
            * (
                (
                    speed_gap * energy
                    - total_pressure * velocity_x
                    + star_total_pressure * contact_speed
                    + bx * (velocity_dot_b_original - velocity_dot_b_star)
                )
                * inverse_contact_gap
            )
            - negative_branch * energy
        )
        star_state = np.array(
            [
                density_star,
                momentum_x_star,
                momentum_y_star,
                momentum_z_star,
                starred_energy,
                by_star,
                bz_star,
            ],
            dtype=np.float64,
        )
        return star_state, density_star, by_star, bz_star

    left_star_state, left_star_density, left_star_by, left_star_bz = build_star_state(
        density_left,
        velocity_x_left,
        velocity_y_left,
        velocity_z_left,
        by_left,
        bz_left,
        total_pressure_left,
        energy_left,
        left_speed_gap,
        left_contact_gap,
    )
    right_star_state, right_star_density, right_star_by, right_star_bz = (
        build_star_state(
            density_right,
            velocity_x_right,
            velocity_y_right,
            velocity_z_right,
            by_right,
            bz_right,
            total_pressure_right,
            energy_right,
            right_speed_gap,
            right_contact_gap,
        )
    )

    left_star_velocity = left_star_state[1] / left_star_density
    left_star_transverse_velocity_y = left_star_state[2] / left_star_density
    left_star_transverse_velocity_z = left_star_state[3] / left_star_density
    right_star_velocity = right_star_state[1] / right_star_density
    right_star_transverse_velocity_y = right_star_state[2] / right_star_density
    right_star_transverse_velocity_z = right_star_state[3] / right_star_density

    left_star_speed = contact_speed - abs(bx) / math.sqrt(left_star_density)
    right_star_speed = contact_speed + abs(bx) / math.sqrt(right_star_density)
    bx_sign = _sign_unit(bx)
    bx_branch = _sign_unit(abs(bx) - 1.0e-40)
    use_rotational_branch = max(0.0, bx_branch)
    inverse_density_sum = use_rotational_branch / (
        math.sqrt(left_star_density) + math.sqrt(right_star_density)
    )

    shared_transverse_velocity_y = inverse_density_sum * (
        math.sqrt(left_star_density) * left_star_transverse_velocity_y
        + math.sqrt(right_star_density) * right_star_transverse_velocity_y
        + bx_sign * (right_star_by - left_star_by)
    )
    shared_transverse_velocity_z = inverse_density_sum * (
        math.sqrt(left_star_density) * left_star_transverse_velocity_z
        + math.sqrt(right_star_density) * right_star_transverse_velocity_z
        + bx_sign * (right_star_bz - left_star_bz)
    )
    shared_by = inverse_density_sum * (
        math.sqrt(left_star_density) * right_star_by
        + math.sqrt(right_star_density) * left_star_by
        + bx_sign
        * math.sqrt(left_star_density)
        * math.sqrt(right_star_density)
        * (right_star_transverse_velocity_y - left_star_transverse_velocity_y)
    )
    shared_bz = inverse_density_sum * (
        math.sqrt(left_star_density) * right_star_bz
        + math.sqrt(right_star_density) * left_star_bz
        + bx_sign
        * math.sqrt(left_star_density)
        * math.sqrt(right_star_density)
        * (right_star_transverse_velocity_z - left_star_transverse_velocity_z)
    )

    left_double_star_state = np.array(
        [
            left_star_density,
            left_star_density * contact_speed,
            left_star_density * shared_transverse_velocity_y,
            left_star_density * shared_transverse_velocity_z,
            left_star_state[4]
            - math.sqrt(left_star_density)
            * bx_sign
            * (
                left_star_velocity * bx
                + left_star_transverse_velocity_y * left_star_by
                + left_star_transverse_velocity_z * left_star_bz
                - (
                    contact_speed * bx
                    + shared_transverse_velocity_y * shared_by
                    + shared_transverse_velocity_z * shared_bz
                )
            )
            * use_rotational_branch,
            shared_by,
            shared_bz,
        ],
        dtype=np.float64,
    )
    right_double_star_state = np.array(
        [
            right_star_density,
            right_star_density * contact_speed,
            right_star_density * shared_transverse_velocity_y,
            right_star_density * shared_transverse_velocity_z,
            right_star_state[4]
            + math.sqrt(right_star_density)
            * bx_sign
            * (
                right_star_velocity * bx
                + right_star_transverse_velocity_y * right_star_by
                + right_star_transverse_velocity_z * right_star_bz
                - (
                    contact_speed * bx
                    + shared_transverse_velocity_y * shared_by
                    + shared_transverse_velocity_z * shared_bz
                )
            )
            * use_rotational_branch,
            shared_by,
            shared_bz,
        ],
        dtype=np.float64,
    )

    left_state_conservative = np.array(
        [
            density_left,
            momentum_x_left,
            momentum_y_left,
            momentum_z_left,
            energy_left,
            by_left,
            bz_left,
        ],
        dtype=np.float64,
    )
    right_state_conservative = np.array(
        [
            density_right,
            momentum_x_right,
            momentum_y_right,
            momentum_z_right,
            energy_right,
            by_right,
            bz_right,
        ],
        dtype=np.float64,
    )
    left_star_flux = left_flux + outer_left_speed * (
        left_star_state - left_state_conservative
    )
    right_star_flux = right_flux + outer_right_speed * (
        right_star_state - right_state_conservative
    )
    left_double_star_flux = left_star_flux + left_star_speed * (
        left_double_star_state - left_star_state
    )
    right_double_star_flux = right_star_flux + right_star_speed * (
        right_double_star_state - right_star_state
    )

    left_wave_branch = outer_left_speed <= 0.0 <= left_star_speed
    left_double_star_branch = left_star_speed <= 0.0 <= contact_speed
    right_double_star_branch = contact_speed <= 0.0 <= right_star_speed
    right_wave_branch = right_star_speed <= 0.0 <= outer_right_speed

    if 0.0 <= outer_left_speed:
        return left_flux
    if left_wave_branch:
        return left_star_flux
    if left_double_star_branch:
        return left_double_star_flux
    if right_double_star_branch:
        return right_double_star_flux
    if right_wave_branch:
        return right_star_flux
    return right_flux


def hlld_flux_from_conservative(
    left_state: np.ndarray,
    right_state: np.ndarray,
    bx: float = DEFAULT_BX,
    gamma: float = DEFAULT_GAMMA,
) -> np.ndarray:
    left_primitive = conservative_to_primitive(left_state, bx=bx, gamma=gamma)
    right_primitive = conservative_to_primitive(right_state, bx=bx, gamma=gamma)
    return hlld_flux_from_primitive(left_primitive, right_primitive, bx=bx, gamma=gamma)


def compute_semidiscrete_rhs(
    conservative_cells: np.ndarray,
    dx: float | None = None,
    bx: float = DEFAULT_BX,
    gamma: float = DEFAULT_GAMMA,
    ghost_width: int = DEFAULT_GHOST_WIDTH,
) -> np.ndarray:
    if ghost_width < 2:
        raise ValueError("ghost_width must be at least 2 for MC2 reconstruction")

    interior_conservative = _require_state_width(
        conservative_cells, name="conservative_cells"
    )
    if interior_conservative.ndim != 2:
        raise ValueError("conservative_cells must be a 2D array with shape (nx, 7)")
    if interior_conservative.shape[0] == 0:
        raise ValueError("conservative_cells must contain at least one cell")

    if dx is None:
        dx = (DOMAIN_RIGHT - DOMAIN_LEFT) / float(interior_conservative.shape[0])
    if dx <= 0.0:
        raise ValueError("dx must be positive")

    padded_conservative = fill_zero_gradient_ghost_cells(
        interior_conservative,
        ghost_width=ghost_width,
    )
    padded_primitive = conservative_to_primitive(
        padded_conservative, bx=bx, gamma=gamma
    )
    left_interface_states, right_interface_states = reconstruct_mc2_interfaces(
        padded_primitive
    )

    interface_fluxes = np.empty_like(left_interface_states)
    for interface_index in range(interface_fluxes.shape[0]):
        interface_fluxes[interface_index] = hlld_flux_from_primitive(
            left_interface_states[interface_index],
            right_interface_states[interface_index],
            bx=bx,
            gamma=gamma,
        )

    cell_count = interior_conservative.shape[0]
    rhs = (
        -(
            interface_fluxes[ghost_width : ghost_width + cell_count]
            - interface_fluxes[ghost_width - 1 : ghost_width - 1 + cell_count]
        )
        / dx
    )
    return rhs


def brio_wu_semidiscrete_rhs(
    nx: int,
    bx: float = DEFAULT_BX,
    gamma: float = DEFAULT_GAMMA,
) -> np.ndarray:
    conservative_profile = brio_wu_conservative_profile(nx, bx=bx, gamma=gamma)
    dx = (DOMAIN_RIGHT - DOMAIN_LEFT) / float(nx)
    return compute_semidiscrete_rhs(conservative_profile, dx=dx, bx=bx, gamma=gamma)


def ssp_rk3_step(
    conservative_cells: np.ndarray,
    dt: float,
    dx: float | None = None,
    bx: float = DEFAULT_BX,
    gamma: float = DEFAULT_GAMMA,
    ghost_width: int = DEFAULT_GHOST_WIDTH,
) -> np.ndarray:
    interior_conservative = _require_state_width(
        conservative_cells, name="conservative_cells"
    )
    if interior_conservative.ndim != 2:
        raise ValueError("conservative_cells must be a 2D array with shape (nx, 7)")
    if interior_conservative.shape[0] == 0:
        raise ValueError("conservative_cells must contain at least one cell")
    if dt <= 0.0:
        raise ValueError("dt must be positive")

    first_rhs = compute_semidiscrete_rhs(
        interior_conservative,
        dx=dx,
        bx=bx,
        gamma=gamma,
        ghost_width=ghost_width,
    )
    first_stage = interior_conservative + dt * first_rhs

    second_rhs = compute_semidiscrete_rhs(
        first_stage,
        dx=dx,
        bx=bx,
        gamma=gamma,
        ghost_width=ghost_width,
    )
    second_stage = 0.75 * interior_conservative + 0.25 * (first_stage + dt * second_rhs)

    third_rhs = compute_semidiscrete_rhs(
        second_stage,
        dx=dx,
        bx=bx,
        gamma=gamma,
        ghost_width=ghost_width,
    )
    next_state = (1.0 / 3.0) * interior_conservative + (2.0 / 3.0) * (
        second_stage + dt * third_rhs
    )
    return next_state


def evolve_ssp_rk3_fixed_dt(
    conservative_cells: np.ndarray,
    t_final: float,
    dt: float,
    dx: float | None = None,
    bx: float = DEFAULT_BX,
    gamma: float = DEFAULT_GAMMA,
    ghost_width: int = DEFAULT_GHOST_WIDTH,
) -> np.ndarray:
    interior_conservative = _require_state_width(
        conservative_cells, name="conservative_cells"
    )
    if interior_conservative.ndim != 2:
        raise ValueError("conservative_cells must be a 2D array with shape (nx, 7)")
    if interior_conservative.shape[0] == 0:
        raise ValueError("conservative_cells must contain at least one cell")
    if t_final < 0.0:
        raise ValueError("t_final must be non-negative")
    if dt <= 0.0:
        raise ValueError("dt must be positive")

    evolved_state = np.array(interior_conservative, dtype=np.float64, copy=True)
    elapsed_time = 0.0
    while elapsed_time < t_final:
        remaining_time = t_final - elapsed_time
        step_dt = min(dt, remaining_time)
        evolved_state = ssp_rk3_step(
            evolved_state,
            step_dt,
            dx=dx,
            bx=bx,
            gamma=gamma,
            ghost_width=ghost_width,
        )
        elapsed_time = t_final if step_dt < dt else elapsed_time + step_dt
    return evolved_state
