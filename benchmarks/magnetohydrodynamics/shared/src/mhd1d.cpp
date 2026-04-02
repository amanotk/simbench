#include "mhd1d.hpp"
#include "hlld.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace mhd1d
{

double sign(const double x)
{
  return copysign(1.0, x);
}

double mc2(double a, double b)
{
  return 0.5 * (sign(a) + sign(b)) *
         std::min({2.0 * std::abs(a), 2.0 * std::abs(b), 0.5 * std::abs(a + b)});
}

void primitive_to_conservative(const double* primitive, double* conservative, double bx,
                               double gamma)
{
  const double rho      = primitive[0];
  const double u        = primitive[1];
  const double v        = primitive[2];
  const double w        = primitive[3];
  const double pressure = primitive[4];
  const double by       = primitive[5];
  const double bz       = primitive[6];

  const double kinetic_energy  = 0.5 * rho * (u * u + v * v + w * w);
  const double magnetic_energy = 0.5 * (bx * bx + by * by + bz * bz);

  conservative[0] = rho;
  conservative[1] = rho * u;
  conservative[2] = rho * v;
  conservative[3] = rho * w;
  conservative[4] = pressure / (gamma - 1.0) + kinetic_energy + magnetic_energy;
  conservative[5] = by;
  conservative[6] = bz;
}

void conservative_to_primitive(const double* conservative, double* primitive, double bx,
                               double gamma)
{
  const double rho = conservative[0];
  if (rho <= 0.0) {
    throw std::runtime_error("density must be positive");
  }

  const double u  = conservative[1] / rho;
  const double v  = conservative[2] / rho;
  const double w  = conservative[3] / rho;
  const double by = conservative[5];
  const double bz = conservative[6];

  const double kinetic_energy  = 0.5 * rho * (u * u + v * v + w * w);
  const double magnetic_energy = 0.5 * (bx * bx + by * by + bz * bz);
  const double pressure = (gamma - 1.0) * (conservative[4] - kinetic_energy - magnetic_energy);

  primitive[0] = rho;
  primitive[1] = u;
  primitive[2] = v;
  primitive[3] = w;
  primitive[4] = pressure;
  primitive[5] = by;
  primitive[6] = bz;
}

void convert_primitive_to_conservative(ArrayView2D primitive, ArrayView2D conservative, double bx,
                                       double gamma)
{
  const int ix_min = 0;
  const int ix_max = primitive.extent(0) - 1;

  for (int ix = ix_min; ix <= ix_max; ++ix) {
    primitive_to_conservative(&primitive(ix, 0), &conservative(ix, 0), bx, gamma);
  }
}

void convert_conservative_to_primitive(ArrayView2D conservative, ArrayView2D primitive, double bx,
                                       double gamma)
{
  const int ix_min = 0;
  const int ix_max = conservative.extent(0) - 1;

  for (int ix = ix_min; ix <= ix_max; ++ix) {
    conservative_to_primitive(&conservative(ix, 0), &primitive(ix, 0), bx, gamma);
  }
}

void set_boundary_lb(ArrayView2D dst, ArrayView2D src, int lbx)
{
  const int ix_min = 0;

  for (int ix = ix_min; ix < lbx; ++ix) {
    for (int component = 0; component < N_Component; ++component) {
      dst(ix, component) = src(lbx, component);
    }
  }
}

void set_boundary_ub(ArrayView2D dst, ArrayView2D src, int ubx)
{
  const int ix_max = dst.extent(0) - 1;

  for (int ix = ubx + 1; ix <= ix_max; ++ix) {
    for (int component = 0; component < N_Component; ++component) {
      dst(ix, component) = src(ubx, component);
    }
  }
}

void set_boundary(ArrayView2D dst, ArrayView2D src, int lbx, int ubx)
{
  set_boundary_lb(dst, src, lbx);
  set_boundary_ub(dst, src, ubx);
}

void compute_lr(SolverWorkspace& workspace)
{
  const ArrayView2D up   = workspace.up;
  const ArrayView2D up_l = workspace.up_l;
  const ArrayView2D up_r = workspace.up_r;

  const int lbx = workspace.Lbx;
  const int ubx = workspace.Ubx;
  for (int ix = lbx; ix <= ubx; ++ix) {
    for (int component = 0; component < N_Component; ++component) {
      const double slope_l = up(ix, component) - up(ix - 1, component);
      const double slope_r = up(ix + 1, component) - up(ix, component);
      const double slope   = mc2(slope_l, slope_r);
      up_l(ix, component)  = up(ix, component) + 0.5 * slope;
      up_r(ix, component)  = up(ix, component) - 0.5 * slope;
    }
  }

  set_boundary_lb(up_l, up_r, lbx);
  set_boundary_ub(up_r, up_l, ubx);
}

void compute_flux_hlld(SolverWorkspace& workspace, double bx, double gamma)
{
  const ArrayView2D up_l = workspace.up_l;
  const ArrayView2D up_r = workspace.up_r;
  const ArrayView2D flux = workspace.flux;

  const int lbx = workspace.Lbx;
  const int ubx = workspace.Ubx;
  for (int ix = lbx - 1; ix <= ubx + 1; ++ix) {
    ::hlld_flux_from_primitive(&up_l(ix, 0), &up_r(ix + 1, 0), bx, gamma, &flux(ix, 0));
  }
}

void compute_rhs(SolverWorkspace& workspace)
{
  const ArrayView2D uc   = workspace.uc;
  const ArrayView2D up   = workspace.up;
  const ArrayView2D flux = workspace.flux;
  const ArrayView2D rhs  = workspace.rhs;

  set_boundary(uc, uc, workspace.Lbx, workspace.Ubx);
  convert_conservative_to_primitive(uc, up, workspace.bx, workspace.gamma);
  set_boundary(up, up, workspace.Lbx, workspace.Ubx);
  compute_lr(workspace);
  compute_flux_hlld(workspace, workspace.bx, workspace.gamma);

  const int lbx = workspace.Lbx;
  const int ubx = workspace.Ubx;
  for (int ix = lbx; ix <= ubx; ++ix) {
    for (int component = 0; component < N_Component; ++component) {
      rhs(ix, component) = -(flux(ix, component) - flux(ix - 1, component)) / workspace.dx;
    }
  }
}

void copy(ArrayView2D source, ArrayView2D destination)
{
  const int nx = source.extent(0);
  for (int ix = 0; ix < nx; ++ix) {
    for (int component = 0; component < N_Component; ++component) {
      destination(ix, component) = source(ix, component);
    }
  }
}

void push_ssp_rk3(SolverWorkspace& workspace, double dt)
{
  constexpr double coeffs[3][3] = {
      {1.0, 0.0, 1.0},
      {3.0 / 4.0, 1.0 / 4.0, 1.0 / 4.0},
      {1.0 / 3.0, 2.0 / 3.0, 2.0 / 3.0},
  };

  const ArrayView2D prev = workspace.prev;
  const ArrayView2D rhs  = workspace.rhs;

  copy(workspace.uc, prev);

  for (int substep = 0; substep < 3; ++substep) {
    compute_rhs(workspace);

    const double a = coeffs[substep][0];
    const double b = coeffs[substep][1];
    const double c = coeffs[substep][2];

    const int lbx = workspace.Lbx;
    const int ubx = workspace.Ubx;
    for (int ix = lbx; ix <= ubx; ++ix) {
      for (int component = 0; component < N_Component; ++component) {
        workspace.uc(ix, component) =
            a * prev(ix, component) + b * workspace.uc(ix, component) + c * dt * rhs(ix, component);
      }
    }

    set_boundary(workspace.uc, workspace.uc, workspace.Lbx, workspace.Ubx);
    convert_conservative_to_primitive(workspace.uc, workspace.up, workspace.bx, workspace.gamma);
    set_boundary(workspace.up, workspace.up, workspace.Lbx, workspace.Ubx);
  }
}

void evolve_ssp_rk3(SolverWorkspace& workspace, double dt, double t_final)
{
  double elapsed_time = 0.0;
  while (elapsed_time < t_final) {
    const double remaining_time = t_final - elapsed_time;
    const double step_dt        = std::min(dt, remaining_time);
    push_ssp_rk3(workspace, step_dt);
    elapsed_time = (step_dt < dt) ? t_final : (elapsed_time + step_dt);
  }
}

} // namespace mhd1d
