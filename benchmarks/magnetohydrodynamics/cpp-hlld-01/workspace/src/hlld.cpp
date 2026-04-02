#include "hlld.hpp"

#include <algorithm>

void hlld_flux_from_primitive(const double* left, const double* right, double bx, double gamma,
                              double* flux)
{
  (void)left;
  (void)right;
  (void)bx;
  (void)gamma;

  std::fill(flux, flux + 7, 0.0);
}
