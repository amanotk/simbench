#include "mhd1d.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <utility>

namespace mhd1d
{

namespace
{

constexpr double HLLD_EPS = 1.0e-40;

double sign(const double x)
{
  return copysign(1.0, x);
}

double mc2(double a, double b)
{
  return 0.5 * (sign(a) + sign(b)) *
         std::min({2.0 * std::abs(a), 2.0 * std::abs(b), 0.5 * std::abs(a + b)});
}

StateVector row_to_state(ArrayView2D cells, int row)
{
  StateVector state{};
  for (int component = 0; component < N_Component; ++component) {
    state[component] = cells(row, component);
  }
  return state;
}

void state_to_row(const StateVector& state, ArrayView2D cells, int row)
{
  for (int component = 0; component < N_Component; ++component) {
    cells(row, component) = state[component];
  }
}

void copy_cells(ArrayView2D source, ArrayView2D destination)
{
  const int nx = source.extent(0);
  for (int ix = 0; ix < nx; ++ix) {
    for (int component = 0; component < N_Component; ++component) {
      destination(ix, component) = source(ix, component);
    }
  }
}

void convert_conservative_to_primitive(ArrayView2D conservative, ArrayView2D primitive, double bx,
                                       double gamma)
{
  const int ix_min = 0;
  const int ix_max = conservative.extent(0) - 1;

  for (int ix = ix_min; ix <= ix_max; ++ix) {
    const StateVector up = conservative_to_primitive(row_to_state(conservative, ix), bx, gamma);
    state_to_row(up, primitive, ix);
  }
}

} // namespace

StateVector primitive_to_conservative(const StateVector& primitive, double bx, double gamma)
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

  return StateVector{
      rho, rho * u, rho * v, rho * w, pressure / (gamma - 1.0) + kinetic_energy + magnetic_energy,
      by,  bz,
  };
}

StateVector conservative_to_primitive(const StateVector& conservative, double bx, double gamma)
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

  return StateVector{rho, u, v, w, pressure, by, bz};
}

void primitive_profile_to_conservative(ArrayView2D primitive, ArrayView2D conservative, double bx,
                                       double gamma)
{
  const int ix_min = 0;
  const int ix_max = primitive.extent(0) - 1;

  for (int ix = ix_min; ix <= ix_max; ++ix) {
    const StateVector uc = primitive_to_conservative(row_to_state(primitive, ix), bx, gamma);
    state_to_row(uc, conservative, ix);
  }
}

StateVector hlld_flux_from_primitive(const StateVector& left, const StateVector& right, double bx,
                                     double gamma);

void reconstruct_mc2(SolverWorkspace& workspace)
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
    const StateVector flux_hlld =
        hlld_flux_from_primitive(row_to_state(up_l, ix), row_to_state(up_r, ix + 1), bx, gamma);
    state_to_row(flux_hlld, flux, ix);
  }
}

