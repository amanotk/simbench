#include "mhd1d.hpp"

namespace mhd1d
{

void primitive_to_conservative(const double* primitive, double* conservative, double bx,
                               double gamma)
{
  (void)primitive;
  (void)conservative;
  (void)bx;
  (void)gamma;
  // TODO(student): convert one primitive state [rho,u,v,w,p,By,Bz] to
  // conservative [rho,mx,my,mz,E,By,Bz].
}

void conservative_to_primitive(const double* conservative, double* primitive, double bx,
                               double gamma)
{
  (void)conservative;
  (void)primitive;
  (void)bx;
  (void)gamma;
  // TODO(student): recover primitive variables from one conservative state.
  // Enforce positive density and compute pressure from total energy.
}

void convert_primitive_to_conservative(ArrayView2D primitive, ArrayView2D conservative, double bx,
                                       double gamma)
{
  (void)primitive;
  (void)conservative;
  (void)bx;
  (void)gamma;
  // TODO(student): loop over cells and call primitive_to_conservative.
}

void convert_conservative_to_primitive(ArrayView2D conservative, ArrayView2D primitive, double bx,
                                       double gamma)
{
  (void)conservative;
  (void)primitive;
  (void)bx;
  (void)gamma;
  // TODO(student): loop over cells and call conservative_to_primitive.
}

void set_boundary_lb(ArrayView2D dst, ArrayView2D src, int lbx)
{
  (void)dst;
  (void)src;
  (void)lbx;
  // TODO(student): copy left interior boundary state into left ghost cells.
}

void set_boundary_ub(ArrayView2D dst, ArrayView2D src, int ubx)
{
  (void)dst;
  (void)src;
  (void)ubx;
  // TODO(student): copy right interior boundary state into right ghost cells.
}

void set_boundary(ArrayView2D dst, ArrayView2D src, int lbx, int ubx)
{
  (void)dst;
  (void)src;
  (void)lbx;
  (void)ubx;
  // TODO(student): apply both lower and upper zero-gradient boundaries.
}

void compute_lr(SolverWorkspace& workspace)
{
  (void)workspace;
  // TODO(student): compute MC2 reconstructed left/right primitive states on each cell.
}

void compute_flux_hlld(SolverWorkspace& workspace, double bx, double gamma)
{
  (void)workspace;
  (void)bx;
  (void)gamma;
  // TODO(student): evaluate HLLD interface fluxes using provided hlld_flux_from_primitive.
}

void compute_rhs(SolverWorkspace& workspace)
{
  (void)workspace;
  // TODO(student): build semidiscrete RHS from flux differences and cell width dx.
}

void push_ssp_rk3(SolverWorkspace& workspace, double dt)
{
  (void)workspace;
  (void)dt;
  // TODO(student): implement one full SSP-RK3 step (3 substeps).
}

void evolve_ssp_rk3(SolverWorkspace& workspace, double dt, double t_final)
{
  (void)workspace;
  (void)dt;
  (void)t_final;
  // TODO(student): repeatedly call push_ssp_rk3 until t_final (clip final dt).
}

} // namespace mhd1d
