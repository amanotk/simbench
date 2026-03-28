#include <catch2/catch_test_macros.hpp>

#include <cmath>
#include <vector>

#include "mhd1d.hpp"

namespace
{

constexpr double kTolerance = 1.0e-12;

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
  const std::vector<mhd1d::StateVector> cells{constant_state, constant_state, constant_state,
                                              constant_state};

  const auto slopes = mhd1d::mc2_slopes(cells);

  REQUIRE(slopes.size() == cells.size());
  for (const auto& slope : slopes) {
    require_state_vector_close(slope, mhd1d::StateVector{});
  }
}

TEST_CASE("reconstruct_mc2_interfaces preserves a constant primitive state exactly",
          "[mhd1d][reconstruction]")
{
  const auto constant_state = mhd1d::StateVector{0.9, 0.3, -0.2, 0.1, 1.8, -0.45, 0.6};
  const std::vector<mhd1d::StateVector> cells{constant_state, constant_state, constant_state,
                                              constant_state};

  const auto [left_states, right_states] = mhd1d::reconstruct_mc2_interfaces(cells);

  REQUIRE(left_states.size() == cells.size() - 1U);
  REQUIRE(right_states.size() == cells.size() - 1U);
  for (const auto& state : left_states) {
    require_state_vector_close(state, constant_state);
  }
  for (const auto& state : right_states) {
    require_state_vector_close(state, constant_state);
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
  const std::vector<mhd1d::StateVector> cells = {
      mhd1d::StateVector{1.0, 0.5, -0.25, 0.125, 2.0, 0.1, -0.05},
      mhd1d::StateVector{1.2, 0.6, -0.2, 0.15, 2.2, 0.12, -0.02},
      mhd1d::StateVector{1.4, 0.7, -0.15, 0.175, 2.4, 0.14, 0.01},
  };

  const auto padded = mhd1d::pad_zero_gradient_ghost_cells(cells);

  REQUIRE(padded.size() == cells.size() + 4U);
  require_state_vector_close(padded[0], cells.front());
  require_state_vector_close(padded[1], cells.front());
  require_state_vector_close(padded[2], cells[0]);
  require_state_vector_close(padded[3], cells[1]);
  require_state_vector_close(padded[4], cells[2]);
  require_state_vector_close(padded[5], cells.back());
  require_state_vector_close(padded[6], cells.back());
}

TEST_CASE("pad_zero_gradient_ghost_cells handles a single interior cell", "[mhd1d][boundary]")
{
  const auto cell = mhd1d::StateVector{1.5, -0.75, 0.25, 0.0, 3.5, -0.1, 0.2};
  const std::vector<mhd1d::StateVector> cells{cell};

  const auto padded = mhd1d::pad_zero_gradient_ghost_cells(cells);

  REQUIRE(padded.size() == 5U);
  for (const auto& padded_cell : padded) {
    require_state_vector_close(padded_cell, cell);
  }
}
