#include <catch2/catch_test_macros.hpp>

#include <cmath>
#include <vector>

#include "mhd1d.hpp"

namespace
{

constexpr double kTolerance = 1.0e-12;

mhd1d::StateVector row_to_state(mhd1d::ConstArrayView cells, std::size_t row)
{
  mhd1d::StateVector state{};
  for (std::size_t component = 0; component < mhd1d::kStateWidth; ++component) {
    state[component] = cells(row, component);
  }
  return state;
}

void state_to_row(mhd1d::ArrayView cells, std::size_t row, const mhd1d::StateVector& state)
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

TEST_CASE("mc2_slopes preserve a constant primitive state", "[mhd1d][reconstruction]")
{
  const auto constant_state = mhd1d::StateVector{1.25, -0.5, 0.25, -0.125, 2.75, 0.4, -0.3};
  std::vector<double>    cells_buffer(4 * mhd1d::kStateWidth, 0.0);
  const mhd1d::ArrayView cells(cells_buffer.data(), 4, mhd1d::kStateWidth);
  for (std::size_t index = 0; index < 4; ++index) {
    state_to_row(cells, index, constant_state);
  }

  std::vector<double>    slopes_buffer(4 * mhd1d::kStateWidth, 0.0);
  const mhd1d::ArrayView slopes(slopes_buffer.data(), 4, mhd1d::kStateWidth);
  mhd1d::mc2_slopes(mhd1d::ConstArrayView(cells_buffer.data(), 4, mhd1d::kStateWidth), slopes);

  for (std::size_t index = 0; index < 4; ++index) {
    require_state_vector_close(row_to_state(slopes, index), mhd1d::StateVector{});
  }
}

TEST_CASE("reconstruct_mc2_interfaces preserves a constant primitive state exactly",
          "[mhd1d][reconstruction]")
{
  const auto             constant_state = mhd1d::StateVector{0.9, 0.3, -0.2, 0.1, 1.8, -0.45, 0.6};
  std::vector<double>    cells_buffer(4 * mhd1d::kStateWidth, 0.0);
  const mhd1d::ArrayView cells(cells_buffer.data(), 4, mhd1d::kStateWidth);
  for (std::size_t index = 0; index < 4; ++index) {
    state_to_row(cells, index, constant_state);
  }

  std::vector<double>    left_buffer(3 * mhd1d::kStateWidth, 0.0);
  std::vector<double>    right_buffer(3 * mhd1d::kStateWidth, 0.0);
  const mhd1d::ArrayView left_states(left_buffer.data(), 3, mhd1d::kStateWidth);
  const mhd1d::ArrayView right_states(right_buffer.data(), 3, mhd1d::kStateWidth);
  mhd1d::reconstruct_mc2_interfaces(
      mhd1d::ConstArrayView(cells_buffer.data(), 4, mhd1d::kStateWidth), left_states, right_states);

  for (std::size_t index = 0; index < 3; ++index) {
    require_state_vector_close(row_to_state(left_states, index), constant_state);
  }
  for (std::size_t index = 0; index < 3; ++index) {
    require_state_vector_close(row_to_state(right_states, index), constant_state);
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

TEST_CASE("pad_zero_gradient_ghost_cells duplicates edge states on both sides", "[mhd1d][boundary]")
{
  std::vector<double>    cells_buffer(3 * mhd1d::kStateWidth, 0.0);
  const mhd1d::ArrayView cells(cells_buffer.data(), 3, mhd1d::kStateWidth);
  state_to_row(cells, 0, mhd1d::StateVector{1.0, 0.5, -0.25, 0.125, 2.0, 0.1, -0.05});
  state_to_row(cells, 1, mhd1d::StateVector{1.2, 0.6, -0.2, 0.15, 2.2, 0.12, -0.02});
  state_to_row(cells, 2, mhd1d::StateVector{1.4, 0.7, -0.15, 0.175, 2.4, 0.14, 0.01});

  std::vector<double>    padded_buffer(7 * mhd1d::kStateWidth, 0.0);
  const mhd1d::ArrayView padded(padded_buffer.data(), 7, mhd1d::kStateWidth);
  mhd1d::pad_zero_gradient_ghost_cells(
      mhd1d::ConstArrayView(cells_buffer.data(), 3, mhd1d::kStateWidth), padded);

  require_state_vector_close(row_to_state(padded, 0), row_to_state(cells, 0));
  require_state_vector_close(row_to_state(padded, 1), row_to_state(cells, 0));
  require_state_vector_close(row_to_state(padded, 2), row_to_state(cells, 0));
  require_state_vector_close(row_to_state(padded, 3), row_to_state(cells, 1));
  require_state_vector_close(row_to_state(padded, 4), row_to_state(cells, 2));
  require_state_vector_close(row_to_state(padded, 5), row_to_state(cells, 2));
  require_state_vector_close(row_to_state(padded, 6), row_to_state(cells, 2));
}

TEST_CASE("pad_zero_gradient_ghost_cells handles a single interior cell", "[mhd1d][boundary]")
{
  const auto             cell = mhd1d::StateVector{1.5, -0.75, 0.25, 0.0, 3.5, -0.1, 0.2};
  std::vector<double>    cells_buffer(1 * mhd1d::kStateWidth, 0.0);
  const mhd1d::ArrayView cells(cells_buffer.data(), 1, mhd1d::kStateWidth);
  state_to_row(cells, 0, cell);

  std::vector<double>    padded_buffer(5 * mhd1d::kStateWidth, 0.0);
  const mhd1d::ArrayView padded(padded_buffer.data(), 5, mhd1d::kStateWidth);
  mhd1d::pad_zero_gradient_ghost_cells(
      mhd1d::ConstArrayView(cells_buffer.data(), 1, mhd1d::kStateWidth), padded);

  for (std::size_t index = 0; index < 5; ++index) {
    require_state_vector_close(row_to_state(padded, index), cell);
  }
}

TEST_CASE("apply_zero_gradient_boundary overwrites ghost cells from interior boundary",
          "[mhd1d][boundary]")
{
  std::vector<double>    cells_buffer(6 * mhd1d::kStateWidth, 0.0);
  const mhd1d::ArrayView cells(cells_buffer.data(), 6, mhd1d::kStateWidth);

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

  mhd1d::apply_zero_gradient_boundary(cells, 1, 4);

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
  const mhd1d::ArrayView view(conservative_cells.data(), 4, mhd1d::kStateWidth);
  state_to_row(view, 0, mhd1d::StateVector{1.0, 0.1, 0.0, 0.0, 1.6, 0.20, 0.00});
  state_to_row(view, 1, mhd1d::StateVector{0.9, 0.0, 0.1, 0.0, 1.3, 0.15, 0.05});
  state_to_row(view, 2, mhd1d::StateVector{0.8, -0.1, 0.0, 0.1, 1.1, 0.10, 0.10});
  state_to_row(view, 3, mhd1d::StateVector{0.7, -0.2, -0.1, 0.0, 0.9, 0.05, 0.15});
  return conservative_cells;
}

TEST_CASE("arrayview compute_semidiscrete_rhs returns finite values", "[mhd1d][arrayview]")
{
  const std::vector<double> conservative_cells = make_sample_conservative_cells();
  const std::size_t         nx                 = 4;

  const double dx = 1.0 / static_cast<double>(nx);

  std::vector<double> rhs_buffer(nx * mhd1d::kStateWidth, 0.0);
  mhd1d::compute_semidiscrete_rhs(
      mhd1d::ConstArrayView(conservative_cells.data(), nx, mhd1d::kStateWidth),
      mhd1d::ArrayView(rhs_buffer.data(), nx, mhd1d::kStateWidth), dx, 0.75, 2.0);

  for (std::size_t row = 0; row < nx; ++row) {
    for (std::size_t component = 0; component < mhd1d::kStateWidth; ++component) {
      REQUIRE(std::isfinite(rhs_buffer[row * mhd1d::kStateWidth + component]));
    }
  }
}

TEST_CASE("arrayview ssp_rk3_step evolves state with finite conservative values",
          "[mhd1d][arrayview]")
{
  const std::vector<double> conservative_cells = make_sample_conservative_cells();
  const std::size_t         nx                 = 4;

  const double        dx = 1.0 / static_cast<double>(nx);
  const double        dt = 1.0e-4;
  std::vector<double> next_buffer(nx * mhd1d::kStateWidth, 0.0);

  mhd1d::ssp_rk3_step(mhd1d::ConstArrayView(conservative_cells.data(), nx, mhd1d::kStateWidth),
                      mhd1d::ArrayView(next_buffer.data(), nx, mhd1d::kStateWidth), dt, dx, 0.75,
                      2.0);

  for (std::size_t row = 0; row < nx; ++row) {
    const double rho = next_buffer[row * mhd1d::kStateWidth + 0U];
    for (std::size_t component = 0; component < mhd1d::kStateWidth; ++component) {
      REQUIRE(std::isfinite(next_buffer[row * mhd1d::kStateWidth + component]));
    }
    REQUIRE(rho > 0.0);
  }
}

TEST_CASE("arrayview evolve_ssp_rk3_fixed_dt matches repeated arrayview steps",
          "[mhd1d][arrayview]")
{
  const std::vector<double> conservative_cells = make_sample_conservative_cells();
  const std::size_t         nx                 = 4;
  const double              dx                 = 1.0 / static_cast<double>(nx);
  const double              dt                 = 1.0e-4;
  const double              t_final            = 2.0e-4;

  std::vector<double> evolved_buffer(nx * mhd1d::kStateWidth, 0.0);
  std::vector<double> step_buffer(nx * mhd1d::kStateWidth, 0.0);
  std::vector<double> manual_buffer = conservative_cells;

  mhd1d::evolve_ssp_rk3_fixed_dt(
      mhd1d::ConstArrayView(conservative_cells.data(), nx, mhd1d::kStateWidth),
      mhd1d::ArrayView(evolved_buffer.data(), nx, mhd1d::kStateWidth), t_final, dt, dx, 0.75, 2.0);

  for (int step = 0; step < 2; ++step) {
    mhd1d::ssp_rk3_step(mhd1d::ConstArrayView(manual_buffer.data(), nx, mhd1d::kStateWidth),
                        mhd1d::ArrayView(step_buffer.data(), nx, mhd1d::kStateWidth), dt, dx, 0.75,
                        2.0);
    manual_buffer.swap(step_buffer);
  }

  for (std::size_t row = 0; row < nx; ++row) {
    for (std::size_t component = 0; component < mhd1d::kStateWidth; ++component) {
      REQUIRE(std::fabs(manual_buffer[row * mhd1d::kStateWidth + component] -
                        evolved_buffer[row * mhd1d::kStateWidth + component]) <= kTolerance);
    }
  }
}
