#include "mhd1d.hpp"

#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <stdexcept>

constexpr int                Nx    = 100;
constexpr double             Gamma = 2.0;
constexpr double             Bx    = 0.75;
constexpr mhd1d::StateVector LeftPrimitive{
    1.0, 0.0, 0.0, 0.0, 1.0, 1.0, 0.0,
};
constexpr mhd1d::StateVector RightPrimitive{
    0.125, 0.0, 0.0, 0.0, 0.1, -1.0, 0.0,
};

int parse_nx(int argc, char** argv)
{
  if (argc <= 1) {
    return Nx;
  }

  char*      end    = nullptr;
  const long parsed = std::strtol(argv[1], &end, 10);
  if (end == argv[1] || *end != '\0' || parsed <= 0) {
    throw std::runtime_error("usage: solver [nx]");
  }
  return static_cast<int>(parsed);
}

mhd1d::SolverWorkspace initialize(int nx, double gamma, double bx,
                                  const mhd1d::StateVector& left_state,
                                  const mhd1d::StateVector& right_state)
{
  mhd1d::SolverWorkspace workspace(nx, gamma, bx);

  for (int ix = workspace.Lbx; ix <= workspace.Ubx; ++ix) {
    const mhd1d::StateVector& state = (workspace.x(ix) < 0.5) ? left_state : right_state;
    for (int component = 0; component < mhd1d::N_Component; ++component) {
      workspace.up(ix, component) = state[component];
      workspace.uc(ix, component) = 0.0;
    }
  }

  for (int ix = 0; ix < workspace.Lbx; ++ix) {
    for (int component = 0; component < mhd1d::N_Component; ++component) {
      workspace.up(ix, component) = workspace.up(workspace.Lbx, component);
      workspace.uc(ix, component) = workspace.uc(workspace.Lbx, component);
    }
  }
  for (int ix = workspace.Ubx + 1; ix < workspace.Nx + 2 * mhd1d::N_margin; ++ix) {
    for (int component = 0; component < mhd1d::N_Component; ++component) {
      workspace.up(ix, component) = workspace.up(workspace.Ubx, component);
      workspace.uc(ix, component) = workspace.uc(workspace.Ubx, component);
    }
  }

  (void)gamma;
  (void)bx;

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

int main(int argc, char** argv)
{
  const int    nx   = parse_nx(argc, argv);
  const double delt = 5.0e-4;
  const double tmax = 0.1;

  auto workspace = initialize(nx, Gamma, Bx, LeftPrimitive, RightPrimitive);

  mhd1d::evolve_ssp_rk3(workspace, delt, tmax);

  write_csv(workspace, std::cout);

  return 0;
}
