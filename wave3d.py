#!/usr/bin/env python3

from __future__ import annotations

import argparse

import numpy as np


def gaussian_initial_condition(
    nx: int, ny: int, nz: int, sigma: float = 0.1
) -> np.ndarray:
    x = (np.arange(nx, dtype=np.float64) + 0.5) / float(nx)
    y = (np.arange(ny, dtype=np.float64) + 0.5) / float(ny)
    z = (np.arange(nz, dtype=np.float64) + 0.5) / float(nz)
    xx, yy, zz = np.meshgrid(x, y, z, indexing="ij")
    r2 = (xx - 0.5) ** 2 + (yy - 0.5) ** 2 + (zz - 0.5) ** 2
    return np.exp(-0.5 * r2 / (sigma * sigma))


def laplacian_periodic(u: np.ndarray, dx: float) -> np.ndarray:
    inv_dx2 = 1.0 / (dx * dx)
    return (
        (np.roll(u, -1, axis=0) - 2.0 * u + np.roll(u, 1, axis=0)) * inv_dx2
        + (np.roll(u, -1, axis=1) - 2.0 * u + np.roll(u, 1, axis=1)) * inv_dx2
        + (np.roll(u, -1, axis=2) - 2.0 * u + np.roll(u, 1, axis=2)) * inv_dx2
    )


def simulate_wave_3d(
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
    if min(nx, ny, nz) <= 0:
        raise ValueError("grid sizes must be positive")
    if dx <= 0.0 or dt < 0.0:
        raise ValueError("dx must be positive and dt must be non-negative")

    u = gaussian_initial_condition(nx, ny, nz, sigma=sigma)
    v = np.zeros_like(u)
    c2 = c * c

    for _ in range(n_steps):
        v = v + dt * c2 * laplacian_periodic(u, dx)
        u = u + dt * v

    return u


def main() -> int:
    parser = argparse.ArgumentParser(
        description="3D wave equation finite-difference solver"
    )
    parser.add_argument("--dt", type=float, default=0.05, help="Time step")
    parser.add_argument("--dx", type=float, default=0.25, help="Grid spacing")
    parser.add_argument("--nx", type=int, default=4, help="Grid size in x")
    parser.add_argument("--ny", type=int, default=4, help="Grid size in y")
    parser.add_argument("--nz", type=int, default=4, help="Grid size in z")
    parser.add_argument("--n-steps", type=int, default=3, help="Number of time steps")
    args = parser.parse_args()

    u = simulate_wave_3d(args.dt, args.dx, args.nx, args.ny, args.nz, args.n_steps)
    print(f"shape={u.shape}")
    print(f"mean={float(np.mean(u)):.16e}")
    print(f"l2={float(np.sqrt(np.mean(u * u))):.16e}")
    print(f"max_abs={float(np.max(np.abs(u))):.16e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
