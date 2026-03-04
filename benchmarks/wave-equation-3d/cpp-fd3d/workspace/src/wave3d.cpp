#include "wave3d.hpp"

#include <experimental/mdspan>
#include <stdexcept>
#include <vector>

std::vector<double> simulate_wave_3d(double dt, double dx, int nx, int ny, int nz, int n_steps)
{
  if (n_steps < 0) {
    throw std::invalid_argument("n_steps must be non-negative");
  }
  if (nx <= 0 || ny <= 0 || nz <= 0) {
    throw std::invalid_argument("grid sizes must be positive");
  }
  if (dx <= 0.0 || dt < 0.0) {
    throw std::invalid_argument("dx must be positive and dt must be non-negative");
  }

  std::vector<double> u(static_cast<size_t>(nz) * static_cast<size_t>(ny) * static_cast<size_t>(nx),
                        0.0);
  std::experimental::mdspan<double, std::experimental::dextents<size_t, 3>> view(
      u.data(), static_cast<size_t>(nz), static_cast<size_t>(ny), static_cast<size_t>(nx));
  (void)view;
  return u;
}
