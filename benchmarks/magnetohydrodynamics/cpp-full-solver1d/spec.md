# cpp-full-solver1d

Implement a 1D ideal MHD full solver in C++.

## Task

The benchmark contract is fixed around these choices:

- domain: `[0, 1]`
- initial discontinuity: `x = 0.5`
- conservative evolution
- primitive reconstruction: MC2
- flux function: HLLD
- time integration: SSP-RK3
- boundary conditions: zero-gradient
- input format: TOML
- output format: CSV with columns `x,rho,u,v,w,p,by,bz`
- default problem: Brio-Wu with `gamma = 2` and `Bx = 0.75`

## Numerical method

The solver implements the following numerical scheme:

1. **Reconstruction**: MC2 (minmod with centered differences) for primitive variables
2. **Riemann solver**: HLLD approximate Riemann solver for ideal MHD fluxes
3. **Time integration**: SSP-RK3 (strong stability preserving Runge-Kutta, 3rd order)
4. **Boundary conditions**: Zero-gradient ghost cells (2 cells per side)

### State ordering

Primitive state vector (7 components):
```
[rho, u, v, w, p, By, Bz]
```

Conservative state vector (7 components):
```
[rho, mx, my, mz, E, By, Bz]
```

where `mx = rho * u`, `my = rho * v`, `mz = rho * w`, and total energy
`E = p/(gamma-1) + 0.5*rho*(u^2+v^2+w^2) + 0.5*(Bx^2+By^2+Bz^2)`.

### Default constants

| Parameter | Value |
|-----------|-------|
| `gamma` | 2.0 |
| `Bx` | 0.75 |
| `dt` | 5.0e-4 |
| `t_final` | 0.1 |
| `nx` | 400 |

## Building

```bash
mkdir build && cd build
cmake ..
cmake --build .
```

The solver executable is placed at `build/bin/cpp_full_solver1d`.

## Usage

```bash
./bin/cpp_full_solver1d <input.toml>
```

The solver reads a TOML configuration file and writes CSV output to stdout.

### Example input (Brio-Wu)

```toml
nx = 400
x_left = 0.0
x_right = 1.0
discontinuity_x = 0.5
gamma = 2.0
bx = 0.75
dt = 5.0e-4
t_final = 0.1

[left]
rho = 1.0
u = 0.0
v = 0.0
w = 0.0
p = 1.0
by = 1.0
bz = 0.0

[right]
rho = 0.125
u = 0.0
v = 0.0
w = 0.0
p = 0.1
by = -1.0
bz = 0.0
```

### Running and saving output

```bash
./bin/cpp_full_solver1d examples/brio_wu.toml > solution.csv
```

## Visualization

A plot helper script is provided for quick inspection of results:

```bash
python scripts/plot_solution.py solution.csv
```

This displays profiles for density (`rho`), velocity (`u`), pressure (`p`), and
magnetic field (`by`).

## API reference

### Core functions (`mhd1d.hpp`)

#### `ProblemConfig make_brio_wu_example()`

Returns a `ProblemConfig` pre-configured with the canonical Brio-Wu parameters.

#### `StateVector primitive_to_conservative(const StateVector& primitive, double bx, double gamma)`

Converts a primitive state vector to conservative form.

**Parameters:**
- `primitive`: 7-component primitive state `[rho, u, v, w, p, By, Bz]`
- `bx`: Constant x-component of magnetic field
- `gamma`: Adiabatic index

**Returns:** 7-component conservative state `[rho, mx, my, mz, E, By, Bz]`

#### `StateVector conservative_to_primitive(const StateVector& conservative, double bx, double gamma)`

Converts a conservative state vector to primitive form.

**Parameters:**
- `conservative`: 7-component conservative state
- `bx`: Constant x-component of magnetic field
- `gamma`: Adiabatic index

**Returns:** 7-component primitive state

#### `std::pair<std::vector<StateVector>, std::vector<StateVector>> reconstruct_mc2_interfaces(const std::vector<StateVector>& primitive_cells)`

Performs MC2 slope-limited reconstruction at cell interfaces.

**Parameters:**
- `primitive_cells`: Cell-centered primitive states

**Returns:** Pair of left and right interface states

#### `StateVector hlld_flux_from_primitive(const StateVector& left, const StateVector& right, double bx, double gamma)`

Computes the HLLD numerical flux given left and right primitive states.

**Parameters:**
- `left`: Left primitive state at interface
- `right`: Right primitive state at interface
- `bx`: Constant x-component of magnetic field
- `gamma`: Adiabatic index

**Returns:** Numerical flux vector

#### `std::vector<StateVector> run_full_simulation(const ProblemConfig& problem)`

Runs the complete simulation from initial conditions to `t_final`.

**Parameters:**
- `problem`: Problem configuration with initial states and parameters

**Returns:** Final primitive state profile at `t_final`

#### `std::vector<StateVector> ssp_rk3_step(const std::vector<StateVector>& conservative_cells, double dt, double dx, double bx, double gamma)`

Performs one SSP-RK3 time step.

**Parameters:**
- `conservative_cells`: Current conservative state profile
- `dt`: Time step size
- `dx`: Cell width
- `bx`: Constant x-component of magnetic field
- `gamma`: Adiabatic index

**Returns:** Updated conservative state profile

## Evaluation

The hidden evaluation compares solver output against a reference solution using:

- **Scored variables**: `rho`, `u`, `p`, `by`
- **Comparison window**: Interior cells only (excludes 2 edge-adjacent cells per side)
- **Metrics**: L1 and Linf absolute errors
- **Tolerances**: Defined in `shared/eval/fixtures/mhd1d/brio_wu_fixture.json`
