#include <catch2/catch_test_macros.hpp>

#include <cmath>
#include <vector>

#include "mhd1d.hpp"

TEST_CASE("set_boundary duplicates edge states on both sides", "[mhd1d][boundary]")
{
  std::vector<double>      padded_buffer(4 * mhd1d::N_Component, 0.0);
  const mhd1d::ArrayView2D padded(padded_buffer.data(), 4, mhd1d::N_Component);

  padded(1, 0) = 1.2;
  padded(2, 0) = 1.4;

  mhd1d::set_boundary_lb(padded, padded, 1);
  mhd1d::set_boundary_ub(padded, padded, 2);

  REQUIRE(padded(0, 0) == padded(1, 0));
  REQUIRE(padded(3, 0) == padded(2, 0));
}

TEST_CASE("compute_flux_hlld fills finite interface values", "[mhd1d][flux]")
{
  mhd1d::SolverWorkspace workspace(4, 2.0, 0.75);

  for (int ix = workspace.Lbx; ix <= workspace.Ubx; ++ix) {
    workspace.up_l(ix, 0) = 1.0;
    workspace.up_l(ix, 1) = 0.0;
    workspace.up_l(ix, 2) = 0.0;
    workspace.up_l(ix, 3) = 0.0;
    workspace.up_l(ix, 4) = 1.0;
    workspace.up_l(ix, 5) = 0.5;
    workspace.up_l(ix, 6) = 0.0;

    workspace.up_r(ix, 0) = 0.9;
    workspace.up_r(ix, 1) = 0.0;
    workspace.up_r(ix, 2) = 0.0;
    workspace.up_r(ix, 3) = 0.0;
    workspace.up_r(ix, 4) = 0.9;
    workspace.up_r(ix, 5) = 0.4;
    workspace.up_r(ix, 6) = 0.0;
  }

  mhd1d::set_boundary_lb(workspace.up_l, workspace.up_l, workspace.Lbx);
  mhd1d::set_boundary_ub(workspace.up_l, workspace.up_l, workspace.Ubx);
  mhd1d::set_boundary_lb(workspace.up_r, workspace.up_r, workspace.Lbx);
  mhd1d::set_boundary_ub(workspace.up_r, workspace.up_r, workspace.Ubx);

  mhd1d::compute_flux_hlld(workspace, 0.75, 2.0);

  for (int ix = workspace.Lbx - 1; ix <= workspace.Ubx + 1; ++ix) {
    REQUIRE(std::isfinite(workspace.flux(ix, 0)));
  }
}
