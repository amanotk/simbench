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
constexpr int    kGhost   = static_cast<int>(kGhostWidth);

using ArrayView      = stdex::mdspan<double, stdex::dextents<std::size_t, 2>>;
using ConstArrayView = stdex::mdspan<const double, stdex::dextents<std::size_t, 2>>;

double minmod3(double first, double second, double third)
{
  if (first * second > 0.0 && first * third > 0.0) {
    const double limited = std::min({std::abs(first), std::abs(second), std::abs(third)});
    return std::copysign(limited, first);
  }

  return 0.0;
}

StateVector row_to_state(ConstArrayView cells, std::size_t row)
{
  StateVector state{};
  for (std::size_t component = 0; component < kStateWidth; ++component) {
    state[component] = cells(row, component);
  }
  return state;
}

void state_to_row(const StateVector& state, ArrayView cells, std::size_t row)
{
  for (std::size_t component = 0; component < kStateWidth; ++component) {
    cells(row, component) = state[component];
  }
}

void conservative_profile_to_primitive_profile_inplace(ConstArrayView conservative_cells,
                                                       ArrayView primitive_cells, double bx,
                                                       double gamma)
{
  const int nx = static_cast<int>(conservative_cells.extent(0));
  for (int ix = 0; ix < nx; ++ix) {
    const std::size_t x = static_cast<std::size_t>(ix);
    const StateVector primitive =
        conservative_to_primitive(row_to_state(conservative_cells, x), bx, gamma);
    state_to_row(primitive, primitive_cells, x);
  }
}

void pad_zero_gradient_ghost_cells_inplace(ConstArrayView cells, ArrayView padded)
{
  const int nx        = static_cast<int>(cells.extent(0));
  const int padded_nx = static_cast<int>(padded.extent(0));

  for (int ghost = 0; ghost < kGhost; ++ghost) {
    const std::size_t g = static_cast<std::size_t>(ghost);
    for (std::size_t component = 0; component < kStateWidth; ++component) {
      padded(g, component) = cells(0U, component);
      padded(static_cast<std::size_t>(padded_nx - 1 - ghost), component) =
          cells(static_cast<std::size_t>(nx - 1), component);
    }
  }

  for (int ix = 0; ix < nx; ++ix) {
    const std::size_t src = static_cast<std::size_t>(ix);
    const std::size_t dst = static_cast<std::size_t>(kGhost + ix);
    for (std::size_t component = 0; component < kStateWidth; ++component) {
      padded(dst, component) = cells(src, component);
    }
  }
}

void mc2_slopes_inplace(ConstArrayView primitive_cells, ArrayView slopes)
{
  const int nx = static_cast<int>(primitive_cells.extent(0));

  for (int ix = 0; ix < nx; ++ix) {
    const std::size_t x = static_cast<std::size_t>(ix);
    for (std::size_t component = 0; component < kStateWidth; ++component) {
      slopes(x, component) = 0.0;
    }
  }

  for (int ix = 1; ix <= nx - 2; ++ix) {
    const std::size_t x = static_cast<std::size_t>(ix);
    for (std::size_t component = 0; component < kStateWidth; ++component) {
      const double left_difference = primitive_cells(x, component) -
                                     primitive_cells(static_cast<std::size_t>(ix - 1), component);
      const double right_difference = primitive_cells(static_cast<std::size_t>(ix + 1), component) -
                                      primitive_cells(x, component);
      const double centered_difference =
          0.5 * (primitive_cells(static_cast<std::size_t>(ix + 1), component) -
                 primitive_cells(static_cast<std::size_t>(ix - 1), component));
      slopes(x, component) =
          minmod3(2.0 * left_difference, centered_difference, 2.0 * right_difference);
    }
  }
}

void reconstruct_mc2_interfaces_inplace(ConstArrayView primitive_cells, ConstArrayView slopes,
                                        ArrayView left_states, ArrayView right_states)
{
  const int interface_count = static_cast<int>(primitive_cells.extent(0) - 1U);
  for (int ix = 0; ix < interface_count; ++ix) {
    const std::size_t x = static_cast<std::size_t>(ix);
    for (std::size_t component = 0; component < kStateWidth; ++component) {
      left_states(x, component)  = primitive_cells(x, component) + 0.5 * slopes(x, component);
      right_states(x, component) = primitive_cells(static_cast<std::size_t>(ix + 1), component) -
                                   0.5 * slopes(static_cast<std::size_t>(ix + 1), component);
    }
  }
}

