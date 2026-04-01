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

using StateVector = std::array<double, kStateWidth>;
using ArrayView1D = stdex::mdspan<double, stdex::dextents<std::size_t, 1>>;
using ArrayView2D = stdex::mdspan<double, stdex::dextents<std::size_t, 2>>;

struct SolverWorkspace {
  explicit SolverWorkspace(std::size_t nx, double gamma, double bx)
      : Nx(nx), Lbx(kGhostWidth), Ubx(kGhostWidth + nx - 1U),
        dx(nx == 0U ? 0.0 : 1.0 / static_cast<double>(nx)), gamma(gamma), bx(bx)
  {
    const std::size_t Nx_total    = Nx + 2U * kGhostWidth;
    const std::size_t padded_size = Nx_total * kStateWidth;

    buf_conservative.resize(padded_size);
    buf_primitive.resize(padded_size);
    buf_slopes.resize(padded_size);
    buf_primitive_left.resize(padded_size);
    buf_primitive_right.resize(padded_size);
    buf_rhs1.resize(padded_size);
    buf_stage1.resize(padded_size);
    buf_flux.resize(padded_size);
    buf_x.resize(Nx_total);

    conservative    = ArrayView2D(buf_conservative.data(), Nx_total, kStateWidth);
    primitive       = ArrayView2D(buf_primitive.data(), Nx_total, kStateWidth);
    slopes          = ArrayView2D(buf_slopes.data(), Nx_total, kStateWidth);
    primitive_left  = ArrayView2D(buf_primitive_left.data(), Nx_total, kStateWidth);
    primitive_right = ArrayView2D(buf_primitive_right.data(), Nx_total, kStateWidth);
    rhs1            = ArrayView2D(buf_rhs1.data(), Nx_total, kStateWidth);
    stage1          = ArrayView2D(buf_stage1.data(), Nx_total, kStateWidth);
    flux            = ArrayView2D(buf_flux.data(), Nx_total, kStateWidth);
    x               = ArrayView1D(buf_x.data(), Nx_total);

    for (std::size_t i = 0; i < Nx_total; ++i) {
      x(i) = (static_cast<double>(i) + 0.5) * dx;
    }
  }

  std::size_t Nx;  // number of grids for the physical domain (excluding the ghost cells)
  std::size_t Lbx; // lower bound of the physical domain in padded indexing
  std::size_t Ubx; // upper bound of the physical domain in padded indexing
  double      dx;
  double      gamma;
  double      bx;

  // buffer
  std::vector<double> buf_conservative;
  std::vector<double> buf_primitive;
  std::vector<double> buf_slopes;
  std::vector<double> buf_primitive_left;
  std::vector<double> buf_primitive_right;
  std::vector<double> buf_rhs1;
  std::vector<double> buf_stage1;
  std::vector<double> buf_flux;
  std::vector<double> buf_x;

  // view
  ArrayView2D conservative;
  ArrayView2D primitive;
  ArrayView2D slopes;
  ArrayView2D primitive_left;
  ArrayView2D primitive_right;
  ArrayView2D rhs1;
  ArrayView2D stage1;
  ArrayView2D flux;
  ArrayView1D x;
};

StateVector primitive_to_conservative(const StateVector& primitive, double bx, double gamma);

StateVector conservative_to_primitive(const StateVector& conservative, double bx, double gamma);

void primitive_profile_to_conservative(ArrayView2D primitive_cells, ArrayView2D conservative_cells,
                                       double bx, double gamma);

StateVector hlld_flux_from_primitive(const StateVector& left, const StateVector& right, double bx,
                                     double gamma);

void set_boundary(ArrayView2D u, std::size_t lbx, std::size_t ubx);

void reconstruct_mc2(SolverWorkspace& workspace);

void compute_flux_hlld(SolverWorkspace& workspace, double bx, double gamma);

void compute_rhs(SolverWorkspace& workspace);

void push_ssp_rk3(SolverWorkspace& workspace, double dt);

void evolve_ssp_rk3(SolverWorkspace& workspace, double dt, double t_final);

} // namespace mhd1d
