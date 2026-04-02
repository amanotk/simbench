# HLLD Riemann Solver Algorithm

This note documents the HLLD approximate Riemann solver used in this suite.  
It focuses on the implementation formulas and branch structure.

## Wave structure

For left and right states $L$ and $R$, the HLLD fan uses five waves:

```math
S_L,
\qquad
S_L^\ast,
\qquad
S_M,
\qquad
S_R^\ast,
\qquad
S_R.
```

These waves separate four intermediate states:

```math
\mathbf{U}_L^\ast,
\qquad
\mathbf{U}_L^{\ast\ast},
\qquad
\mathbf{U}_R^{\ast\ast},
\qquad
\mathbf{U}_R^\ast.
```

Within the HLLD fan, the normal velocity and total pressure are assumed  
constant:

```math
u^\ast = S_M,
\qquad
p_T^\ast = \text{constant}.
```

## Outer wave speeds

Use the following wave-speed estimate for the outer waves $S_L$ and $S_R$.

```math
S_L=\min(u_L,u_R)-\max(c_{f,L},c_{f,R})
\qquad
S_R=\max(u_L,u_R)+\max(c_{f,L},c_{f,R})
```

This wave-speed estimate is part of the benchmark convention.

## Contact speed and total pressure

The contact-wave speed is

```math
S_M =
\frac{
(S_R-u_R)\rho_R u_R - (S_L-u_L)\rho_L u_L - p_{T,R} + p_{T,L}
}{
(S_R-u_R)\rho_R - (S_L-u_L)\rho_L
}.
```

The common total pressure in the star region is

```math
p_T^\ast
=
p_{T,L} + \rho_L (S_L-u_L)(S_M-u_L)
=
p_{T,R} + \rho_R (S_R-u_R)(S_M-u_R).
```

## Single-star states

For $\alpha \in \{L,R\}$, define

```math
\rho_\alpha^\ast
=
\rho_\alpha
\frac{S_\alpha-u_\alpha}{S_\alpha-S_M}.
```

Also define the denominator

```math
D_\alpha =
\rho_\alpha (S_\alpha-u_\alpha)(S_\alpha-S_M) - B_x^2.
```

Then the transverse velocity components are

```math
v_\alpha^\ast
=
v_\alpha
-
B_x B_{y,\alpha}
\frac{S_M-u_\alpha}{D_\alpha},
```

```math
w_\alpha^\ast
=
w_\alpha
-
B_x B_{z,\alpha}
\frac{S_M-u_\alpha}{D_\alpha},
```

and the transverse magnetic-field components are

```math
B_{y,\alpha}^\ast
=
B_{y,\alpha}
\frac{\rho_\alpha (S_\alpha-u_\alpha)^2 - B_x^2}{D_\alpha},
```

```math
B_{z,\alpha}^\ast
=
B_{z,\alpha}
\frac{\rho_\alpha (S_\alpha-u_\alpha)^2 - B_x^2}{D_\alpha}.
```

The normal momentum in the star state is

```math
m_{x,\alpha}^\ast = \rho_\alpha^\ast S_M,
```

and the transverse momenta are

```math
m_{y,\alpha}^\ast = \rho_\alpha^\ast v_\alpha^\ast,
\qquad
m_{z,\alpha}^\ast = \rho_\alpha^\ast w_\alpha^\ast.
```

The star-region energy is

```math
E_\alpha^\ast
=
\frac{
(S_\alpha-u_\alpha)E_\alpha
- p_{T,\alpha} u_\alpha
+ p_T^\ast S_M
+ B_x\left(
\mathbf{v}_\alpha\cdot\mathbf{B}_\alpha
-
\mathbf{v}_\alpha^\ast\cdot\mathbf{B}_\alpha^\ast
\right)
}{
S_\alpha-S_M
},
```

where

```math
\mathbf{v}_\alpha = (u_\alpha, v_\alpha, w_\alpha),
\qquad
\mathbf{B}_\alpha = (B_x, B_{y,\alpha}, B_{z,\alpha}).
```

For the starred-state dot product in the energy formula, use

```math
\mathbf{v}_\alpha^\ast = (S_M, v_\alpha^\ast, w_\alpha^\ast),
\qquad
\mathbf{B}_\alpha^\ast = (B_x, B_{y,\alpha}^\ast, B_{z,\alpha}^\ast).
```

So the full conservative single-star state is

```math
\mathbf{U}_\alpha^\ast =
\begin{bmatrix}
\rho_\alpha^\ast \\
\rho_\alpha^\ast S_M \\
\rho_\alpha^\ast v_\alpha^\ast \\
\rho_\alpha^\ast w_\alpha^\ast \\
E_\alpha^\ast \\
B_{y,\alpha}^\ast \\
B_{z,\alpha}^\ast
\end{bmatrix}.
```

## Double-star states

The rotational-wave speeds are

```math
S_L^\ast = S_M - \frac{|B_x|}{\sqrt{\rho_L^\ast}},
\qquad
S_R^\ast = S_M + \frac{|B_x|}{\sqrt{\rho_R^\ast}}.
```

The density and normal momentum are unchanged across the rotational waves:

```math
\rho_L^{\ast\ast} = \rho_L^\ast,
\qquad
\rho_R^{\ast\ast} = \rho_R^\ast,
```

```math
m_{x,L}^{\ast\ast} = \rho_L^\ast S_M,
\qquad
m_{x,R}^{\ast\ast} = \rho_R^\ast S_M.
```

The transverse velocity and magnetic field are shared across the contact:

```math
v_L^{\ast\ast} = v_R^{\ast\ast} \equiv v^{\ast\ast},
\qquad
w_L^{\ast\ast} = w_R^{\ast\ast} \equiv w^{\ast\ast},
```

