#pragma once

#include <array>

using PrimitiveState    = std::array<double, 7>;
using ConservativeState = std::array<double, 7>;
using FluxState         = std::array<double, 7>;

FluxState hlld_flux_from_primitive(const PrimitiveState& left, const PrimitiveState& right,
                                   double bx, double gamma);

FluxState hlld_flux_from_conservative(const ConservativeState& left, const ConservativeState& right,
                                      double bx, double gamma);
