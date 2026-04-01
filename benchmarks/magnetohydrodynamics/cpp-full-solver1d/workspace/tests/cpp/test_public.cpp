#include <catch2/catch_test_macros.hpp>

#include <cmath>
#include <vector>

#include "mhd1d.hpp"

namespace
{

constexpr double kTolerance = 1.0e-12;

mhd1d::StateVector row_to_state(mhd1d::ArrayView2D cells, std::size_t row)
{
  mhd1d::StateVector state{};
  for (std::size_t component = 0; component < mhd1d::kStateWidth; ++component) {
    state[component] = cells(row, component);
  }
  return state;
}

void state_to_row(mhd1d::ArrayView2D cells, std::size_t row, const mhd1d::StateVector& state)
{
  for (std::size_t component = 0; component < mhd1d::kStateWidth; ++component) {
    cells(row, component) = state[component];
  }
}

void require_state_vector_close(const mhd1d::StateVector& actual,
                                const mhd1d::StateVector& expected)
{
  for (std::size_t component = 0; component < mhd1d::kStateWidth; ++component) {
    REQUIRE(std::fabs(actual[component] - expected[component]) <= kTolerance);
  }
}

} // namespace

TEST_CASE("primitive_to_conservative converts a known state", "[mhd1d][conversion]")
{
  const double bx     = 0.75;
  const double gamma  = 2.0;
  const auto   state  = mhd1d::StateVector{1.5, 2.0, -1.0, 0.5, 3.0, 0.25, -0.5};
  const auto   actual = mhd1d::primitive_to_conservative(state, bx, gamma);

  const auto expected = mhd1d::StateVector{1.5, 3.0, -1.5, 0.75, 7.375, 0.25, -0.5};
  require_state_vector_close(actual, expected);
}

TEST_CASE("conservative_to_primitive converts a known state", "[mhd1d][conversion]")
{
  const double bx     = 0.75;
  const double gamma  = 2.0;
  const auto   state  = mhd1d::StateVector{1.5, 3.0, -1.5, 0.75, 7.375, 0.25, -0.5};
  const auto   actual = mhd1d::conservative_to_primitive(state, bx, gamma);

  const auto expected = mhd1d::StateVector{1.5, 2.0, -1.0, 0.5, 3.0, 0.25, -0.5};
  require_state_vector_close(actual, expected);
}

TEST_CASE("primitive and conservative states round-trip", "[mhd1d][conversion]")
{
  const double bx    = 0.75;
  const double gamma = 2.0;
  const auto   input = mhd1d::StateVector{0.875, -1.25, 0.5, 0.75, 2.125, -0.2, 0.35};

  const auto conservative = mhd1d::primitive_to_conservative(input, bx, gamma);
  const auto output       = mhd1d::conservative_to_primitive(conservative, bx, gamma);

  require_state_vector_close(output, input);
}

TEST_CASE("reconstruct_mc2 preserves a constant primitive state exactly",
          "[mhd1d][reconstruction]")
{
  mhd1d::SolverWorkspace workspace(4, 2.0, 0.75);
  const auto             constant_state = mhd1d::StateVector{0.9, 0.3, -0.2, 0.1, 1.8, -0.45, 0.6};

  for (std::size_t index = 0; index < workspace.conservative.extent(0); ++index) {
    state_to_row(workspace.primitive, index, constant_state);
  }

  mhd1d::reconstruct_mc2(workspace);

  for (std::size_t index = workspace.Lbx; index <= workspace.Ubx; ++index) {
    require_state_vector_close(row_to_state(workspace.primitive_left, index), constant_state);
    require_state_vector_close(row_to_state(workspace.primitive_right, index), constant_state);
  }
}

TEST_CASE("hlld_flux_from_primitive matches the physical flux for identical states",
          "[mhd1d][flux]")
{
  const double bx     = 0.75;
  const double gamma  = 2.0;
  const auto   state  = mhd1d::StateVector{1.4, -0.6, 0.25, 0.1, 1.9, -0.35, 0.5};
  const auto   actual = mhd1d::hlld_flux_from_primitive(state, state, bx, gamma);

  const double rho = state[0];
  const double u   = state[1];
  const double v   = state[2];
  const double w   = state[3];
  const double p   = state[4];
  const double by  = state[5];
  const double bz  = state[6];
  const double bx2 = bx * bx;
  const double pt  = p + 0.5 * (bx2 + by * by + bz * bz);
  const double e =
      p / (gamma - 1.0) + 0.5 * rho * (u * u + v * v + w * w) + 0.5 * (bx2 + by * by + bz * bz);

  const auto expected = mhd1d::StateVector{
      rho * u,
      rho * u * u + pt - bx2,
      rho * u * v - bx * by,
      rho * u * w - bx * bz,
      u * (e + pt - bx2) - bx * (v * by + w * bz),
      by * u - bx * v,
      bz * u - bx * w,
  };

  require_state_vector_close(actual, expected);
}

