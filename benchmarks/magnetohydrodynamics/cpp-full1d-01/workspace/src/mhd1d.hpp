#pragma once

#include <array>
#include <vector>

#include <experimental/mdspan>

namespace mhd1d
{

namespace stdex = std::experimental;

constexpr int N_Component = 7;
constexpr int N_margin    = 1;

using StateVector = std::array<double, N_Component>;
using ArrayView1D = stdex::mdspan<double, stdex::dextents<int, 1>, stdex::layout_right>;
using ArrayView2D = stdex::mdspan<double, stdex::dextents<int, 2>, stdex::layout_right>;

struct SolverWorkspace {
  explicit SolverWorkspace(int nx, double gamma, double bx)
      : Nx(nx), Lbx(N_margin), Ubx(N_margin + nx - 1), dx(1.0 / static_cast<double>(nx)),
        gamma(gamma), bx(bx), storage(Nx + 2 * N_margin, N_Component)
  {
    init_views(Nx + 2 * N_margin, N_Component);

    for (int ix = Lbx; ix <= Ubx; ++ix) {
      x(ix) = (static_cast<double>(ix - Lbx) + 0.5) * dx;
    }
  }

  int    Nx;
  int    Lbx;
  int    Ubx;
  double dx;
  double gamma;
  double bx;

  ArrayView1D x;
  ArrayView2D uc;
  ArrayView2D up;
  ArrayView2D up_l;
  ArrayView2D up_r;
  ArrayView2D rhs;
  ArrayView2D prev;
  ArrayView2D flux;

private:
  void init_views(int n_grid, int n_component)
  {
    x    = ArrayView1D(storage.x.data(), n_grid);
    uc   = ArrayView2D(storage.uc.data(), n_grid, n_component);
    up   = ArrayView2D(storage.up.data(), n_grid, n_component);
    up_l = ArrayView2D(storage.up_l.data(), n_grid, n_component);
    up_r = ArrayView2D(storage.up_r.data(), n_grid, n_component);
    rhs  = ArrayView2D(storage.rhs.data(), n_grid, n_component);
    prev = ArrayView2D(storage.prev.data(), n_grid, n_component);
    flux = ArrayView2D(storage.flux.data(), n_grid, n_component);
  }

  struct Storage {
    explicit Storage(int n_grid, int n_component)
        : x(n_grid), uc(n_grid * n_component), up(n_grid * n_component), up_l(n_grid * n_component),
          up_r(n_grid * n_component), rhs(n_grid * n_component), prev(n_grid * n_component),
          flux(n_grid * n_component)
    {
    }

    std::vector<double> x;
    std::vector<double> uc;
    std::vector<double> up;
    std::vector<double> up_l;
    std::vector<double> up_r;
    std::vector<double> rhs;
    std::vector<double> prev;
    std::vector<double> flux;
  };

  Storage storage;
};

void evolve_ssp_rk3(SolverWorkspace& workspace, double dt, double t_final);

} // namespace mhd1d
