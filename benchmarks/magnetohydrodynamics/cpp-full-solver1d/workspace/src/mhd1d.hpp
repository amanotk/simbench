#pragma once

#include <array>
#include <cstddef>
#include <utility>
#include <vector>

#include <experimental/mdspan>

namespace mhd1d
{

namespace stdex = std::experimental;

constexpr std::size_t kStateWidth = 7;
constexpr std::size_t kGhostWidth = 2;

using StateVector    = std::array<double, kStateWidth>;
using ArrayView      = stdex::mdspan<double, stdex::dextents<std::size_t, 2>>;
using ConstArrayView = stdex::mdspan<const double, stdex::dextents<std::size_t, 2>>;

struct SolverWorkspace {
  explicit SolverWorkspace(std::size_t nx, double x_left = 0.0, double x_right = 1.0,
                           double dt = 5.0e-4, double t_final = 0.1, double gamma = 2.0,
                           double bx = 0.75)
      : Nx(nx), Lbx(kGhostWidth), Ubx(kGhostWidth + nx - 1U), x_left(x_left), x_right(x_right),
        dx(nx == 0U ? 0.0 : (x_right - x_left) / static_cast<double>(nx)), dt(dt), t_final(t_final),
        gamma(gamma), bx(bx)
  {
    const std::size_t Nx_total    = Nx + 2U * kGhostWidth;
    const std::size_t interface_n = Nx_total - 1U;
    const std::size_t padded_size = Nx_total * kStateWidth;
    const std::size_t state_size  = Nx * kStateWidth;

    buf_conservative.resize(padded_size);
    buf_primitive.resize(padded_size);
    buf_slopes.resize(padded_size);
    buf_primitive_left.resize(interface_n * kStateWidth);
    buf_primitive_right.resize(interface_n * kStateWidth);
    buf_rhs1.resize(state_size);
    buf_rhs2.resize(state_size);
    buf_rhs3.resize(state_size);
    buf_stage1.resize(state_size);
    buf_stage2.resize(state_size);
    buf_stage3.resize(state_size);

    conservative    = ArrayView(buf_conservative.data(), Nx_total, kStateWidth);
    primitive       = ArrayView(buf_primitive.data(), Nx_total, kStateWidth);
    slopes          = ArrayView(buf_slopes.data(), Nx_total, kStateWidth);
    primitive_left  = ArrayView(buf_primitive_left.data(), interface_n, kStateWidth);
    primitive_right = ArrayView(buf_primitive_right.data(), interface_n, kStateWidth);
    rhs1            = ArrayView(buf_rhs1.data(), Nx, kStateWidth);
    rhs2            = ArrayView(buf_rhs2.data(), Nx, kStateWidth);
    rhs3            = ArrayView(buf_rhs3.data(), Nx, kStateWidth);
    stage1          = ArrayView(buf_stage1.data(), Nx, kStateWidth);
    stage2          = ArrayView(buf_stage2.data(), Nx, kStateWidth);
    stage3          = ArrayView(buf_stage3.data(), Nx, kStateWidth);
  }

  using ArrayView = stdex::mdspan<double, stdex::dextents<std::size_t, 2>>;

  std::size_t Nx;  // number of grids for the physical domain (excluding the ghost cells)
  std::size_t Lbx; // lower bound of the physical domain in padded indexing
  std::size_t Ubx; // upper bound of the physical domain in padded indexing
  double      x_left;
  double      x_right;
  double      dx;
  double      dt;
  double      t_final;
  double      gamma;
  double      bx;

  // buffer
  std::vector<double> buf_conservative;
  std::vector<double> buf_primitive;
  std::vector<double> buf_slopes;
  std::vector<double> buf_primitive_left;
  std::vector<double> buf_primitive_right;
  std::vector<double> buf_rhs1;
  std::vector<double> buf_rhs2;
  std::vector<double> buf_rhs3;
  std::vector<double> buf_stage1;
  std::vector<double> buf_stage2;
  std::vector<double> buf_stage3;

  // view
  ArrayView conservative;
  ArrayView primitive;
  ArrayView slopes;
  ArrayView primitive_left;
  ArrayView primitive_right;
  ArrayView rhs1;
  ArrayView rhs2;
  ArrayView rhs3;
  ArrayView stage1;
  ArrayView stage2;
  ArrayView stage3;
};

StateVector primitive_to_conservative(const StateVector& primitive, double bx, double gamma);

StateVector conservative_to_primitive(const StateVector& conservative, double bx, double gamma);

void primitive_profile_to_conservative(ConstArrayView primitive_cells, ArrayView conservative_cells,
                                       double bx = 0.75, double gamma = 2.0);

void conservative_profile_to_primitive(ConstArrayView conservative_cells, ArrayView primitive_cells,
                                       double bx = 0.75, double gamma = 2.0);

StateVector hlld_flux_from_primitive(const StateVector& left, const StateVector& right, double bx,
                                     double gamma);

std::vector<double> cell_centers(std::size_t nx, double x_left, double x_right);

void pad_zero_gradient_ghost_cells(ConstArrayView cells, ArrayView padded);

void mc2_slopes(ConstArrayView primitive_cells, ArrayView slopes);

void reconstruct_mc2_interfaces(ConstArrayView primitive_cells, ArrayView left_states,
                                ArrayView right_states);

void compute_semidiscrete_rhs(ConstArrayView conservative_cells, ArrayView rhs, double dx,
                              double bx = 0.75, double gamma = 2.0);

void ssp_rk3_step(ConstArrayView conservative_cells, ArrayView output, double dt, double dx,
                  double bx = 0.75, double gamma = 2.0);

void evolve_ssp_rk3_fixed_dt(ConstArrayView conservative_cells, ArrayView output, double t_final,
                             double dt, double dx, double bx = 0.75, double gamma = 2.0);

} // namespace mhd1d
