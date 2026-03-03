#include "rk2.hpp"

#include <cstdlib>
#include <functional>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {

double parse_double(const char* s, const char* name) {
    char* end = nullptr;
    const double v = std::strtod(s, &end);
    if (end == s || (end != nullptr && *end != '\0')) {
        throw std::invalid_argument(std::string("invalid ") + name + ": " + s);
    }
    return v;
}

int parse_int(const char* s, const char* name) {
    char* end = nullptr;
    const long v = std::strtol(s, &end, 10);
    if (end == s || (end != nullptr && *end != '\0')) {
        throw std::invalid_argument(std::string("invalid ") + name + ": " + s);
    }
    if (v < 0 || v > 1000000) {
        throw std::invalid_argument(std::string("out-of-range ") + name + ": " + s);
    }
    return static_cast<int>(v);
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 6) {
            std::cerr << "usage: rk2_cli <rhs_name> <y0> <t0> <h> <n_steps>\n";
            return 2;
        }

        const std::string rhs_name = argv[1];
        const double y0 = parse_double(argv[2], "y0");
        const double t0 = parse_double(argv[3], "t0");
        const double h = parse_double(argv[4], "h");
        const int n_steps = parse_int(argv[5], "n_steps");

        std::function<double(double, double)> rhs;
        if (rhs_name == "exp_growth") {
            rhs = [](double, double y) { return y; };
        } else if (rhs_name == "damped_forced") {
            rhs = [](double t, double y) { return -2.0 * y + t; };
        } else {
            throw std::invalid_argument("unknown rhs_name");
        }

        const auto y = solve_rk2_midpoint(rhs, y0, t0, h, n_steps);

        std::cout << std::setprecision(15);
        for (double v : y) {
            std::cout << v << "\n";
        }
        return 0;
    } catch (const std::exception& e) {
        std::cerr << e.what() << "\n";
        return 1;
    }
}
