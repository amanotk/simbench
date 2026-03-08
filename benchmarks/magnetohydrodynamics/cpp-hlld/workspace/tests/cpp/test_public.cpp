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

namespace
{

constexpr double kTolerance = 1e-12;

ConservativeState primitive_to_conservative(const PrimitiveState& state, double bx, double gamma)
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

  return ConservativeState{
      rho, rho * u, rho * v, rho * w, energy, by, bz,
  };
}

FluxState physical_flux_x(const ConservativeState& state, double bx, double gamma)
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

  return FluxState{
      rho * u,
      rho * u * u + total_pressure - bx * bx,
      rho * v * u - bx * by,
      rho * w * u - bx * bz,
      (energy + total_pressure) * u - bx * (u * bx + v * by + w * bz),
      by * u - bx * v,
      bz * u - bx * w,
  };
}

void require_close(const FluxState& actual, const FluxState& expected)
{
  for (std::size_t i = 0; i < actual.size(); ++i) {
    REQUIRE(std::abs(actual[i] - expected[i]) <= kTolerance);
  }
}

} // namespace

TEST_CASE("equal primitive states reduce to the physical flux")
{
  const double            bx    = 0.75;
  const double            gamma = 1.4;
  const PrimitiveState    state{1.1, 0.2, -0.3, 0.4, 0.9, 0.5, -0.6};
  const ConservativeState conservative = primitive_to_conservative(state, bx, gamma);

  const FluxState actual   = hlld_flux_from_primitive(state, state, bx, gamma);
  const FluxState expected = physical_flux_x(conservative, bx, gamma);

  require_close(actual, expected);
}

TEST_CASE("primitive and conservative entry points agree")
{
  const double bx    = -0.4;
  const double gamma = 5.0 / 3.0;

  const PrimitiveState left{1.0, 0.3, 0.1, -0.2, 1.0, 0.7, -0.5};
  const PrimitiveState right{0.8, -0.1, -0.4, 0.25, 0.7, -0.2, 0.3};

  const ConservativeState left_cons  = primitive_to_conservative(left, bx, gamma);
  const ConservativeState right_cons = primitive_to_conservative(right, bx, gamma);

  const FluxState from_primitive    = hlld_flux_from_primitive(left, right, bx, gamma);
  const FluxState from_conservative = hlld_flux_from_conservative(left_cons, right_cons, bx, gamma);

  require_close(from_primitive, from_conservative);
}

TEST_CASE("right-going contact discontinuity is resolved exactly")
{
  const double bx    = 0.8;
  const double gamma = 5.0 / 3.0;

  const PrimitiveState left{1.0, 0.3, 0.2, -0.15, 1.0, 0.6, -0.3};
  const PrimitiveState right{0.7, 0.3, 0.2, -0.15, 1.0, 0.6, -0.3};

  const FluxState actual = hlld_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, physical_flux_x(primitive_to_conservative(left, bx, gamma), bx, gamma));
}

TEST_CASE("left-going contact discontinuity is resolved exactly")
{
  const double bx    = 0.8;
  const double gamma = 5.0 / 3.0;

  const PrimitiveState left{1.0, -0.25, 0.2, -0.15, 1.0, 0.6, -0.3};
  const PrimitiveState right{0.7, -0.25, 0.2, -0.15, 1.0, 0.6, -0.3};

  const FluxState actual = hlld_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, physical_flux_x(primitive_to_conservative(right, bx, gamma), bx, gamma));
}

TEST_CASE("right-going rotational discontinuity is resolved exactly")
{
  const double bx    = 1.0;
  const double gamma = 5.0 / 3.0;

  const PrimitiveState left{1.0, 0.2, 0.1, -0.2, 1.0, 1.0, 0.0};
  const PrimitiveState right{1.0, 0.2, 0.5, -1.0, 1.0, 0.6, 0.8};

  const FluxState actual = hlld_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, physical_flux_x(primitive_to_conservative(left, bx, gamma), bx, gamma));
}

