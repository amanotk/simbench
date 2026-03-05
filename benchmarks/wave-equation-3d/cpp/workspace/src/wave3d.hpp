#pragma once

#include <vector>

void apply_periodic_ghosts(std::vector<double>& a, int nx, int ny, int nz);
void push_wave_3d(std::vector<double>& u, std::vector<double>& v, double dt, double dx, int nx,
                  int ny, int nz);
