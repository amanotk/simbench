#if __has_include("hlld.hpp")
#include "hlld.hpp"
#else
#include "../../src/hlld.hpp"
#endif

#if __has_include(<catch2/catch_test_macros.hpp>)
#include <catch2/catch_test_macros.hpp>
#else
#include "/usr/local/include/catch2/catch_test_macros.hpp"
#endif

#include <cmath>

#include <array>

using StateVector = std::array<double, 7>;

namespace
{

constexpr double kTolerance = 1e-12;
constexpr double kPi        = 3.14159265358979323846;

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

  return StateVector{
      rho, rho * u, rho * v, rho * w, energy, by, bz,
  };
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

StateVector solver_flux_from_primitive(const StateVector& left, const StateVector& right, double bx,
                                       double gamma)
{
  StateVector flux{};
  hlld_flux_from_primitive(left.data(), right.data(), bx, gamma, flux.data());
  return flux;
}

void require_close(const StateVector& actual, const StateVector& expected)
{
  for (std::size_t i = 0; i < actual.size(); ++i) {
    REQUIRE(std::abs(actual[i] - expected[i]) <= kTolerance);
  }
}

} // namespace

TEST_CASE("equal primitive states reduce to the physical flux")
{
  const double      bx    = 0.75;
  const double      gamma = 1.4;
  const StateVector state{1.1, 0.2, -0.3, 0.4, 0.9, 0.5, -0.6};
  const StateVector conservative = primitive_to_conservative(state, bx, gamma);

  const StateVector actual   = solver_flux_from_primitive(state, state, bx, gamma);
  const StateVector expected = physical_flux_x(conservative, bx, gamma);

  require_close(actual, expected);
}

TEST_CASE("right-going contact discontinuity is resolved exactly")
{
  const double bx    = 0.8;
  const double gamma = 5.0 / 3.0;

  const StateVector left{1.0, 0.3, 0.2, -0.15, 1.0, 0.6, -0.3};
  const StateVector right{0.7, 0.3, 0.2, -0.15, 1.0, 0.6, -0.3};

  const StateVector actual = solver_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, physical_flux_x(primitive_to_conservative(left, bx, gamma), bx, gamma));
}

TEST_CASE("left-going contact discontinuity is resolved exactly")
{
  const double bx    = 0.8;
  const double gamma = 5.0 / 3.0;

  const StateVector left{1.0, -0.25, 0.2, -0.15, 1.0, 0.6, -0.3};
  const StateVector right{0.7, -0.25, 0.2, -0.15, 1.0, 0.6, -0.3};

  const StateVector actual = solver_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, physical_flux_x(primitive_to_conservative(right, bx, gamma), bx, gamma));
}

TEST_CASE("right-going rotational discontinuity is resolved exactly")
{
  const double bx    = 1.0;
  const double gamma = 5.0 / 3.0;

  const StateVector left{1.0, 0.2, 0.1, -0.2, 1.0, 1.0, 0.0};
  const StateVector right{1.0, 0.2, 0.5, -1.0, 1.0, 0.6, 0.8};
  const StateVector expected{
      0.2, 1.04, -0.98, -0.04, 0.609, 0.1, 0.2,
  };

  const StateVector actual = solver_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, expected);
}

TEST_CASE("left-going rotational discontinuity is resolved exactly")
{
  const double bx    = 1.0;
  const double gamma = 5.0 / 3.0;

  const StateVector left{1.0, 0.2, 0.1, -0.2, 1.0, 1.0, 0.0};
  const StateVector right{1.0, 0.2, -0.3, 0.6, 1.0, 0.6, 0.8};
  const StateVector expected{
      0.2, 1.04, -0.66, -0.68, 0.449, 0.42, -0.44,
  };

  const StateVector actual = solver_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, expected);
}

TEST_CASE("Bx equals zero hydro case matches reference flux")
{
  const double bx    = 0.0;
  const double gamma = 1.4;

  const StateVector left{1.0, 0.75, 0.0, 0.0, 1.0, 0.0, 0.0};
  const StateVector right{0.125, 0.0, 0.0, 0.0, 0.1, 0.0, 0.0};
  const StateVector expected{
      0.92274146439449267, 1.3581095429585437, 0.0, 0.0, 3.1282919538345322, 0.0, 0.0,
  };

  const StateVector actual = solver_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, expected);
}