TEST_CASE("set_boundary duplicates edge states on both sides", "[mhd1d][boundary]")
{
  std::vector<double>    padded_buffer(7 * mhd1d::kStateWidth, 0.0);
  const mhd1d::ArrayView2D padded(padded_buffer.data(), 7, mhd1d::kStateWidth);
  state_to_row(padded, 2, mhd1d::StateVector{1.0, 0.5, -0.25, 0.125, 2.0, 0.1, -0.05});
  state_to_row(padded, 3, mhd1d::StateVector{1.2, 0.6, -0.2, 0.15, 2.2, 0.12, -0.02});
  state_to_row(padded, 4, mhd1d::StateVector{1.4, 0.7, -0.15, 0.175, 2.4, 0.14, 0.01});

  mhd1d::set_boundary(padded, 2, 4);

  require_state_vector_close(row_to_state(padded, 0), row_to_state(padded, 2));
  require_state_vector_close(row_to_state(padded, 1), row_to_state(padded, 2));
  require_state_vector_close(row_to_state(padded, 2), row_to_state(padded, 2));
  require_state_vector_close(row_to_state(padded, 3), row_to_state(padded, 3));
  require_state_vector_close(row_to_state(padded, 4), row_to_state(padded, 4));
  require_state_vector_close(row_to_state(padded, 5), row_to_state(padded, 4));
  require_state_vector_close(row_to_state(padded, 6), row_to_state(padded, 4));
}

TEST_CASE("set_boundary handles a single interior cell", "[mhd1d][boundary]")
{
  std::vector<double>    padded_buffer(5 * mhd1d::kStateWidth, 0.0);
  const mhd1d::ArrayView2D padded(padded_buffer.data(), 5, mhd1d::kStateWidth);
  const auto             cell = mhd1d::StateVector{1.5, -0.75, 0.25, 0.0, 3.5, -0.1, 0.2};
  state_to_row(padded, 2, cell);
  mhd1d::set_boundary(padded, 2, 2);

  for (std::size_t index = 0; index < 5; ++index) {
    require_state_vector_close(row_to_state(padded, index), cell);
  }
}

TEST_CASE("set_boundary overwrites ghost cells from interior boundary",
          "[mhd1d][boundary]")
{
  std::vector<double>    cells_buffer(6 * mhd1d::kStateWidth, 0.0);
  const mhd1d::ArrayView2D cells(cells_buffer.data(), 6, mhd1d::kStateWidth);

  state_to_row(cells, 0, mhd1d::StateVector{-1.0, -1.0, -1.0, -1.0, -1.0, -1.0, -1.0});
  state_to_row(cells, 1, mhd1d::StateVector{1.0, 0.1, 0.2, 0.3, 2.0, 0.4, 0.5});
  state_to_row(cells, 2, mhd1d::StateVector{2.0, 0.2, 0.3, 0.4, 2.1, 0.5, 0.6});
  state_to_row(cells, 3, mhd1d::StateVector{3.0, 0.3, 0.4, 0.5, 2.2, 0.6, 0.7});
  state_to_row(cells, 4, mhd1d::StateVector{4.0, 0.4, 0.5, 0.6, 2.3, 0.7, 0.8});
  state_to_row(cells, 5, mhd1d::StateVector{-2.0, -2.0, -2.0, -2.0, -2.0, -2.0, -2.0});

  const mhd1d::StateVector interior_left  = row_to_state(cells, 1);
  const mhd1d::StateVector interior_right = row_to_state(cells, 4);
  const mhd1d::StateVector interior_mid_2 = row_to_state(cells, 2);
  const mhd1d::StateVector interior_mid_3 = row_to_state(cells, 3);

  mhd1d::set_boundary(cells, 1, 4);

  require_state_vector_close(row_to_state(cells, 0), interior_left);
  require_state_vector_close(row_to_state(cells, 5), interior_right);
  require_state_vector_close(row_to_state(cells, 1), interior_left);
  require_state_vector_close(row_to_state(cells, 2), interior_mid_2);
  require_state_vector_close(row_to_state(cells, 3), interior_mid_3);
  require_state_vector_close(row_to_state(cells, 4), interior_right);
}

