# 3D Wave Equation Solver Description

## Governing Equation

For a scalar field $u(x, y, z, t)$ with wave speed $c$:

```math
\frac{\partial^2 u}{\partial t^2} = c^2
\left(
\frac{\partial^2 u}{\partial x^2} +
\frac{\partial^2 u}{\partial y^2} +
\frac{\partial^2 u}{\partial z^2}
\right).
```

This can be rewritten as a first-order system by introducing $v = \partial u / \partial t$:

```math
\begin{aligned}
\frac{\partial v}{\partial t} &= c^2
\left(
\frac{\partial^2 u}{\partial x^2} +
\frac{\partial^2 u}{\partial y^2} +
\frac{\partial^2 u}{\partial z^2}
\right), \\
\frac{\partial u}{\partial t} &= v.
\end{aligned}
```

## Numerical Method

Use a finite-difference discretization in space and time. Let $u^n_{i,j,k}$ be the value at time index $n$ and grid index $(i, j, k)$.

One leapfrog-style update is:

```math
\begin{aligned}
v_{i,j,k}^{n+1/2} &= v_{i,j,k}^{n-1/2} + c^2 \Delta t
\left(
\frac{u^n_{i+1,j,k} - 2u^n_{i,j,k} + u^n_{i-1,j,k}}{\Delta x^2} +
\frac{u^n_{i,j+1,k} - 2u^n_{i,j,k} + u^n_{i,j-1,k}}{\Delta y^2} +
\frac{u^n_{i,j,k+1} - 2u^n_{i,j,k} + u^n_{i,j,k-1}}{\Delta z^2}
\right), \\
u_{i,j,k}^{n+1} &= u_{i,j,k}^{n} + \Delta t\,v_{i,j,k}^{n+1/2}.
\end{aligned}
```

## Initial Condition

Use centered Gaussian initial displacement with zero initial velocity:

```math
u_0(x,y,z) = \exp\left(-\frac{(x-0.5)^2 + (y-0.5)^2 + (z-0.5)^2}{2\sigma^2}\right),\quad
\sigma = 0.1,
\quad v_0(x,y,z)=0.
```

Use cell-centered grid coordinates:

```math
x_i = \frac{i + 0.5}{n_x},\; y_j = \frac{j + 0.5}{n_y},\; z_k = \frac{k + 0.5}{n_z}
```

## Boundary Conditions

Use periodic boundary conditions in all three spatial dimensions.

## Implementation Notes

- A one-cell ghost layer on both sides of each dimension must be used.
- Given interior sizes `(nx, ny, nz)`, allocate arrays with one ghost cell on
  both sides of each physical dimension:
  - Fortran representation `u(ix, iy, iz)`: `(nx + 2, ny + 2, nz + 2)`
  - C++/Python representation `u(iz, iy, ix)`: `(nz + 2, ny + 2, nx + 2)`
- The boundary condition implementation should update ghost cells.
- Indexing for arrays starts from 0 in C++ and Python, and from 1 in Fortran.
- For loop indices, use `int` in C++, and `integer` in Fortran, unless specified otherwise.
- The physical field is always `u(x, y, z)` with physical indices `(ix, iy, iz)`. Assume always `x` direction is contiguous in memory, then `y`, then `z`. In other words, we have the following mapping between physical indices and array indices:
  - Fortran representation: `u(ix, iy, iz)`
  - C++/Python representation: `u(iz, iy, ix)`
- For C++ implementations, use `mdspan` with default C-style layout (`layout_right`) for multidimensional views.
  - Include `experimental/mdspan` and declare `namespace stdex = std::experimental`, then `stdex::mdspan` is a backport of the C++23 `std::mdspan`.
  - Accessing each element of the mdspan should be done with `operator()`, e.g. `u(iz, iy, ix)`.

## Push API Contract

Tasks expose a one-step kernel named `push_wave_3d` that updates `u` and `v`
in place. Initial condition setup and the loop over `n_steps` are done by the
caller (tests or CLI main program).

## CLI Output Contract (Compiled Tasks)

- When a task uses a CLI executable, print the interior field in the memory layout order (fastest to slowest) after the final time step, with one value per line.

- Output one float per line with enough precision for `1e-12` checks
- Default CLI arguments for this suite are:

  `<dt> <dx> <nx> <ny> <nz> <n_steps>`