StateVector hlld_flux_from_primitive(const StateVector& left, const StateVector& right, double bx,
                                     double gamma)
{
  const double rol = left[0];
  const double vxl = left[1];
  const double vyl = left[2];
  const double vzl = left[3];
  const double prl = left[4];
  const double byl = left[5];
  const double bzl = left[6];

  const double ror = right[0];
  const double vxr = right[1];
  const double vyr = right[2];
  const double vzr = right[3];
  const double prr = right[4];
  const double byr = right[5];
  const double bzr = right[6];

  const double igm  = 1.0 / (gamma - 1.0);
  const double bxs  = bx;
  const double bxsq = bxs * bxs;

  const double pbl = 0.5 * (bxsq + byl * byl + bzl * bzl);
  const double pbr = 0.5 * (bxsq + byr * byr + bzr * bzr);
  const double ptl = prl + pbl;
  const double ptr = prr + pbr;

  const double rxl = rol * vxl;
  const double ryl = rol * vyl;
  const double rzl = rol * vzl;
  const double rxr = ror * vxr;
  const double ryr = ror * vyr;
  const double rzr = ror * vzr;

  const double eel = prl * igm + 0.5 * (rxl * vxl + ryl * vyl + rzl * vzl) + pbl;
  const double eer = prr * igm + 0.5 * (rxr * vxr + ryr * vyr + rzr * vzr) + pbr;

  const double gmpl = gamma * prl;
  const double gmpr = gamma * prr;
  const double gpbl = gmpl + 2.0 * pbl;
  const double gpbr = gmpr + 2.0 * pbr;

  const double cfl = std::sqrt((gpbl + std::sqrt((gmpl - 2.0 * pbl) * (gmpl - 2.0 * pbl) +
                                                 4.0 * gmpl * (byl * byl + bzl * bzl))) *
                               0.5 / rol);
  const double cfr = std::sqrt((gpbr + std::sqrt((gmpr - 2.0 * pbr) * (gmpr - 2.0 * pbr) +
                                                 4.0 * gmpr * (byr * byr + bzr * bzr))) *
                               0.5 / ror);

  const double sl = std::min(vxl, vxr) - std::max(cfl, cfr);
  const double sr = std::max(vxl, vxr) + std::max(cfl, cfr);

  const StateVector fql{rxl,
                        rxl * vxl + ptl - bxsq,
                        rxl * vyl - bxs * byl,
                        rxl * vzl - bxs * bzl,
                        vxl * (eel + ptl - bxsq) - bxs * (vyl * byl + vzl * bzl),
                        byl * vxl - bxs * vyl,
                        bzl * vxl - bxs * vzl};
  const StateVector fqr{rxr,
                        rxr * vxr + ptr - bxsq,
                        rxr * vyr - bxs * byr,
                        rxr * vzr - bxs * bzr,
                        vxr * (eer + ptr - bxsq) - bxs * (vyr * byr + vzr * bzr),
                        byr * vxr - bxs * vyr,
                        bzr * vxr - bxs * vzr};

  const double sdl   = sl - vxl;
  const double sdr   = sr - vxr;
  const double rosdl = rol * sdl;
  const double rosdr = ror * sdr;
  const double temp  = 1.0 / (rosdr - rosdl);
  const double sm    = (rosdr * vxr - rosdl * vxl - ptr + ptl) * temp;
  const double sdml  = sl - sm;
  const double sdmr  = sr - sm;
  const double ptst  = (rosdr * ptl - rosdl * ptr + rosdl * rosdr * (vxr - vxl)) * temp;

  const double temp_fst_l = rosdl * sdml - bxsq;
  const double sign1_l    = std::copysign(1.0, std::abs(temp_fst_l) - HLLD_EPS);
  const double maxs1_l    = std::max(0.0, sign1_l);
  const double mins1_l    = std::min(0.0, sign1_l);
  const double itf_l      = 1.0 / (temp_fst_l + mins1_l);
  const double isdml      = 1.0 / sdml;

  const double temp_l   = bxs * (sdl - sdml) * itf_l;
  const double rolst    = maxs1_l * (rosdl * isdml) - mins1_l * rol;
  const double vxlst    = maxs1_l * sm - mins1_l * vxl;
  const double rxlst    = rolst * vxlst;
  const double vylst    = maxs1_l * (vyl - byl * temp_l) - mins1_l * vyl;
  const double rylst    = rolst * vylst;
  const double vzlst    = maxs1_l * (vzl - bzl * temp_l) - mins1_l * vzl;
  const double rzlst    = rolst * vzlst;
  const double temp_l_b = (rosdl * sdl - bxsq) * itf_l;
  const double bylst    = maxs1_l * (byl * temp_l_b) - mins1_l * byl;
  const double bzlst    = maxs1_l * (bzl * temp_l_b) - mins1_l * bzl;
  const double vdbstl   = vxlst * bxs + vylst * bylst + vzlst * bzlst;
  const double eelst    = maxs1_l * ((sdl * eel - ptl * vxl + ptst * sm +
                                   bxs * (vxl * bxs + vyl * byl + vzl * bzl - vdbstl)) *
                                  isdml) -
                       mins1_l * eel;

  const double temp_fst_r = rosdr * sdmr - bxsq;
  const double sign1_r    = std::copysign(1.0, std::abs(temp_fst_r) - HLLD_EPS);
  const double maxs1_r    = std::max(0.0, sign1_r);
  const double mins1_r    = std::min(0.0, sign1_r);
  const double itf_r      = 1.0 / (temp_fst_r + mins1_r);
  const double isdmr      = 1.0 / sdmr;

  const double temp_r   = bxs * (sdr - sdmr) * itf_r;
  const double rorst    = maxs1_r * (rosdr * isdmr) - mins1_r * ror;
  const double vxrst    = maxs1_r * sm - mins1_r * vxr;
  const double rxrst    = rorst * vxrst;
  const double vyrst    = maxs1_r * (vyr - byr * temp_r) - mins1_r * vyr;
  const double ryrst    = rorst * vyrst;
  const double vzrst    = maxs1_r * (vzr - bzr * temp_r) - mins1_r * vzr;
  const double rzrst    = rorst * vzrst;
  const double temp_r_b = (rosdr * sdr - bxsq) * itf_r;
  const double byrst    = maxs1_r * (byr * temp_r_b) - mins1_r * byr;
  const double bzrst    = maxs1_r * (bzr * temp_r_b) - mins1_r * bzr;
  const double vdbstr   = vxrst * bxs + vyrst * byrst + vzrst * bzrst;
  const double eerst    = maxs1_r * ((sdr * eer - ptr * vxr + ptst * sm +
                                   bxs * (vxr * bxs + vyr * byr + vzr * bzr - vdbstr)) *
                                  isdmr) -
                       mins1_r * eer;

  const double sqrtrol  = std::sqrt(rolst);
  const double sqrtror  = std::sqrt(rorst);
  const double abbx     = std::abs(bxs);
  const double slst     = sm - abbx / sqrtrol;
  const double srst     = sm + abbx / sqrtror;
  const double signbx   = std::copysign(1.0, bxs);
  const double sign1_b  = std::copysign(1.0, abbx - HLLD_EPS);
  const double maxs1_b  = std::max(0.0, sign1_b);
  const double mins1_b  = -std::min(0.0, sign1_b);
  const double invsumro = maxs1_b / (sqrtrol + sqrtror);

  const double roldst = rolst;
  const double rordst = rorst;
  const double rxldst = rxlst;
  const double rxrdst = rxrst;

  const double vy_shared =
      invsumro * (sqrtrol * vylst + sqrtror * vyrst + signbx * (byrst - bylst));
  const double ryldst = rylst * mins1_b + roldst * vy_shared;
  const double ryrdst = ryrst * mins1_b + rordst * vy_shared;

  const double vz_shared =
      invsumro * (sqrtrol * vzlst + sqrtror * vzrst + signbx * (bzrst - bzlst));
  const double rzldst = rzlst * mins1_b + roldst * vz_shared;
  const double rzrdst = rzrst * mins1_b + rordst * vz_shared;

  const double by_shared =
      invsumro * (sqrtrol * byrst + sqrtror * bylst + signbx * sqrtrol * sqrtror * (vyrst - vylst));
  const double byldst = bylst * mins1_b + by_shared;
  const double byrdst = byrst * mins1_b + by_shared;

  const double bz_shared =
      invsumro * (sqrtrol * bzrst + sqrtror * bzlst + signbx * sqrtrol * sqrtror * (vzrst - vzlst));
  const double bzldst = bzlst * mins1_b + bz_shared;
  const double bzrdst = bzrst * mins1_b + bz_shared;

  const double vyldst   = vylst * mins1_b + vy_shared;
  const double vyrdst   = vyrst * mins1_b + vy_shared;
  const double vzldst   = vzlst * mins1_b + vz_shared;
  const double vzrdst   = vzrst * mins1_b + vz_shared;
  const double temp_dst = sm * bxs + vyldst * byldst + vzldst * bzldst;
  const double eeldst   = eelst - sqrtrol * signbx * (vdbstl - temp_dst) * maxs1_b;
  const double eerdst   = eerst + sqrtror * signbx * (vdbstr - temp_dst) * maxs1_b;

  const double sign1       = std::copysign(1.0, sm);
  const double maxs1       = std::max(0.0, sign1);
  const double mins1       = -std::min(0.0, sign1);
  const double msl         = std::min(sl, 0.0);
  const double mslst       = std::min(slst, 0.0);
  const double msrst       = std::max(srst, 0.0);
  const double msr         = std::max(sr, 0.0);
  const double temp_flux_l = mslst - msl;
  const double temp_flux_r = msrst - msr;

  return StateVector{
      (fql[0] - msl * rol - rolst * temp_flux_l + roldst * mslst) * maxs1 +
          (fqr[0] - msr * ror - rorst * temp_flux_r + rordst * msrst) * mins1,
      (fql[1] - msl * rxl - rxlst * temp_flux_l + rxldst * mslst) * maxs1 +
          (fqr[1] - msr * rxr - rxrst * temp_flux_r + rxrdst * msrst) * mins1,
      (fql[2] - msl * ryl - rylst * temp_flux_l + ryldst * mslst) * maxs1 +
          (fqr[2] - msr * ryr - ryrst * temp_flux_r + ryrdst * msrst) * mins1,
      (fql[3] - msl * rzl - rzlst * temp_flux_l + rzldst * mslst) * maxs1 +
          (fqr[3] - msr * rzr - rzrst * temp_flux_r + rzrdst * msrst) * mins1,
      (fql[4] - msl * eel - eelst * temp_flux_l + eeldst * mslst) * maxs1 +
          (fqr[4] - msr * eer - eerst * temp_flux_r + eerdst * msrst) * mins1,
      (fql[5] - msl * byl - bylst * temp_flux_l + byldst * mslst) * maxs1 +
          (fqr[5] - msr * byr - byrst * temp_flux_r + byrdst * msrst) * mins1,
      (fql[6] - msl * bzl - bzlst * temp_flux_l + bzldst * mslst) * maxs1 +
          (fqr[6] - msr * bzr - bzrst * temp_flux_r + bzrdst * msrst) * mins1,
  };
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

void compute_rhs(SolverWorkspace& workspace)
{
  const ArrayView2D uc   = workspace.uc;
  const ArrayView2D up   = workspace.up;
  const ArrayView2D flux = workspace.flux;
  const ArrayView2D rhs  = workspace.rhs;

  set_boundary(uc, uc, workspace.Lbx, workspace.Ubx);
  convert_conservative_to_primitive(uc, up, workspace.bx, workspace.gamma);
  set_boundary(up, up, workspace.Lbx, workspace.Ubx);
  reconstruct_mc2(workspace);
  compute_flux_hlld(workspace, workspace.bx, workspace.gamma);

  const int lbx = workspace.Lbx;
  const int ubx = workspace.Ubx;
  for (int ix = lbx; ix <= ubx; ++ix) {
    for (int component = 0; component < N_Component; ++component) {
      rhs(ix, component) = -(flux(ix, component) - flux(ix - 1, component)) / workspace.dx;
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

  copy_cells(workspace.uc, prev);

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