TEST_CASE("Bx equals zero magnetized case matches reference flux")
{
  const double bx    = 0.0;
  const double gamma = 5.0 / 3.0;

  const StateVector left{1.0, 0.6, 0.1, -0.2, 1.0, 0.7, -0.5};
  const StateVector right{0.7, -0.3, -0.15, 0.25, 0.5, -0.2, 0.4};
  const StateVector expected{
      0.44815524807196727, 2.011116795062418,   0.044815524807196722, -0.089631049614393443,
      1.6980640537315086,  0.31370867365037713, -0.22407762403598386,
  };

  const StateVector actual = solver_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, expected);
}

TEST_CASE("small Bx near-degenerate case matches reference flux")
{
  const double bx    = 1.0e-6;
  const double gamma = 1.4;

  const StateVector left{1.0, 0.4, 0.2, -0.1, 1.0, 0.5, -0.4};
  const StateVector right{0.85, -0.3, -0.15, 0.25, 0.8, -0.35, 0.45};
  const StateVector expected{
      0.16298732855830989, 1.7549717390289374,   0.032596899426565185,  -0.016298279827753587,
      0.72345786285986069, 0.081493464279122407, -0.065194831423298072,
  };

  const StateVector actual = solver_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, expected);
}

TEST_CASE("Ryu and Jones shock tube matches reference flux")
{
  const double bx    = 4.0 / std::sqrt(4.0 * kPi);
  const double gamma = 5.0 / 3.0;

  const StateVector left{
      1.08, 1.2, 0.01, 0.5, 0.95, 3.6 / std::sqrt(4.0 * kPi), 2.0 / std::sqrt(4.0 * kPi),
  };
  const StateVector right{
      1.0, 0.0, 0.0, 0.0, 1.0, 4.0 / std::sqrt(4.0 * kPi), 2.0 / std::sqrt(4.0 * kPi),
  };
  const StateVector expected{
      0.79485593966715773, 3.5458209484697329,  -1.3572358551169827,   -0.22185101509215432,
      3.9950643754664625,  0.67495208799031015, -0.062307582042232856,
  };

  const StateVector actual = solver_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, expected);
}

TEST_CASE("Brio and Wu shock tube matches reference flux")
{
  const double bx    = 0.75;
  const double gamma = 5.0 / 3.0;

  const StateVector left{1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0};
  const StateVector right{0.125, 0.0, 0.0, 0.0, 0.1, -1.0, 0.0};
  const StateVector expected{
      0.2063330447744266,
      0.4638678509599396,
      0.064186763013841408,
      0.0,
      0.16136546437466026,
      1.010233243594872,
      0.0,
  };

  const StateVector actual = solver_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, expected);
}

TEST_CASE("Falle switch-off shock matches reference flux")
{
  const double bx    = 1.0;
  const double gamma = 5.0 / 3.0;

  const StateVector left{1.368, 0.269, 1.0, 0.0, 1.769, 0.0, 0.0};
  const StateVector right{1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0};
  const StateVector expected{
      0.29721990694355238,
      1.4932992607654056,
      0.2893229270591654,
      0.0,
      1.1427267633652525,
      -1.0066552479847843,
      0.0,
  };

  const StateVector actual = solver_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, expected);
}

TEST_CASE("Falle switch-off rarefaction matches reference flux")
{
  const double bx    = 1.0;
  const double gamma = 5.0 / 3.0;

  const StateVector left{1.0, 0.0, 0.0, 0.0, 2.0, 0.0, 0.0};
  const StateVector right{0.2, 1.186, 2.967, 0.0, 0.1368, 1.6405, 0.0};
  const StateVector expected{
      0.27717801577960577,
      0.28228035303750848,
      -1.3364302412732558,
      0.0,
      -1.5599793330037519,
      -1.3806947854633354,
      0.0,
  };

  const StateVector actual = solver_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, expected);
}

TEST_CASE("super-fast expansion matches reference flux")
{
  const double bx    = 0.0;
  const double gamma = 5.0 / 3.0;

  const StateVector left{1.0, -3.0, 0.0, 0.0, 0.45, 0.5, 0.0};
  const StateVector right{1.0, 3.0, 0.0, 0.0, 0.45, 0.5, 0.0};
  const StateVector expected{
      0.0, -2.425, 0.0, 0.0, 0.0, 0.0, 0.0,
  };

  const StateVector actual = solver_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, expected);
}
