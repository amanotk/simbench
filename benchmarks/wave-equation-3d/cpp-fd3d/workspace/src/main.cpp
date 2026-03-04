#include "wave3d.hpp"

#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>

int main(int argc, char** argv)
{
  try {
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

    const auto u = simulate_wave_3d(dt, dx, nx, ny, nz, n_steps);
    if (u.size() != static_cast<size_t>(nx) * static_cast<size_t>(ny) * static_cast<size_t>(nz)) {
      throw std::runtime_error("unexpected output size");
    }

    std::cout << std::setprecision(17);
    for (int ix = 0; ix < nx; ++ix) {
      for (int iy = 0; iy < ny; ++iy) {
        for (int iz = 0; iz < nz; ++iz) {
          const size_t idx =
              (static_cast<size_t>(iz) * static_cast<size_t>(ny) + static_cast<size_t>(iy)) *
                  static_cast<size_t>(nx) +
              static_cast<size_t>(ix);
          std::cout << u[idx] << "\n";
        }
      }
    }
    return 0;
  } catch (const std::exception& e) {
    std::cerr << e.what() << "\n";
    return 1;
  }
}
