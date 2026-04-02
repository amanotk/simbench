#if __has_include("hlld.hpp")
#include "hlld.hpp"
#else
#include "../../../workspace/src/hlld.hpp"
#endif

#if __has_include(<catch2/catch_test_macros.hpp>)
#include <catch2/catch_test_macros.hpp>
#else
#include "/usr/local/include/catch2/catch_test_macros.hpp"
#endif

#include "hlld_reference.hpp"

#include <array>
#include <cmath>

using StateVector = std::array<double, 7>;

namespace
{

constexpr double kTolerance = 1e-12;

StateVector primitive_to_conservative(const StateVector& state, double bx, double gamma)
{
  const double rho = state[0];
  const double u   = state[1];
  const double v   = state[2];
  const double w   = state[3];
  const double p   = state[4];
  const double by  = state[5];
  const double bz  = state[6];

  const double kinetic  = 0.5 * rho * (u * u + v * v + w * w);
  const double magnetic = 0.5 * (bx * bx + by * by + bz * bz);
  const double energy   = p / (gamma - 1.0) + kinetic + magnetic;

  return StateVector{rho, rho * u, rho * v, rho * w, energy, by, bz};
}

StateVector physical_flux_x(const StateVector& state, double bx, double gamma)
{
  const double rho    = state[0];
  const double mx     = state[1];
  const double my     = state[2];
  const double mz     = state[3];
  const double energy = state[4];
  const double by     = state[5];
  const double bz     = state[6];

  const double u              = mx / rho;
  const double v              = my / rho;
  const double w              = mz / rho;
  const double kinetic        = 0.5 * rho * (u * u + v * v + w * w);
  const double magnetic       = 0.5 * (bx * bx + by * by + bz * bz);
  const double pressure       = (gamma - 1.0) * (energy - kinetic - magnetic);
  const double total_pressure = pressure + magnetic;

  return StateVector{
      rho * u,
      rho * u * u + total_pressure - bx * bx,
      rho * v * u - bx * by,
      rho * w * u - bx * bz,
      (energy + total_pressure) * u - bx * (u * bx + v * by + w * bz),
      by * u - bx * v,
      bz * u - bx * w,
  };
}

void require_close(const StateVector& actual, const StateVector& expected)
{
  for (std::size_t i = 0; i < actual.size(); ++i) {
    REQUIRE(std::abs(actual[i] - expected[i]) <= kTolerance);
  }
}

StateVector solver_flux_from_primitive(const StateVector& left, const StateVector& right, double bx,
                                       double gamma)
{
  StateVector flux{};
  hlld_flux_from_primitive(left.data(), right.data(), bx, gamma, flux.data());
  return flux;
}

} // namespace

TEST_CASE("equal primitive states reduce to the physical flux")
{
  const double      bx    = 0.35;
  const double      gamma = 1.4;
  const StateVector state{0.9, -0.45, 0.2, 0.15, 0.8, -0.3, 0.55};

  const StateVector actual = solver_flux_from_primitive(state, state, bx, gamma);
  const StateVector expected =
      physical_flux_x(primitive_to_conservative(state, bx, gamma), bx, gamma);

  require_close(actual, expected);
}

TEST_CASE("nontrivial primitive solve returns finite values")
{
  const double bx    = -0.65;
  const double gamma = 5.0 / 3.0;

  const StateVector left{1.08, 0.45, -0.12, 0.08, 0.95, 0.4, -0.3};
  const StateVector right{0.72, -0.25, 0.16, -0.05, 0.58, -0.2, 0.35};

  const StateVector flux = solver_flux_from_primitive(left, right, bx, gamma);

  for (double value : flux) {
    REQUIRE(std::isfinite(value));
  }
}

TEST_CASE("hidden reference flux case 1 matches reference implementation")
{
  const double bx    = -0.65;
  const double gamma = 5.0 / 3.0;

  const StateVector left{1.08, 0.45, -0.12, 0.08, 0.95, 0.4, -0.3};
  const StateVector right{0.72, -0.25, 0.16, -0.05, 0.58, -0.2, 0.35};
  const StateVector expected = hidden_reference::hlld_flux_from_primitive(left, right, bx, gamma);

  const StateVector actual = solver_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, expected);
}

TEST_CASE("hidden reference flux case 2 matches reference implementation")
{
  const double bx    = 0.35;
  const double gamma = 1.4;

  const StateVector left{0.9, -0.45, 0.2, 0.15, 0.8, -0.3, 0.55};
  const StateVector right{1.15, 0.18, -0.12, -0.08, 1.05, 0.22, -0.4};
  const StateVector expected = hidden_reference::hlld_flux_from_primitive(left, right, bx, gamma);

  const StateVector actual = solver_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, expected);
}

TEST_CASE("small Bx near-degenerate reference case matches reference implementation")
{
  const double bx    = 1.0e-6;
  const double gamma = 1.4;

  const StateVector left{1.0, 0.4, 0.2, -0.1, 1.0, 0.5, -0.4};
  const StateVector right{0.85, -0.3, -0.15, 0.25, 0.8, -0.35, 0.45};
  const StateVector expected = hidden_reference::hlld_flux_from_primitive(left, right, bx, gamma);

  const StateVector actual = solver_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, expected);
}

TEST_CASE("second Bx equals zero hydro case matches reference implementation")
{
  const double bx    = 0.0;
  const double gamma = 1.4;

  const StateVector left{0.4, -1.1, 0.0, 0.0, 0.4, 0.0, 0.0};
  const StateVector right{1.2, -0.2, 0.0, 0.0, 1.3, 0.0, 0.0};
  const StateVector expected = hidden_reference::hlld_flux_from_primitive(left, right, bx, gamma);

  const StateVector actual = solver_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, expected);
}
