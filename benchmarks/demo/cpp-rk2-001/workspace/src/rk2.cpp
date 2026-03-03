#include "rk2.hpp"

#include <stdexcept>
#include <vector>

std::vector<double> solve_rk2_midpoint(
    const std::function<double(double, double)>& rhs,
    double y0,
    double t0,
    double h,
    int n_steps
) {
    (void)rhs;
    (void)t0;
    (void)h;

    if (n_steps < 0) {
        throw std::invalid_argument("n_steps must be non-negative");
    }

    std::vector<double> y(static_cast<size_t>(n_steps) + 1, 0.0);
    y[0] = y0;
    return y;
}