void copy_cells(ConstArrayView source, ArrayView destination)
{
  const int nx = static_cast<int>(source.extent(0));
  for (int ix = 0; ix < nx; ++ix) {
    const std::size_t x = static_cast<std::size_t>(ix);
    for (std::size_t component = 0; component < kStateWidth; ++component) {
      destination(x, component) = source(x, component);
    }
  }
}

void compute_semidiscrete_rhs_inplace(ConstArrayView conservative_cells, double dx, double bx,
                                      double gamma, SolverWorkspace& workspace, ArrayView rhs)
{
  const ArrayView padded_conservative = workspace.conservative;
  const ArrayView padded_primitive    = workspace.primitive;
  const ArrayView slopes              = workspace.slopes;
  const ArrayView left_interface      = workspace.primitive_left;
  const ArrayView right_interface     = workspace.primitive_right;

  pad_zero_gradient_ghost_cells_inplace(conservative_cells, padded_conservative);
  conservative_profile_to_primitive_profile_inplace(padded_conservative, padded_primitive, bx,
                                                    gamma);
  mc2_slopes_inplace(padded_primitive, slopes);
  reconstruct_mc2_interfaces_inplace(padded_primitive, slopes, left_interface, right_interface);

  const int lbx = static_cast<int>(workspace.Lbx);
  const int ubx = static_cast<int>(workspace.Ubx);
  for (int ix = lbx; ix <= ubx; ++ix) {
    const std::size_t i = static_cast<std::size_t>(ix - lbx);
    const std::size_t x = static_cast<std::size_t>(ix);

    const StateVector right_flux = hlld_flux_from_primitive(
        row_to_state(left_interface, x), row_to_state(right_interface, x), bx, gamma);
    const StateVector left_flux = hlld_flux_from_primitive(
        row_to_state(left_interface, x - 1U), row_to_state(right_interface, x - 1U), bx, gamma);
    for (std::size_t component = 0; component < kStateWidth; ++component) {
      rhs(i, component) = -(right_flux[component] - left_flux[component]) / dx;
    }
  }
}