std::vector<double> make_sample_conservative_cells()
{
  std::vector<double>    conservative_cells(4 * mhd1d::kStateWidth, 0.0);
  const mhd1d::ArrayView2D view(conservative_cells.data(), 4, mhd1d::kStateWidth);
  state_to_row(view, 0, mhd1d::StateVector{1.0, 0.1, 0.0, 0.0, 1.6, 0.20, 0.00});
  state_to_row(view, 1, mhd1d::StateVector{0.9, 0.0, 0.1, 0.0, 1.3, 0.15, 0.05});
  state_to_row(view, 2, mhd1d::StateVector{0.8, -0.1, 0.0, 0.1, 1.1, 0.10, 0.10});
  state_to_row(view, 3, mhd1d::StateVector{0.7, -0.2, -0.1, 0.0, 0.9, 0.05, 0.15});
  return conservative_cells;
}

TEST_CASE("compute_rhs returns finite values", "[mhd1d][evolution]")
{
  const std::size_t      nx = 4;
  mhd1d::SolverWorkspace workspace(nx, 2.0, 0.75);

  const std::vector<double> conservative_cells = make_sample_conservative_cells();
  for (std::size_t row = 0; row < nx; ++row) {
    for (std::size_t component = 0; component < mhd1d::kStateWidth; ++component) {
      workspace.conservative(workspace.Lbx + row, component) =
          conservative_cells[row * mhd1d::kStateWidth + component];
    }
  }

  mhd1d::compute_rhs(workspace);
  for (std::size_t row = workspace.Lbx; row <= workspace.Ubx; ++row) {
    for (std::size_t component = 0; component < mhd1d::kStateWidth; ++component) {
      REQUIRE(std::isfinite(workspace.rhs1(row, component)));
    }
  }
}

TEST_CASE("push_ssp_rk3 evolves state with finite conservative values", "[mhd1d][evolution]")
{
  const std::size_t      nx = 4;
  mhd1d::SolverWorkspace workspace(nx, 2.0, 0.75);

  const std::vector<double> conservative_cells = make_sample_conservative_cells();
  for (std::size_t row = 0; row < nx; ++row) {
    for (std::size_t component = 0; component < mhd1d::kStateWidth; ++component) {
      workspace.conservative(workspace.Lbx + row, component) =
          conservative_cells[row * mhd1d::kStateWidth + component];
    }
  }

  mhd1d::push_ssp_rk3(workspace, 1.0e-4);

  for (std::size_t row = workspace.Lbx; row <= workspace.Ubx; ++row) {
    const double rho = workspace.conservative(row, 0U);
    for (std::size_t component = 0; component < mhd1d::kStateWidth; ++component) {
      REQUIRE(std::isfinite(workspace.conservative(row, component)));
    }
    REQUIRE(rho > 0.0);
  }
}

TEST_CASE("evolve_ssp_rk3 matches repeated push_ssp_rk3 calls", "[mhd1d][evolution]")
{
  const std::size_t nx      = 4;
  const double      dt      = 1.0e-4;
  const double      t_final = 2.0e-4;

  mhd1d::SolverWorkspace evolved_workspace(nx, 2.0, 0.75);
  mhd1d::SolverWorkspace manual_workspace(nx, 2.0, 0.75);

  const std::vector<double> conservative_cells = make_sample_conservative_cells();
  for (std::size_t row = 0; row < nx; ++row) {
    for (std::size_t component = 0; component < mhd1d::kStateWidth; ++component) {
      const double value = conservative_cells[row * mhd1d::kStateWidth + component];
      evolved_workspace.conservative(evolved_workspace.Lbx + row, component) = value;
      manual_workspace.conservative(manual_workspace.Lbx + row, component)   = value;
    }
  }

  mhd1d::evolve_ssp_rk3(evolved_workspace, dt, t_final);

  for (int step = 0; step < 2; ++step) {
    mhd1d::push_ssp_rk3(manual_workspace, dt);
  }

  for (std::size_t row = 0; row < nx; ++row) {
    const std::size_t i = evolved_workspace.Lbx + row;
    for (std::size_t component = 0; component < mhd1d::kStateWidth; ++component) {
      REQUIRE(std::fabs(manual_workspace.conservative(i, component) -
                        evolved_workspace.conservative(i, component)) <= kTolerance);
    }
  }
}
