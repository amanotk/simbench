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
  const std::vector<double> centers =
      mhd1d::cell_centers(workspace.Nx, workspace.x_left, workspace.x_right);

  for (std::size_t index = workspace.Lbx; index <= workspace.Ubx; ++index) {
    const std::size_t         center_index = index - workspace.Lbx;
    const mhd1d::StateVector& state        = (centers[center_index] < kBrioWuDiscontinuityX)
                                                 ? kBrioWuLeftPrimitive
                                                 : kBrioWuRightPrimitive;
    for (std::size_t component = 0; component < mhd1d::kStateWidth; ++component) {
      workspace.primitive(index, component) = state[component];
    }
  }

  mhd1d::apply_zero_gradient_boundary(workspace.primitive, workspace.Lbx, workspace.Ubx);
  mhd1d::primitive_profile_to_conservative(workspace.primitive, workspace.conservative,
                                           workspace.bx, workspace.gamma);
  mhd1d::evolve_ssp_rk3_fixed_dt_patterned(workspace);

  std::cout << "x,rho,u,v,w,p,by,bz\n";
  std::cout << std::setprecision(17);
  for (std::size_t index = workspace.Lbx; index <= workspace.Ubx; ++index) {
    const std::size_t center_index = index - workspace.Lbx;
    std::cout << centers[center_index] << ',' << workspace.primitive(index, 0) << ','
              << workspace.primitive(index, 1) << ',' << workspace.primitive(index, 2) << ','
              << workspace.primitive(index, 3) << ',' << workspace.primitive(index, 4) << ','
              << workspace.primitive(index, 5) << ',' << workspace.primitive(index, 6) << '\n';
  }

  return 0;
}
