#include "mhd1d.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <utility>

namespace mhd1d
{

namespace
{

constexpr double kHlldEps = 1.0e-40;

double sign(const double x)
{
  return copysign(1.0, x);
}

double mc2(double a, double b)
{
  return 0.5 * (sign(a) + sign(b)) *
         std::min({2.0 * std::abs(a), 2.0 * std::abs(b), 0.5 * std::abs(a + b)});
}

StateVector row_to_state(ArrayView2D cells, std::size_t row)
{
  StateVector state{};
  for (std::size_t component = 0; component < kStateWidth; ++component) {
    state[component] = cells(row, component);
  }
  return state;
}

void state_to_row(const StateVector& state, ArrayView2D cells, std::size_t row)
{
  for (std::size_t component = 0; component < kStateWidth; ++component) {
    cells(row, component) = state[component];
  }
}

void copy_cells(ArrayView2D source, ArrayView2D destination)
{
  const int nx = static_cast<int>(source.extent(0));
  for (int ix = 0; ix < nx; ++ix) {
    const std::size_t x = static_cast<std::size_t>(ix);
    for (std::size_t component = 0; component < kStateWidth; ++component) {
      destination(x, component) = source(x, component);
    }
  }
}

void convert_conservative_to_primitive(ArrayView2D conservative_cells, ArrayView2D primitive_cells,
                                       double bx, double gamma)
{
  const int nx = static_cast<int>(conservative_cells.extent(0));
  for (int ix = 0; ix < nx; ++ix) {
    const std::size_t x = static_cast<std::size_t>(ix);
    const StateVector primitive =
        conservative_to_primitive(row_to_state(conservative_cells, x), bx, gamma);
    state_to_row(primitive, primitive_cells, x);
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

void primitive_profile_to_conservative(ArrayView2D primitive_cells, ArrayView2D conservative_cells,
                                       double bx, double gamma)
{
  const int nx = static_cast<int>(primitive_cells.extent(0));
  for (int ix = 0; ix < nx; ++ix) {
    const std::size_t x = static_cast<std::size_t>(ix);
    const StateVector conservative =
        primitive_to_conservative(row_to_state(primitive_cells, x), bx, gamma);
    state_to_row(conservative, conservative_cells, x);
  }
}

void reconstruct_mc2(SolverWorkspace& workspace)
{
  const ArrayView2D primitive_cells = workspace.primitive;
  const ArrayView2D left_states     = workspace.primitive_left;
  const ArrayView2D right_states    = workspace.primitive_right;

  const int lbx = static_cast<int>(workspace.Lbx) - 1;
  const int ubx = static_cast<int>(workspace.Ubx) + 1;
  for (int ix = lbx; ix <= ubx; ++ix) {
    const std::size_t i = static_cast<std::size_t>(ix);
    for (std::size_t component = 0; component < kStateWidth; ++component) {
      const double left_slope = primitive_cells(i, component) -
                                primitive_cells(static_cast<std::size_t>(ix - 1), component);
      const double right_slope = primitive_cells(static_cast<std::size_t>(ix + 1), component) -
                                 primitive_cells(i, component);
      const double slope         = mc2(left_slope, right_slope);
      left_states(i, component)  = primitive_cells(i, component) + 0.5 * slope;
      right_states(i, component) = primitive_cells(i, component) - 0.5 * slope;
    }
  }
}

void compute_flux_hlld(SolverWorkspace& workspace, double bx, double gamma)
{
  const ArrayView2D left_states  = workspace.primitive_left;
  const ArrayView2D right_states = workspace.primitive_right;
  const ArrayView2D fluxes       = workspace.flux;

  const int lbx = static_cast<int>(workspace.Lbx);
  const int ubx = static_cast<int>(workspace.Ubx);
  for (int ix = lbx - 1; ix <= ubx; ++ix) {
    const std::size_t i    = static_cast<std::size_t>(ix);
    const StateVector flux = hlld_flux_from_primitive(
        row_to_state(left_states, i), row_to_state(right_states, static_cast<std::size_t>(ix + 1)),
        bx, gamma);
    state_to_row(flux, fluxes, i);
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
  const double sign1_l    = std::copysign(1.0, std::abs(temp_fst_l) - kHlldEps);
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
  const double sign1_r    = std::copysign(1.0, std::abs(temp_fst_r) - kHlldEps);
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
  const double sign1_b  = std::copysign(1.0, abbx - kHlldEps);
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

void set_boundary(ArrayView2D u, std::size_t lbx, std::size_t ubx)
{
  const std::size_t nx_total = u.extent(0);

  for (std::size_t ix = 0; ix < lbx; ++ix) {
    for (std::size_t component = 0; component < kStateWidth; ++component) {
      u(ix, component) = u(lbx, component);
    }
  }

  for (std::size_t ix = ubx + 1U; ix < nx_total; ++ix) {
    for (std::size_t component = 0; component < kStateWidth; ++component) {
      u(ix, component) = u(ubx, component);
    }
  }
}

void compute_rhs(SolverWorkspace& workspace)
{
  const ArrayView2D conservative = workspace.conservative;
  const ArrayView2D primitive    = workspace.primitive;
  const ArrayView2D fluxes       = workspace.flux;
  const ArrayView2D rhs          = workspace.rhs1;

  set_boundary(conservative, workspace.Lbx, workspace.Ubx);
  convert_conservative_to_primitive(conservative, primitive, workspace.bx, workspace.gamma);
  set_boundary(primitive, workspace.Lbx, workspace.Ubx);
  reconstruct_mc2(workspace);
  compute_flux_hlld(workspace, workspace.bx, workspace.gamma);

  const int lbx = static_cast<int>(workspace.Lbx);
  const int ubx = static_cast<int>(workspace.Ubx);
  for (int ix = lbx; ix <= ubx; ++ix) {
    const std::size_t x = static_cast<std::size_t>(ix);
    for (std::size_t component = 0; component < kStateWidth; ++component) {
      rhs(x, component) =
          -(fluxes(x, component) - fluxes(static_cast<std::size_t>(ix - 1), component)) /
          workspace.dx;
    }
  }
}

void push_ssp_rk3(SolverWorkspace& workspace, double dt)
{
  constexpr double kCoeffs[3][3] = {
      {1.0, 0.0, 1.0},
      {3.0 / 4.0, 1.0 / 4.0, 1.0 / 4.0},
      {1.0 / 3.0, 2.0 / 3.0, 2.0 / 3.0},
  };

  const ArrayView2D u0  = workspace.stage1;
  const ArrayView2D rhs = workspace.rhs1;

  copy_cells(workspace.conservative, u0);

  for (int substep = 0; substep < 3; ++substep) {
    compute_rhs(workspace);

    const double a = kCoeffs[substep][0];
    const double b = kCoeffs[substep][1];
    const double c = kCoeffs[substep][2];

    const int lbx = static_cast<int>(workspace.Lbx);
    const int ubx = static_cast<int>(workspace.Ubx);
    for (int ix = lbx; ix <= ubx; ++ix) {
      const std::size_t x = static_cast<std::size_t>(ix);
      for (std::size_t component = 0; component < kStateWidth; ++component) {
        workspace.conservative(x, component) = a * u0(x, component) +
                                               b * workspace.conservative(x, component) +
                                               c * dt * rhs(x, component);
      }
    }

    convert_conservative_to_primitive(workspace.conservative, workspace.primitive, workspace.bx,
                                      workspace.gamma);
    set_boundary(workspace.primitive, workspace.Lbx, workspace.Ubx);
  }

  set_boundary(workspace.conservative, workspace.Lbx, workspace.Ubx);
}

void evolve_ssp_rk3(SolverWorkspace& workspace, double dt, double t_final)
{
  if (t_final < 0.0 || dt <= 0.0) {
    set_boundary(workspace.conservative, workspace.Lbx, workspace.Ubx);
    convert_conservative_to_primitive(workspace.conservative, workspace.primitive, workspace.bx,
                                      workspace.gamma);
    set_boundary(workspace.primitive, workspace.Lbx, workspace.Ubx);
    return;
  }

  set_boundary(workspace.conservative, workspace.Lbx, workspace.Ubx);
  convert_conservative_to_primitive(workspace.conservative, workspace.primitive, workspace.bx,
                                    workspace.gamma);
  set_boundary(workspace.primitive, workspace.Lbx, workspace.Ubx);

  double elapsed_time = 0.0;
  while (elapsed_time < t_final) {
    const double remaining_time = t_final - elapsed_time;
    const double step_dt        = std::min(dt, remaining_time);
    push_ssp_rk3(workspace, step_dt);
    elapsed_time = (step_dt < dt) ? t_final : (elapsed_time + step_dt);
  }
}

} // namespace mhd1d
