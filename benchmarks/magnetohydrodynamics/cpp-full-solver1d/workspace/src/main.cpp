#include "mhd1d.hpp"

#include <iomanip>
#include <iostream>
#include <vector>

namespace
{

constexpr std::size_t        kBrioWuNx             = 400;
constexpr double             kBrioWuXLeft          = 0.0;
constexpr double             kBrioWuXRight         = 1.0;
constexpr double             kBrioWuDiscontinuityX = 0.5;
constexpr double             kBrioWuDt             = 5.0e-4;
constexpr double             kBrioWuTFinal         = 0.1;
constexpr double             kBrioWuGamma          = 2.0;
constexpr double             kBrioWuBx             = 0.75;
constexpr mhd1d::StateVector kBrioWuLeftPrimitive{
    1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0,
};
constexpr mhd1d::StateVector kBrioWuRightPrimitive{
    0.125, 0.0, 0.0, 0.0, 0.1, -1.0, 0.0,
};

} // namespace

int main()
{
  mhd1d::SolverWorkspace workspace(kBrioWuNx, kBrioWuXLeft, kBrioWuXRight, kBrioWuDt, kBrioWuTFinal,
                                   kBrioWuGamma, kBrioWuBx);
  const mhd1d::ArrayView primitive_cells(workspace.buf_primitive.data(), workspace.Nx,
                                         mhd1d::kStateWidth);
  const std::vector<double> centers =
      mhd1d::cell_centers(workspace.Nx, workspace.x_left, workspace.x_right);

  for (std::size_t index = 0; index < workspace.Nx; ++index) {
    const mhd1d::StateVector& state =
        (centers[index] < kBrioWuDiscontinuityX) ? kBrioWuLeftPrimitive : kBrioWuRightPrimitive;
    for (std::size_t component = 0; component < mhd1d::kStateWidth; ++component) {
      primitive_cells(index, component) = state[component];
    }
  }

  mhd1d::primitive_profile_to_conservative(primitive_cells, workspace.stage1, workspace.bx,
                                           workspace.gamma);

  mhd1d::evolve_ssp_rk3_fixed_dt(workspace.stage1, workspace.stage1, workspace.t_final,
                                 workspace.dt, workspace.dx, workspace.bx, workspace.gamma);

  mhd1d::conservative_profile_to_primitive(workspace.stage1, primitive_cells, workspace.bx,
                                           workspace.gamma);

  std::cout << "x,rho,u,v,w,p,by,bz\n";
  std::cout << std::setprecision(17);
  for (std::size_t index = 0; index < workspace.Nx; ++index) {
    std::cout << centers[index] << ',' << primitive_cells(index, 0) << ','
              << primitive_cells(index, 1) << ',' << primitive_cells(index, 2) << ','
              << primitive_cells(index, 3) << ',' << primitive_cells(index, 4) << ','
              << primitive_cells(index, 5) << ',' << primitive_cells(index, 6) << '\n';
  }

  return 0;
}
