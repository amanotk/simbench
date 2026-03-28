#include "mhd1d.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <utility>

namespace mhd1d
{

namespace
{

constexpr double      kDefaultGamma  = 2.0;
constexpr double      kDefaultBx     = 0.75;
constexpr double      kDefaultDt     = 5.0e-4;
constexpr double      kDefaultTFinal = 0.1;
constexpr std::size_t kDefaultNx     = 400;
constexpr std::size_t kGhostWidth    = 2U;
constexpr double      kHlldEps       = 1.0e-40;

double sign_unit(double x)
{
  return (x >= 0.0) ? 1.0 : -1.0;
}

double minmod3(double first, double second, double third)
{
  if (first * second > 0.0 && first * third > 0.0) {
    const double limited = std::min({std::abs(first), std::abs(second), std::abs(third)});
    return std::copysign(limited, first);
  }

  return 0.0;
}

} // namespace

namespace
{

std::vector<StateVector>
conservative_profile_to_primitive_profile(const std::vector<StateVector>& conservative_cells,
                                          double bx, double gamma)
{
  std::vector<StateVector> primitive_cells(conservative_cells.size());
  for (std::size_t index = 0; index < conservative_cells.size(); ++index) {
    primitive_cells[index] = conservative_to_primitive(conservative_cells[index], bx, gamma);
  }

  return primitive_cells;
}

} // namespace

ProblemConfig make_brio_wu_example()
{
  return ProblemConfig{
      kDefaultNx,
      0.0,
      1.0,
      0.5,
      kDefaultDt,
      kDefaultTFinal,
      kDefaultGamma,
      kDefaultBx,
      StateVector{1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0},
      StateVector{0.125, 0.0, 0.0, 0.0, 0.1, -1.0, 0.0},
  };
}

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

std::vector<StateVector> mc2_slopes(const std::vector<StateVector>& primitive_cells)
{
  if (primitive_cells.size() < 3U) {
    throw std::runtime_error("primitive_cells must contain at least three cells");
  }

  std::vector<StateVector> slopes(primitive_cells.size());
  for (std::size_t index = 1; index + 1U < primitive_cells.size(); ++index) {
    const StateVector& left_cell     = primitive_cells[index - 1U];
    const StateVector& center_cell   = primitive_cells[index];
    const StateVector& right_cell    = primitive_cells[index + 1U];
    StateVector&       limited_slope = slopes[index];

    for (std::size_t component = 0; component < kStateWidth; ++component) {
      const double left_difference     = center_cell[component] - left_cell[component];
      const double right_difference    = right_cell[component] - center_cell[component];
      const double centered_difference = 0.5 * (right_cell[component] - left_cell[component]);
      limited_slope[component] =
          minmod3(2.0 * left_difference, centered_difference, 2.0 * right_difference);
    }
  }

  return slopes;
}

std::pair<std::vector<StateVector>, std::vector<StateVector>>
reconstruct_mc2_interfaces(const std::vector<StateVector>& primitive_cells)
{
  const std::vector<StateVector> slopes          = mc2_slopes(primitive_cells);
  const std::size_t              interface_count = primitive_cells.size() - 1U;

  std::vector<StateVector> left_states(interface_count);
  std::vector<StateVector> right_states(interface_count);

  for (std::size_t index = 0; index < interface_count; ++index) {
    for (std::size_t component = 0; component < kStateWidth; ++component) {
      left_states[index][component] =
          primitive_cells[index][component] + 0.5 * slopes[index][component];
      right_states[index][component] =
          primitive_cells[index + 1U][component] - 0.5 * slopes[index + 1U][component];
    }
  }

  return {left_states, right_states};
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
  const double sign1_l    = sign_unit(std::abs(temp_fst_l) - kHlldEps);
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
  const double sign1_r    = sign_unit(std::abs(temp_fst_r) - kHlldEps);
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
  const double signbx   = sign_unit(bxs);
  const double sign1_b  = sign_unit(abbx - kHlldEps);
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

  const double sign1       = sign_unit(sm);
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

std::vector<StateVector> pad_zero_gradient_ghost_cells(const std::vector<StateVector>& cells)
{
  if (cells.empty()) {
    return {};
  }

  std::vector<StateVector> padded;
  padded.reserve(cells.size() + 4U);
  padded.insert(padded.end(), 2U, cells.front());
  padded.insert(padded.end(), cells.begin(), cells.end());
  padded.insert(padded.end(), 2U, cells.back());
  return padded;
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

std::vector<StateVector> brio_wu_initial_profile(const ProblemConfig& problem)
{
  const std::vector<double> centers = cell_centers(problem.nx, problem.x_left, problem.x_right);
  std::vector<StateVector>  profile(problem.nx);

  for (std::size_t index = 0; index < centers.size(); ++index) {
    profile[index] = (centers[index] < problem.discontinuity_x) ? problem.left_primitive
                                                                : problem.right_primitive;
  }

  return profile;
}

std::vector<StateVector> run_full_simulation(const ProblemConfig& problem)
{
  if (problem.nx == 0U) {
    return {};
  }

  const std::vector<StateVector> initial_primitive_profile = brio_wu_initial_profile(problem);
  std::vector<StateVector>       conservative_cells(initial_primitive_profile.size());
  for (std::size_t index = 0; index < initial_primitive_profile.size(); ++index) {
    conservative_cells[index] =
        primitive_to_conservative(initial_primitive_profile[index], problem.bx, problem.gamma);
  }

  const double dx = (problem.x_right - problem.x_left) / static_cast<double>(problem.nx);
  const std::vector<StateVector> evolved_conservative_cells = evolve_ssp_rk3_fixed_dt(
      conservative_cells, problem.t_final, problem.dt, dx, problem.bx, problem.gamma);

  std::vector<StateVector> final_primitive_profile(evolved_conservative_cells.size());
  for (std::size_t index = 0; index < evolved_conservative_cells.size(); ++index) {
    final_primitive_profile[index] =
        conservative_to_primitive(evolved_conservative_cells[index], problem.bx, problem.gamma);
  }

  return final_primitive_profile;
}

std::vector<StateVector>
compute_semidiscrete_rhs(const std::vector<StateVector>& conservative_cells, double bx,
                         double gamma)
{
  if (conservative_cells.empty()) {
    throw std::runtime_error("conservative_cells must contain at least one cell");
  }

  const double dx = 1.0 / static_cast<double>(conservative_cells.size());
  return compute_semidiscrete_rhs(conservative_cells, dx, bx, gamma);
}

std::vector<StateVector>
compute_semidiscrete_rhs(const std::vector<StateVector>& conservative_cells, double dx, double bx,
                         double gamma)
{
  if (conservative_cells.empty()) {
    throw std::runtime_error("conservative_cells must contain at least one cell");
  }

  if (dx <= 0.0) {
    throw std::runtime_error("dx must be positive");
  }

  const std::vector<StateVector> padded_conservative =
      pad_zero_gradient_ghost_cells(conservative_cells);
  const std::vector<StateVector> padded_primitive =
      conservative_profile_to_primitive_profile(padded_conservative, bx, gamma);
  const std::pair<std::vector<StateVector>, std::vector<StateVector>> interface_states =
      reconstruct_mc2_interfaces(padded_primitive);

  const std::vector<StateVector>& left_interface_states  = interface_states.first;
  const std::vector<StateVector>& right_interface_states = interface_states.second;

  std::vector<StateVector> interface_fluxes(left_interface_states.size());
  for (std::size_t index = 0; index < left_interface_states.size(); ++index) {
    interface_fluxes[index] = hlld_flux_from_primitive(left_interface_states[index],
                                                       right_interface_states[index], bx, gamma);
  }

  std::vector<StateVector> rhs(conservative_cells.size());
  for (std::size_t index = 0; index < conservative_cells.size(); ++index) {
    for (std::size_t component = 0; component < kStateWidth; ++component) {
      rhs[index][component] = -(interface_fluxes[index + kGhostWidth][component] -
                                interface_fluxes[index + kGhostWidth - 1U][component]) /
                              dx;
    }
  }

  return rhs;
}

std::vector<StateVector> ssp_rk3_step(const std::vector<StateVector>& conservative_cells, double dt,
                                      double bx, double gamma)
{
  if (conservative_cells.empty()) {
    throw std::runtime_error("conservative_cells must contain at least one cell");
  }

  const double dx = 1.0 / static_cast<double>(conservative_cells.size());
  return ssp_rk3_step(conservative_cells, dt, dx, bx, gamma);
}

std::vector<StateVector> ssp_rk3_step(const std::vector<StateVector>& conservative_cells, double dt,
                                      double dx, double bx, double gamma)
{
  if (conservative_cells.empty()) {
    throw std::runtime_error("conservative_cells must contain at least one cell");
  }

  if (dt <= 0.0) {
    throw std::runtime_error("dt must be positive");
  }

  std::vector<StateVector>       first_stage = conservative_cells;
  const std::vector<StateVector> first_rhs =
      compute_semidiscrete_rhs(conservative_cells, dx, bx, gamma);
  for (std::size_t index = 0; index < first_stage.size(); ++index) {
    for (std::size_t component = 0; component < kStateWidth; ++component) {
      first_stage[index][component] += dt * first_rhs[index][component];
    }
  }

  std::vector<StateVector>       second_stage = conservative_cells;
  const std::vector<StateVector> second_rhs = compute_semidiscrete_rhs(first_stage, dx, bx, gamma);
  for (std::size_t index = 0; index < second_stage.size(); ++index) {
    for (std::size_t component = 0; component < kStateWidth; ++component) {
      second_stage[index][component] =
          0.75 * conservative_cells[index][component] +
          0.25 * (first_stage[index][component] + dt * second_rhs[index][component]);
    }
  }

  const std::vector<StateVector> third_rhs  = compute_semidiscrete_rhs(second_stage, dx, bx, gamma);
  std::vector<StateVector>       next_stage = conservative_cells;
  for (std::size_t index = 0; index < next_stage.size(); ++index) {
    for (std::size_t component = 0; component < kStateWidth; ++component) {
      next_stage[index][component] =
          (1.0 / 3.0) * conservative_cells[index][component] +
          (2.0 / 3.0) * (second_stage[index][component] + dt * third_rhs[index][component]);
    }
  }

  return next_stage;
}

std::vector<StateVector> evolve_ssp_rk3_fixed_dt(const std::vector<StateVector>& conservative_cells,
                                                 double t_final, double dt, double bx, double gamma)
{
  if (conservative_cells.empty()) {
    throw std::runtime_error("conservative_cells must contain at least one cell");
  }

  const double dx = 1.0 / static_cast<double>(conservative_cells.size());
  return evolve_ssp_rk3_fixed_dt(conservative_cells, t_final, dt, dx, bx, gamma);
}

std::vector<StateVector> evolve_ssp_rk3_fixed_dt(const std::vector<StateVector>& conservative_cells,
                                                 double t_final, double dt, double dx, double bx,
                                                 double gamma)
{
  if (conservative_cells.empty()) {
    throw std::runtime_error("conservative_cells must contain at least one cell");
  }

  if (t_final < 0.0) {
    throw std::runtime_error("t_final must be non-negative");
  }

  if (dt <= 0.0) {
    throw std::runtime_error("dt must be positive");
  }

  std::vector<StateVector> evolved_state = conservative_cells;
  double                   elapsed_time  = 0.0;
  while (elapsed_time < t_final) {
    const double remaining_time = t_final - elapsed_time;
    const double step_dt        = std::min(dt, remaining_time);
    evolved_state               = ssp_rk3_step(evolved_state, step_dt, dx, bx, gamma);
    elapsed_time                = (step_dt < dt) ? t_final : (elapsed_time + step_dt);
  }

  return evolved_state;
}

} // namespace mhd1d
