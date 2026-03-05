#!/usr/bin/env python3

from __future__ import annotations

import argparse

import numpy as np


def set_boundary_condition_numpy(
    uv: np.ndarray, lbx: int, ubx: int, lby: int, uby: int, lbz: int, ubz: int
) -> None:
    uv[lbx - 1, lby : uby + 1, lbz : ubz + 1] = uv[ubx, lby : uby + 1, lbz : ubz + 1]
    uv[ubx + 1, lby : uby + 1, lbz : ubz + 1] = uv[lbx, lby : uby + 1, lbz : ubz + 1]
    uv[lbx : ubx + 1, lby - 1, lbz : ubz + 1] = uv[lbx : ubx + 1, uby, lbz : ubz + 1]
    uv[lbx : ubx + 1, uby + 1, lbz : ubz + 1] = uv[lbx : ubx + 1, lby, lbz : ubz + 1]
    uv[lbx : ubx + 1, lby : uby + 1, lbz - 1] = uv[lbx : ubx + 1, lby : uby + 1, ubz]
    uv[lbx : ubx + 1, lby : uby + 1, ubz + 1] = uv[lbx : ubx + 1, lby : uby + 1, lbz]


def set_initial_condition(
    u: np.ndarray,
    v: np.ndarray,
    lbx: int,
    ubx: int,
    lby: int,
    uby: int,
    lbz: int,
    ubz: int,
    sigma: float,
) -> None:
    nx = ubx - lbx + 1
    ny = uby - lby + 1
    nz = ubz - lbz + 1
    x = (np.arange(nx, dtype=np.float64) + 0.5) / float(nx)
    y = (np.arange(ny, dtype=np.float64) + 0.5) / float(ny)
    z = (np.arange(nz, dtype=np.float64) + 0.5) / float(nz)
    xx, yy, zz = np.meshgrid(x, y, z, indexing="ij")
    w = 0.5 * ((xx - 0.5) ** 2 + (yy - 0.5) ** 2 + (zz - 0.5) ** 2) / (sigma * sigma)

    ixc = slice(lbx, ubx + 1)
    iyc = slice(lby, uby + 1)
    izc = slice(lbz, ubz + 1)
    u[ixc, iyc, izc] = np.exp(-w)
    v[ixc, iyc, izc] = 0.0

    set_boundary_condition_numpy(u, lbx, ubx, lby, uby, lbz, ubz)
    set_boundary_condition_numpy(v, lbx, ubx, lby, uby, lbz, ubz)


def push_numpy_slice(
    u: np.ndarray,
    v: np.ndarray,
    lbx: int,
    ubx: int,
    lby: int,
    uby: int,
    lbz: int,
    ubz: int,
    dt: float,
    dx: float,
    dy: float,
    dz: float,
    c: float,
) -> None:
    ixp = slice(lbx + 1, ubx + 2)
    ixc = slice(lbx + 0, ubx + 1)
    ixm = slice(lbx - 1, ubx + 0)
    iyp = slice(lby + 1, uby + 2)
    iyc = slice(lby + 0, uby + 1)
    iym = slice(lby - 1, uby + 0)
    izp = slice(lbz + 1, ubz + 2)
    izc = slice(lbz + 0, ubz + 1)
    izm = slice(lbz - 1, ubz + 0)
    c2 = c * c

    v[ixc, iyc, izc] += (
        c2
        * dt
        * (
            (u[ixp, iyc, izc] - 2.0 * u[ixc, iyc, izc] + u[ixm, iyc, izc]) / (dx * dx)
            + (u[ixc, iyp, izc] - 2.0 * u[ixc, iyc, izc] + u[ixc, iym, izc]) / (dy * dy)
            + (u[ixc, iyc, izp] - 2.0 * u[ixc, iyc, izc] + u[ixc, iyc, izm]) / (dz * dz)
        )
    )

    u[ixc, iyc, izc] += dt * v[ixc, iyc, izc]
    set_boundary_condition_numpy(u, lbx, ubx, lby, uby, lbz, ubz)


def push_wave_3d(
    u: np.ndarray,
    v: np.ndarray,
    dt: float,
    dx: float,
    nx: int,
    ny: int,
    nz: int,
    c: float = 1.0,
) -> None:
    if min(nx, ny, nz) <= 0:
        raise ValueError("grid sizes must be positive")
    if dx <= 0.0 or dt < 0.0:
        raise ValueError("dx must be positive and dt must be non-negative")
    if u.shape != (nx + 2, ny + 2, nz + 2):
        raise ValueError("u must have shape (nx+2, ny+2, nz+2)")
    if v.shape != (nx + 2, ny + 2, nz + 2):
        raise ValueError("v must have shape (nx+2, ny+2, nz+2)")

    nb = 1
    lbx = nb
    ubx = nx + nb - 1
    lby = nb
    uby = ny + nb - 1
    lbz = nb
    ubz = nz + nb - 1

    push_numpy_slice(u, v, lbx, ubx, lby, uby, lbz, ubz, dt, dx, dx, dx, c)


def run_simulation(
    dt: float,
    dx: float,
    nx: int,
    ny: int,
    nz: int,
    n_steps: int,
    c: float = 1.0,
    sigma: float = 0.1,
) -> np.ndarray:
    if n_steps < 0:
        raise ValueError("n_steps must be non-negative")

    u = np.zeros((nx + 2, ny + 2, nz + 2), dtype=np.float64)
    v = np.zeros_like(u)
    set_initial_condition(u, v, 1, nx, 1, ny, 1, nz, sigma=sigma)
    for _ in range(n_steps):
        push_wave_3d(u, v, dt, dx, nx, ny, nz, c=c)
    return u[1 : nx + 1, 1 : ny + 1, 1 : nz + 1].copy()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="3D wave equation finite-difference reference solver"
    )
    parser.add_argument("--dt", type=float, default=0.05, help="Time step")
    parser.add_argument("--dx", type=float, default=0.25, help="Grid spacing")
    parser.add_argument("--nx", type=int, default=4, help="Grid size in x")
    parser.add_argument("--ny", type=int, default=4, help="Grid size in y")
    parser.add_argument("--nz", type=int, default=4, help="Grid size in z")
    parser.add_argument("--n-steps", type=int, default=3, help="Number of time steps")
    args = parser.parse_args()

    u = run_simulation(args.dt, args.dx, args.nx, args.ny, args.nz, args.n_steps)
    print(f"shape={u.shape}")
    print(f"mean={float(np.mean(u)):.16e}")
    print(f"l2={float(np.sqrt(np.mean(u * u))):.16e}")
    print(f"max_abs={float(np.max(np.abs(u))):.16e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