void ssp_rk3_step_inplace(ConstArrayView conservative_cells, double dt, double dx, double bx,
                          double gamma, SolverWorkspace& workspace, ArrayView output)
{
  const ArrayView first_stage  = workspace.stage1;
  const ArrayView second_stage = workspace.stage2;
  const ArrayView first_rhs    = workspace.rhs1;
  const ArrayView second_rhs   = workspace.rhs2;
  const ArrayView third_rhs    = workspace.rhs3;

  copy_cells(conservative_cells, first_stage);
  compute_semidiscrete_rhs_inplace(conservative_cells, dx, bx, gamma, workspace, first_rhs);
  const int lbx = static_cast<int>(workspace.Lbx);
  const int ubx = static_cast<int>(workspace.Ubx);

  for (int ix = lbx; ix <= ubx; ++ix) {
    const std::size_t i = static_cast<std::size_t>(ix - lbx);
    for (std::size_t component = 0; component < kStateWidth; ++component) {
      first_stage(i, component) += dt * first_rhs(i, component);
    }
  }

  compute_semidiscrete_rhs_inplace(first_stage, dx, bx, gamma, workspace, second_rhs);
  for (int ix = lbx; ix <= ubx; ++ix) {
    const std::size_t i = static_cast<std::size_t>(ix - lbx);
    for (std::size_t component = 0; component < kStateWidth; ++component) {
      second_stage(i, component) =
          0.75 * conservative_cells(i, component) +
          0.25 * (first_stage(i, component) + dt * second_rhs(i, component));
    }
  }

  compute_semidiscrete_rhs_inplace(second_stage, dx, bx, gamma, workspace, third_rhs);
  for (int ix = lbx; ix <= ubx; ++ix) {
    const std::size_t i = static_cast<std::size_t>(ix - lbx);
    for (std::size_t component = 0; component < kStateWidth; ++component) {
      output(i, component) =
          (1.0 / 3.0) * conservative_cells(i, component) +
          (2.0 / 3.0) * (second_stage(i, component) + dt * third_rhs(i, component));
    }
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

void primitive_profile_to_conservative(ConstArrayView primitive_cells, ArrayView conservative_cells,
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

void conservative_profile_to_primitive(ConstArrayView conservative_cells, ArrayView primitive_cells,
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

void mc2_slopes(ConstArrayView primitive_cells, ArrayView slopes)
{
  if (primitive_cells.extent(0) < 3U) {
    throw std::runtime_error("primitive_cells must contain at least three cells");
  }

  mc2_slopes_inplace(primitive_cells, slopes);
}

void reconstruct_mc2_interfaces(ConstArrayView primitive_cells, ArrayView left_states,
                                ArrayView right_states)
{
  if (primitive_cells.extent(0) < 2U) {
    throw std::runtime_error("primitive_cells must contain at least two cells");
  }

  const std::size_t   interface_count = primitive_cells.extent(0) - 1U;
  std::vector<double> slopes_buffer(primitive_cells.extent(0) * kStateWidth, 0.0);
  ArrayView           slopes(slopes_buffer.data(), primitive_cells.extent(0), kStateWidth);
  mc2_slopes_inplace(primitive_cells, slopes);
  reconstruct_mc2_interfaces_inplace(primitive_cells, slopes, left_states, right_states);
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

void pad_zero_gradient_ghost_cells(ConstArrayView cells, ArrayView padded)
{
  if (cells.extent(0) == 0U) {
    return;
  }

  for (std::size_t ghost = 0; ghost < kGhostWidth; ++ghost) {
    for (std::size_t component = 0; component < kStateWidth; ++component) {
      padded(ghost, component)                         = cells(0, component);
      padded(padded.extent(0) - 1U - ghost, component) = cells(cells.extent(0) - 1U, component);
    }
  }

  for (std::size_t index = 0; index < cells.extent(0); ++index) {
    for (std::size_t component = 0; component < kStateWidth; ++component) {
      padded(index + kGhostWidth, component) = cells(index, component);
    }
  }
}

std::vector<double> cell_centers(std::size_t nx, double x_left, double x_right)
{
  if (nx == 0U) {
    return {};
  }

  if (!(x_right > x_left)) {
    throw std::runtime_error("x_right must be greater than x_left");
  }

  const double        dx = (x_right - x_left) / static_cast<double>(nx);
  std::vector<double> centers(nx);
  for (std::size_t index = 0; index < nx; ++index) {
    centers[index] = x_left + (static_cast<double>(index) + 0.5) * dx;
  }

  return centers;
}

void compute_semidiscrete_rhs(ConstArrayView conservative_cells, ArrayView rhs, double dx,
                              double bx, double gamma)
{
  SolverWorkspace workspace(conservative_cells.extent(0));
  compute_semidiscrete_rhs_inplace(conservative_cells, dx, bx, gamma, workspace, rhs);
}

void ssp_rk3_step(ConstArrayView conservative_cells, ArrayView output, double dt, double dx,
                  double bx, double gamma)
{
  SolverWorkspace workspace(conservative_cells.extent(0));
  ssp_rk3_step_inplace(conservative_cells, dt, dx, bx, gamma, workspace, output);
}

void evolve_ssp_rk3_fixed_dt(ConstArrayView conservative_cells, ArrayView output, double t_final,
                             double dt, double dx, double bx, double gamma)
{
  if (conservative_cells.extent(0) == 0U || t_final < 0.0 || dt <= 0.0) {
    copy_cells(conservative_cells, output);
    return;
  }

  const std::size_t   state_size = conservative_cells.extent(0) * kStateWidth;
  std::vector<double> evolved_buffer(state_size);
  std::vector<double> stage_buffer(state_size);

  ArrayView evolved_state(evolved_buffer.data(), conservative_cells.extent(0), kStateWidth);
  ArrayView stage_state(stage_buffer.data(), conservative_cells.extent(0), kStateWidth);

  copy_cells(conservative_cells, evolved_state);

  SolverWorkspace workspace(conservative_cells.extent(0));
  double          elapsed_time = 0.0;
  while (elapsed_time < t_final) {
    const double remaining_time = t_final - elapsed_time;
    const double step_dt        = std::min(dt, remaining_time);
    ssp_rk3_step_inplace(evolved_state, step_dt, dx, bx, gamma, workspace, stage_state);
    std::swap(evolved_buffer, stage_buffer);
    evolved_state = ArrayView(evolved_buffer.data(), conservative_cells.extent(0), kStateWidth);
    stage_state   = ArrayView(stage_buffer.data(), conservative_cells.extent(0), kStateWidth);
    elapsed_time  = (step_dt < dt) ? t_final : (elapsed_time + step_dt);
  }

  copy_cells(evolved_state, output);
}

} // namespace mhd1d
