#include "rk2.hpp"

#include <cxxopts.hpp>

#include <functional>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>

int main(int argc, char** argv)
{
  try {
    cxxopts::Options options("rk2_cli", "RK2 midpoint solver CLI");
    options.add_options()("rhs_name", "RHS function name", cxxopts::value<std::string>())(
        "y0", "Initial y", cxxopts::value<double>())("t0", "Initial t", cxxopts::value<double>())(
        "h", "Step size", cxxopts::value<double>())("n_steps", "Number of steps",
                                                    cxxopts::value<int>())("help", "Show usage");
    options.parse_positional({"rhs_name", "y0", "t0", "h", "n_steps"});

    const auto parsed = options.parse(argc, argv);
    if (parsed.count("help") != 0 || argc != 6) {
      std::cerr << "usage: rk2_cli <rhs_name> <y0> <t0> <h> <n_steps>\n";
      return 2;
    }

    const std::string rhs_name = parsed["rhs_name"].as<std::string>();
    const double      y0       = parsed["y0"].as<double>();
    const double      t0       = parsed["t0"].as<double>();
    const double      h        = parsed["h"].as<double>();
    const int         n_steps  = parsed["n_steps"].as<int>();
    if (n_steps < 0 || n_steps > 1000000) {
      throw std::invalid_argument("out-of-range n_steps");
    }

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
