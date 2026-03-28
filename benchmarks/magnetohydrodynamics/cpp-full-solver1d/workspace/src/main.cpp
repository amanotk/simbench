#include "mhd1d.hpp"

#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

int main(int argc, char** argv)
{
  if (argc != 2) {
    std::cerr << "usage: cpp_full_solver1d <input.toml>\n";
    return 2;
  }

  const std::string input_path = argv[1];
  std::ifstream     input_stream(input_path);
  if (!input_stream) {
    std::cerr << "cpp-full-solver1d: unable to read TOML input '" << input_path << "'\n";
    return 1;
  }

  const mhd1d::ProblemConfig            problem               = mhd1d::make_brio_wu_example();
  const std::vector<mhd1d::StateVector> final_primitive_cells = mhd1d::run_full_simulation(problem);
  const std::vector<double>             centers =
      mhd1d::cell_centers(problem.nx, problem.x_left, problem.x_right);

  std::cout << "x,rho,u,v,w,p,by,bz\n";
  std::cout << std::setprecision(17);
  for (std::size_t index = 0; index < final_primitive_cells.size(); ++index) {
    const mhd1d::StateVector& cell = final_primitive_cells[index];
    std::cout << centers[index] << ',' << cell[0] << ',' << cell[1] << ',' << cell[2] << ','
              << cell[3] << ',' << cell[4] << ',' << cell[5] << ',' << cell[6] << '\n';
  }

  return 0;
}
