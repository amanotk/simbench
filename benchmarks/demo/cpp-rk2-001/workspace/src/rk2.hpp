#pragma once

#include <functional>
#include <string>
#include <vector>

std::vector<double> solve_rk2_midpoint(
    const std::function<double(double, double)>& rhs,
    double y0,
    double t0,
    double h,
    int n_steps
);