TEST_CASE("left-going rotational discontinuity is resolved exactly")
{
  const double bx    = 1.0;
  const double gamma = 5.0 / 3.0;

  const PrimitiveState left{1.0, 0.2, 0.1, -0.2, 1.0, 1.0, 0.0};
  const PrimitiveState right{1.0, 0.2, -0.3, 0.6, 1.0, 0.6, 0.8};

  const FluxState actual = hlld_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, physical_flux_x(primitive_to_conservative(right, bx, gamma), bx, gamma));
}

TEST_CASE("Bx equals zero hydro case matches reference flux")
{
  const double bx    = 0.0;
  const double gamma = 1.4;

  const PrimitiveState left{1.0, 0.75, 0.0, 0.0, 1.0, 0.0, 0.0};
  const PrimitiveState right{0.125, 0.0, 0.0, 0.0, 0.1, 0.0, 0.0};
  const FluxState      expected{
      0.92274146439449267, 1.3581095429585437, 0.0, 0.0, 3.1282919538345322, 0.0, 0.0,
  };

  const FluxState actual = hlld_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, expected);
}

TEST_CASE("Bx equals zero magnetized case matches reference flux")
{
  const double bx    = 0.0;
  const double gamma = 5.0 / 3.0;

  const PrimitiveState left{1.0, 0.6, 0.1, -0.2, 1.0, 0.7, -0.5};
  const PrimitiveState right{0.7, -0.3, -0.15, 0.25, 0.5, -0.2, 0.4};
  const FluxState      expected{
      0.44815524807196727, 2.011116795062418,   0.044815524807196722, -0.089631049614393443,
      1.6980640537315086,  0.31370867365037713, -0.22407762403598386,
  };

  const FluxState actual = hlld_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, expected);
}

TEST_CASE("small Bx near-degenerate case matches reference flux")
{
  const double bx    = 1.0e-6;
  const double gamma = 1.4;

  const PrimitiveState left{1.0, 0.4, 0.2, -0.1, 1.0, 0.5, -0.4};
  const PrimitiveState right{0.85, -0.3, -0.15, 0.25, 0.8, -0.35, 0.45};
  const FluxState      expected{
      0.16298732855830989, 1.7549717390289374,   0.032596899426565185,  -0.016298279827753587,
      0.72345786285986069, 0.081493464279122407, -0.065194831423298072,
  };

  const FluxState actual = hlld_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, expected);
}

TEST_CASE("generic coupled MHD case 1 matches reference flux")
{
  const double bx    = -0.65;
  const double gamma = 5.0 / 3.0;

  const PrimitiveState left{1.08, 0.45, -0.12, 0.08, 0.95, 0.4, -0.3};
  const PrimitiveState right{0.72, -0.25, 0.16, -0.05, 0.58, -0.2, 0.35};
  const FluxState      expected{
      0.33341182495747945, 1.3232304013056353,  0.06667172041085781,  -0.02277204332310151,
      0.88458241136476201, 0.20058802344338272, -0.18511862133859658,
  };

  const FluxState actual = hlld_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, expected);
}

TEST_CASE("generic coupled MHD case 2 matches reference flux")
{
  const double bx    = 0.35;
  const double gamma = 1.4;

  const PrimitiveState left{0.9, -0.45, 0.2, 0.15, 0.8, -0.3, 0.55};
  const PrimitiveState right{1.15, 0.18, -0.12, -0.08, 1.05, 0.22, -0.4};
  const FluxState      expected{
      -0.14227120841958368, 0.6095322640180193,    0.028703852070217931, 0.063723510257583313,
      -0.40524273615789225, -0.065690714628438368, 0.14700372046240096,
  };

  const FluxState actual = hlld_flux_from_primitive(left, right, bx, gamma);
  require_close(actual, expected);
}
