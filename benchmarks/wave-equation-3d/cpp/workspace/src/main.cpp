#include "wave3d.hpp"

#include <cmath>
#include <experimental/mdspan>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace stdex = std::experimental;

namespace
{

using shape3d = stdex::dextents<int, 3>;

void set_initial_condition(std::vector<double>& u, std::vector<double>& v, int nx, int ny, int nz)
{
  stdex::mdspan<double, shape3d> u_view(u.data(), nz + 2, ny + 2, nx + 2);
  stdex::mdspan<double, shape3d> v_view(v.data(), nz + 2, ny + 2, nx + 2);

  const double sigma      = 0.1;
  const double two_sigma2 = 2.0 * sigma * sigma;

  for (int iz = 1; iz <= nz; ++iz) {
    const double z = (static_cast<double>(iz - 1) + 0.5) / static_cast<double>(nz);
    for (int iy = 1; iy <= ny; ++iy) {
      const double y = (static_cast<double>(iy - 1) + 0.5) / static_cast<double>(ny);
      for (int ix = 1; ix <= nx; ++ix) {
        const double x     = (static_cast<double>(ix - 1) + 0.5) / static_cast<double>(nx);
        const double r2    = (x - 0.5) * (x - 0.5) + (y - 0.5) * (y - 0.5) + (z - 0.5) * (z - 0.5);
        u_view(iz, iy, ix) = std::exp(-r2 / two_sigma2);
        v_view(iz, iy, ix) = 0.0;
      }
    }
  }

  apply_periodic_ghosts(u, nx, ny, nz);
  apply_periodic_ghosts(v, nx, ny, nz);
}

} // namespace

int main(int argc, char** argv)
{
  if (argc != 7) {
    std::cerr << "usage: fd3d_cli <dt> <dx> <nx> <ny> <nz> <n_steps>\n";
    return 2;
  }

  const double dt      = std::stod(argv[1]);
  const double dx      = std::stod(argv[2]);
  const int    nx      = std::stoi(argv[3]);
  const int    ny      = std::stoi(argv[4]);
  const int    nz      = std::stoi(argv[5]);
  const int    n_steps = std::stoi(argv[6]);

  if (n_steps < 0 || nx <= 0 || ny <= 0 || nz <= 0 || dx <= 0.0 || dt < 0.0) {
    std::cerr << "invalid arguments\n";
    return 1;
  }

  const size_t n_total =
      static_cast<size_t>(nx + 2) * static_cast<size_t>(ny + 2) * static_cast<size_t>(nz + 2);

  std::vector<double> u(n_total, 0.0);
  std::vector<double> v(n_total, 0.0);
  set_initial_condition(u, v, nx, ny, nz);

  for (int step = 0; step < n_steps; ++step) {
    push_wave_3d(u, v, dt, dx, nx, ny, nz);
  }

  stdex::mdspan<double, shape3d> u_view(u.data(), nz + 2, ny + 2, nx + 2);

  std::cout << std::setprecision(17);
  for (int iz = 1; iz <= nz; ++iz) {
    for (int iy = 1; iy <= ny; ++iy) {
      for (int ix = 1; ix <= nx; ++ix) {
        std::cout << u_view(iz, iy, ix) << "\n";
      }
    }
  }
  return 0;
}
