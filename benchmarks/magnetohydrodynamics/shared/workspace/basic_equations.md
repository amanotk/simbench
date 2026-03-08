# Ideal MHD Equations

Below we summarize the ideal magnetohydrodynamics (MHD) equations in 1D along the x direction.  
The normal magnetic field $B_x$ is constant and can be separated from the 7-component state vectors.  
Multidimensional extensions are straightforward and are not discussed here.

## Units and conventions

We use Lorentz-Heaviside units, so no explicit $4\pi$ or $\mu_0$ factors appear.

## Primitive variables

The primitive-state ordering in this suite is

```math
\mathbf{W} =
\begin{bmatrix}
\rho & u & v & w & p & B_y & B_z
\end{bmatrix}^{\mathsf T}.
```

## Conservative variables

The conservative-state ordering in this suite is

```math
\mathbf{U} =
\begin{bmatrix}
\rho & m_x & m_y & m_z & E & B_y & B_z
\end{bmatrix}^{\mathsf T},
```

where

```math
m_x = \rho u,
\qquad
m_y = \rho v,
\qquad
m_z = \rho w.
```

## Equation of state and derived quantities

We use an ideal-gas equation of state with ratio of specific heats $\gamma$.

The total energy density is

```math
E =
\frac{p}{\gamma - 1}
+ \frac{1}{2}\rho\left(u^2 + v^2 + w^2\right)
+ \frac{1}{2}\left(B_x^2 + B_y^2 + B_z^2\right).
```

Given a conservative state, the gas pressure is recovered as

```math
p =
(\gamma - 1)
\left[
E
- \frac{1}{2}\rho\left(u^2 + v^2 + w^2\right)
- \frac{1}{2}\left(B_x^2 + B_y^2 + B_z^2\right)
\right].
```

The total pressure is

```math
p_T = p + \frac{1}{2}\left(B_x^2 + B_y^2 + B_z^2\right).
```

## Physical flux in the x direction

For the conservative state

```math
\mathbf{U} =
\begin{bmatrix}
\rho & m_x & m_y & m_z & E & B_y & B_z
\end{bmatrix}^{\mathsf T},
```

with

```math
u = \frac{m_x}{\rho},
\qquad
v = \frac{m_y}{\rho},
\qquad
w = \frac{m_z}{\rho},
```

the physical $x$-flux is

```math
\mathbf{F}_x(\mathbf{U}) =
\begin{bmatrix}
\rho u \\
\rho u^2 + p_T - B_x^2 \\
\rho v u - B_x B_y \\
\rho w u - B_x B_z \\
(E + p_T)u - B_x(u B_x + v B_y + w B_z) \\
B_y u - B_x v \\
B_z u - B_x w
\end{bmatrix}.
```

## Fast magnetosonic speed

Define

```math
a^2 = \frac{\gamma p}{\rho},
\qquad
b_x^2 = \frac{B_x^2}{\rho},
\qquad
b_t^2 = \frac{B_y^2 + B_z^2}{\rho},
\qquad
b^2 = b_x^2 + b_t^2.
```

Then the fast magnetosonic speed in the $x$ direction is

```math
c_f^2 =
\frac{1}{2}
\left[
a^2 + b^2 +
\sqrt{\left(a^2 + b^2\right)^2 - 4 a^2 b_x^2}
\right].
```

Use

```math
c_f = \sqrt{c_f^2}.
```