```math
B_{y,L}^{\ast\ast} = B_{y,R}^{\ast\ast} \equiv B_y^{\ast\ast},
\qquad
B_{z,L}^{\ast\ast} = B_{z,R}^{\ast\ast} \equiv B_z^{\ast\ast}.
```

Use

```math
v^{\ast\ast}
=
\frac{
\sqrt{\rho_L^\ast} v_L^\ast
+
\sqrt{\rho_R^\ast} v_R^\ast
+
(B_{y,R}^\ast - B_{y,L}^\ast)\mathrm{sgn}(B_x)
}{
\sqrt{\rho_L^\ast} + \sqrt{\rho_R^\ast}
},
```

```math
w^{\ast\ast}
=
\frac{
\sqrt{\rho_L^\ast} w_L^\ast
+
\sqrt{\rho_R^\ast} w_R^\ast
+
(B_{z,R}^\ast - B_{z,L}^\ast)\mathrm{sgn}(B_x)
}{
\sqrt{\rho_L^\ast} + \sqrt{\rho_R^\ast}
},
```

```math
B_y^{\ast\ast}
=
\frac{
\sqrt{\rho_L^\ast} B_{y,R}^\ast
+
\sqrt{\rho_R^\ast} B_{y,L}^\ast
+
\sqrt{\rho_L^\ast\rho_R^\ast}(v_R^\ast - v_L^\ast)\mathrm{sgn}(B_x)
}{
\sqrt{\rho_L^\ast} + \sqrt{\rho_R^\ast}
},
```

```math
B_z^{\ast\ast}
=
\frac{
\sqrt{\rho_L^\ast} B_{z,R}^\ast
+
\sqrt{\rho_R^\ast} B_{z,L}^\ast
+
\sqrt{\rho_L^\ast\rho_R^\ast}(w_R^\ast - w_L^\ast)\mathrm{sgn}(B_x)
}{
\sqrt{\rho_L^\ast} + \sqrt{\rho_R^\ast}
}.
```

The double-star energies are

```math
E_L^{\ast\ast}
=
E_L^\ast
-
\sqrt{\rho_L^\ast}
\left(
\mathbf{v}_L^\ast\cdot\mathbf{B}_L^\ast
-
\mathbf{v}^{\ast\ast}\cdot\mathbf{B}^{\ast\ast}
\right)\mathrm{sgn}(B_x),
```

```math
E_R^{\ast\ast}
=
E_R^\ast
+
\sqrt{\rho_R^\ast}
\left(
\mathbf{v}_R^\ast\cdot\mathbf{B}_R^\ast
-
\mathbf{v}^{\ast\ast}\cdot\mathbf{B}^{\ast\ast}
\right)\mathrm{sgn}(B_x).
```

Here

```math
\mathbf{v}^{\ast\ast} = (S_M, v^{\ast\ast}, w^{\ast\ast}),
\qquad
\mathbf{B}^{\ast\ast} = (B_x, B_y^{\ast\ast}, B_z^{\ast\ast}).
```

The double-star conservative states are therefore

```math
\mathbf{U}_L^{\ast\ast} =
\begin{bmatrix}
\rho_L^\ast \\
\rho_L^\ast S_M \\
\rho_L^\ast v^{\ast\ast} \\
\rho_L^\ast w^{\ast\ast} \\
E_L^{\ast\ast} \\
B_y^{\ast\ast} \\
B_z^{\ast\ast}
\end{bmatrix},
\qquad
\mathbf{U}_R^{\ast\ast} =
\begin{bmatrix}
\rho_R^\ast \\
\rho_R^\ast S_M \\
\rho_R^\ast v^{\ast\ast} \\
\rho_R^\ast w^{\ast\ast} \\
E_R^{\ast\ast} \\
B_y^{\ast\ast} \\
B_z^{\ast\ast}
\end{bmatrix}.
```

## Fluxes for intermediate states

For any wave speed $S$ and corresponding state $\mathbf{U}$ reached from side  
state $\mathbf{U}_0$ with physical flux $\mathbf{F}_0$, the Rankine-Hugoniot  
flux update is

```math
\mathbf{F} = \mathbf{F}_0 + S(\mathbf{U} - \mathbf{U}_0).
```

In particular,

```math
\mathbf{F}_L^\ast = \mathbf{F}_L + S_L(\mathbf{U}_L^\ast - \mathbf{U}_L),
\qquad
\mathbf{F}_R^\ast = \mathbf{F}_R + S_R(\mathbf{U}_R^\ast - \mathbf{U}_R),
```

```math
\mathbf{F}_L^{\ast\ast} = \mathbf{F}_L^\ast + S_L^\ast(\mathbf{U}_L^{\ast\ast} - \mathbf{U}_L^\ast),
\qquad
\mathbf{F}_R^{\ast\ast} = \mathbf{F}_R^\ast + S_R^\ast(\mathbf{U}_R^{\ast\ast} - \mathbf{U}_R^\ast).
```

## Flux selection

After constructing all intermediate states, choose the interface flux according  
to the location of zero in the wave fan:

```math
\mathbf{F}^\ast =
\begin{cases}
\mathbf{F}_L, & 0 \le S_L, \\
\mathbf{F}_L^\ast, & S_L \le 0 \le S_L^\ast, \\
\mathbf{F}_L^{\ast\ast}, & S_L^\ast \le 0 \le S_M, \\
\mathbf{F}_R^{\ast\ast}, & S_M \le 0 \le S_R^\ast, \\
\mathbf{F}_R^\ast, & S_R^\ast \le 0 \le S_R, \\
\mathbf{F}_R, & S_R \le 0.
\end{cases}
```

All fluxes use the conservative component ordering defined in  
`basic_equations.md`.
