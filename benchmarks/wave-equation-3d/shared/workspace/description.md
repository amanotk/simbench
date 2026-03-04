# 3D Wave Equation Description

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

## Boundary Conditions

Use periodic boundary conditions in all three spatial dimensions.

For implementation, use a one-cell ghost layer around the interior domain and
copy periodic faces into ghost cells each step.

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

## Implementation Notes

- A standard finite-difference implementation with explicit neighbor indexing
  (or equivalent slice indexing) is preferred.
- Avoid `np.roll`-specific formulations so the same scheme maps directly to
  C++/Fortran implementations.

## Language-specific Array Mapping

The physical field is always `u(x, y, z)` with physical indices `(ix, iy, iz)`.

- Fortran representation: `u(ix, iy, iz)`
- C++/Python representation: `u(iz, iy, ix)`

For C++, use `std::mdspan` with default C-style layout (`layout_right`) for
multidimensional views.

## CLI Output Contract (Compiled Tasks)

When a task uses a CLI executable, print the interior field in **physical
index order**:

1. `ix` outer loop
2. `iy` middle loop
3. `iz` inner loop

Output one float per line with enough precision for `1e-12` checks.

Default CLI arguments for this suite are:

`<dt> <dx> <nx> <ny> <nz> <n_steps>`
