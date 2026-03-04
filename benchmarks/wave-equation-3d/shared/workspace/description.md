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
