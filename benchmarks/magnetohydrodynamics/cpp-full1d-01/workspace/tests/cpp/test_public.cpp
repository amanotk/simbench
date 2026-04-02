#include <catch2/catch_test_macros.hpp>

#include <vector>

#include "mhd1d.hpp"

TEST_CASE("set_boundary duplicates edge states on both sides", "[mhd1d][boundary]")
{
  std::vector<double>      padded_buffer(4 * mhd1d::N_Component, 0.0);
  const mhd1d::ArrayView2D padded(padded_buffer.data(), 4, mhd1d::N_Component);

  padded(1, 0) = 1.2;
  padded(2, 0) = 1.4;

  const int lbx = 1;
  const int ubx = 2;

  for (int ix = 0; ix < lbx; ++ix) {
    padded(ix, 0) = padded(lbx, 0);
  }
  for (int ix = ubx + 1; ix < 4; ++ix) {
    padded(ix, 0) = padded(ubx, 0);
  }

  REQUIRE(padded(0, 0) == padded(1, 0));
  REQUIRE(padded(3, 0) == padded(2, 0));
}
