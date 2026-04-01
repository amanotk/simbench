#include "mhd1d.hpp"

#include <iomanip>
#include <iostream>
#include <vector>

constexpr int                Nx    = 400;
constexpr double             Gamma = 2.0;
constexpr double             Bx    = 0.75;
constexpr mhd1d::StateVector LeftPrimitive{
    1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0,
};
constexpr mhd1d::StateVector RightPrimitive{
    0.125, 0.0, 0.0, 0.0, 0.1, -1.0, 0.0,
};

mhd1d::SolverWorkspace initialize(int nx, double gamma, double bx,
                                  const mhd1d::StateVector& left_state,
                                  const mhd1d::StateVector& right_state)
{
  mhd1d::SolverWorkspace workspace(nx, gamma, bx);

  for (int ix = workspace.Lbx; ix <= workspace.Ubx; ++ix) {
    const mhd1d::StateVector& state = (workspace.x(ix) < 0.5) ? left_state : right_state;
    for (int component = 0; component < mhd1d::N_Component; ++component) {
      workspace.up(ix, component) = state[component];
    }
  }

  mhd1d::set_boundary(workspace.up, workspace.up, workspace.Lbx, workspace.Ubx);
  mhd1d::primitive_profile_to_conservative(workspace.up, workspace.uc, bx, gamma);

  return workspace;
}

void write_csv(const mhd1d::SolverWorkspace& workspace, std::ostream& os)
{
  os << "x,rho,u,v,w,p,by,bz\n";
  os << std::setprecision(17);
  for (int ix = workspace.Lbx; ix <= workspace.Ubx; ++ix) {
    os << workspace.x(ix) << ',' << workspace.up(ix, 0) << ',' << workspace.up(ix, 1) << ','
       << workspace.up(ix, 2) << ',' << workspace.up(ix, 3) << ',' << workspace.up(ix, 4) << ','
       << workspace.up(ix, 5) << ',' << workspace.up(ix, 6) << '\n';
  }
}

int main()
{
  const double delt = 5.0e-4;
  const double tmax = 0.1;

  auto workspace = initialize(Nx, Gamma, Bx, LeftPrimitive, RightPrimitive);

  mhd1d::evolve_ssp_rk3(workspace, delt, tmax);

  write_csv(workspace, std::cout);

  return 0;
}
