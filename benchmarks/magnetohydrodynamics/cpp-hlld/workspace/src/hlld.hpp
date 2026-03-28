#pragma once

#include <array>

using StateVector = std::array<double, 7>;

StateVector hlld_flux_from_primitive(const StateVector& left, const StateVector& right, double bx,
                                     double gamma);

StateVector hlld_flux_from_conservative(const StateVector& left, const StateVector& right,
                                        double bx, double gamma);
