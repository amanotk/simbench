#pragma once

#include <array>
#include <cstddef>
#include <utility>
#include <vector>

namespace mhd1d
{

constexpr std::size_t kStateWidth = 7;

using StateVector = std::array<double, kStateWidth>;

struct ProblemConfig {
  std::size_t nx              = 0;
  double      x_left          = 0.0;
  double      x_right         = 1.0;
  double      discontinuity_x = 0.5;
  double      dt              = 0.0;
  double      t_final         = 0.0;
  double      gamma           = 0.0;
  double      bx              = 0.0;
  StateVector left_primitive{};
  StateVector right_primitive{};
};

ProblemConfig make_brio_wu_example();

StateVector primitive_to_conservative(const StateVector& primitive, double bx, double gamma);

StateVector conservative_to_primitive(const StateVector& conservative, double bx, double gamma);

std::vector<StateVector> mc2_slopes(const std::vector<StateVector>& primitive_cells);

std::pair<std::vector<StateVector>, std::vector<StateVector>>
reconstruct_mc2_interfaces(const std::vector<StateVector>& primitive_cells);

StateVector hlld_flux_from_primitive(const StateVector& left, const StateVector& right, double bx,
                                     double gamma);

std::vector<double> cell_centers(std::size_t nx, double x_left, double x_right);

std::vector<StateVector> pad_zero_gradient_ghost_cells(const std::vector<StateVector>& cells);

std::vector<StateVector> brio_wu_initial_profile(const ProblemConfig& problem);

std::vector<StateVector> run_full_simulation(const ProblemConfig& problem);

std::vector<StateVector>
compute_semidiscrete_rhs(const std::vector<StateVector>& conservative_cells, double bx = 0.75,
                         double gamma = 2.0);

std::vector<StateVector>
compute_semidiscrete_rhs(const std::vector<StateVector>& conservative_cells, double dx, double bx,
                         double gamma);

std::vector<StateVector> ssp_rk3_step(const std::vector<StateVector>& conservative_cells, double dt,
                                      double bx = 0.75, double gamma = 2.0);

std::vector<StateVector> ssp_rk3_step(const std::vector<StateVector>& conservative_cells, double dt,
                                      double dx, double bx, double gamma);

std::vector<StateVector> evolve_ssp_rk3_fixed_dt(const std::vector<StateVector>& conservative_cells,
                                                 double t_final, double dt, double bx = 0.75,
                                                 double gamma = 2.0);

std::vector<StateVector> evolve_ssp_rk3_fixed_dt(const std::vector<StateVector>& conservative_cells,
                                                 double t_final, double dt, double dx, double bx,
                                                 double gamma);

} // namespace mhd1d
