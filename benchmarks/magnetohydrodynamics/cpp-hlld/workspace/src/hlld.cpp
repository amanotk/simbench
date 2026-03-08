#include "hlld.hpp"

namespace
{

FluxState zero_flux()
{
  return FluxState{0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0};
}

} // namespace

FluxState hlld_flux_from_primitive(const PrimitiveState& left, const PrimitiveState& right,
                                   double bx, double gamma)
{
  (void)left;
  (void)right;
  (void)bx;
  (void)gamma;
  return zero_flux();
}

FluxState hlld_flux_from_conservative(const ConservativeState& left, const ConservativeState& right,
                                      double bx, double gamma)
{
  (void)left;
  (void)right;
  (void)bx;
  (void)gamma;
  return zero_flux();
}
