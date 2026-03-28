#pragma once

#if __has_include("hlld.hpp")
#include "hlld.hpp"
#else
#include "../../../workspace/src/hlld.hpp"
#endif

#include <cmath>

namespace hidden_reference
{

inline StateVector hlld_flux_from_primitive(const StateVector& left, const StateVector& right,
                                            double bx, double gamma)
{
  constexpr double eps = 1.0e-40;

  const double rol = left[0];
  const double vxl = left[1];
  const double vyl = left[2];
  const double vzl = left[3];
  const double prl = left[4];
  const double byl = left[5];
  const double bzl = left[6];

  const double ror = right[0];
  const double vxr = right[1];
  const double vyr = right[2];
  const double vzr = right[3];
  const double prr = right[4];
  const double byr = right[5];
  const double bzr = right[6];

  const double igm  = 1.0 / (gamma - 1.0);
  const double bxs  = bx;
  const double bxsq = bxs * bxs;

  const double pbl = 0.5 * (bxsq + byl * byl + bzl * bzl);
  const double pbr = 0.5 * (bxsq + byr * byr + bzr * bzr);
  const double ptl = prl + pbl;
  const double ptr = prr + pbr;

  const double rxl = rol * vxl;
  const double ryl = rol * vyl;
  const double rzl = rol * vzl;
  const double rxr = ror * vxr;
  const double ryr = ror * vyr;
  const double rzr = ror * vzr;

  const double eel = prl * igm + 0.5 * (rxl * vxl + ryl * vyl + rzl * vzl) + pbl;
  const double eer = prr * igm + 0.5 * (rxr * vxr + ryr * vyr + rzr * vzr) + pbr;

  const double gmpl = gamma * prl;
  const double gmpr = gamma * prr;
  const double gpbl = gmpl + 2.0 * pbl;
  const double gpbr = gmpr + 2.0 * pbr;

  const double cfl = std::sqrt((gpbl + std::sqrt((gmpl - 2.0 * pbl) * (gmpl - 2.0 * pbl) +
                                                 4.0 * gmpl * (byl * byl + bzl * bzl))) *
                               0.5 / rol);
  const double cfr = std::sqrt((gpbr + std::sqrt((gmpr - 2.0 * pbr) * (gmpr - 2.0 * pbr) +
                                                 4.0 * gmpr * (byr * byr + bzr * bzr))) *
                               0.5 / ror);

  const double sl = std::min(vxl, vxr) - std::max(cfl, cfr);
  const double sr = std::max(vxl, vxr) + std::max(cfl, cfr);

  const StateVector fql{rxl,
                        rxl * vxl + ptl - bxsq,
                        rxl * vyl - bxs * byl,
                        rxl * vzl - bxs * bzl,
                        vxl * (eel + ptl - bxsq) - bxs * (vyl * byl + vzl * bzl),
                        byl * vxl - bxs * vyl,
                        bzl * vxl - bxs * vzl};
  const StateVector fqr{rxr,
                        rxr * vxr + ptr - bxsq,
                        rxr * vyr - bxs * byr,
                        rxr * vzr - bxs * bzr,
                        vxr * (eer + ptr - bxsq) - bxs * (vyr * byr + vzr * bzr),
                        byr * vxr - bxs * vyr,
                        bzr * vxr - bxs * vzr};

  const double sdl   = sl - vxl;
  const double sdr   = sr - vxr;
  const double rosdl = rol * sdl;
  const double rosdr = ror * sdr;
  const double temp  = 1.0 / (rosdr - rosdl);
  const double sm    = (rosdr * vxr - rosdl * vxl - ptr + ptl) * temp;
  const double sdml  = sl - sm;
  const double sdmr  = sr - sm;
  const double ptst  = (rosdr * ptl - rosdl * ptr + rosdl * rosdr * (vxr - vxl)) * temp;

  const auto sign_unit = [](double x) { return (x >= 0.0) ? 1.0 : -1.0; };

  const double temp_fst_l = rosdl * sdml - bxsq;
  const double sign1_l    = sign_unit(std::abs(temp_fst_l) - eps);
  const double maxs1_l    = std::max(0.0, sign1_l);
  const double mins1_l    = std::min(0.0, sign1_l);
  const double itf_l      = 1.0 / (temp_fst_l + mins1_l);
  const double isdml      = 1.0 / sdml;

  const double temp_l   = bxs * (sdl - sdml) * itf_l;
  const double rolst    = maxs1_l * (rosdl * isdml) - mins1_l * rol;
  const double vxlst    = maxs1_l * sm - mins1_l * vxl;
  const double rxlst    = rolst * vxlst;
  const double vylst    = maxs1_l * (vyl - byl * temp_l) - mins1_l * vyl;
  const double rylst    = rolst * vylst;
  const double vzlst    = maxs1_l * (vzl - bzl * temp_l) - mins1_l * vzl;
  const double rzlst    = rolst * vzlst;
  const double temp_l_b = (rosdl * sdl - bxsq) * itf_l;
  const double bylst    = maxs1_l * (byl * temp_l_b) - mins1_l * byl;
  const double bzlst    = maxs1_l * (bzl * temp_l_b) - mins1_l * bzl;
  const double vdbstl   = vxlst * bxs + vylst * bylst + vzlst * bzlst;
  const double eelst    = maxs1_l * ((sdl * eel - ptl * vxl + ptst * sm +
                                   bxs * (vxl * bxs + vyl * byl + vzl * bzl - vdbstl)) *
                                  isdml) -
                       mins1_l * eel;

  const double temp_fst_r = rosdr * sdmr - bxsq;
  const double sign1_r    = sign_unit(std::abs(temp_fst_r) - eps);
  const double maxs1_r    = std::max(0.0, sign1_r);
  const double mins1_r    = std::min(0.0, sign1_r);
  const double itf_r      = 1.0 / (temp_fst_r + mins1_r);
  const double isdmr      = 1.0 / sdmr;

  const double temp_r   = bxs * (sdr - sdmr) * itf_r;
  const double rorst    = maxs1_r * (rosdr * isdmr) - mins1_r * ror;
  const double vxrst    = maxs1_r * sm - mins1_r * vxr;
  const double rxrst    = rorst * vxrst;
  const double vyrst    = maxs1_r * (vyr - byr * temp_r) - mins1_r * vyr;
  const double ryrst    = rorst * vyrst;
  const double vzrst    = maxs1_r * (vzr - bzr * temp_r) - mins1_r * vzr;
  const double rzrst    = rorst * vzrst;
  const double temp_r_b = (rosdr * sdr - bxsq) * itf_r;
  const double byrst    = maxs1_r * (byr * temp_r_b) - mins1_r * byr;
  const double bzrst    = maxs1_r * (bzr * temp_r_b) - mins1_r * bzr;
  const double vdbstr   = vxrst * bxs + vyrst * byrst + vzrst * bzrst;
  const double eerst    = maxs1_r * ((sdr * eer - ptr * vxr + ptst * sm +
                                   bxs * (vxr * bxs + vyr * byr + vzr * bzr - vdbstr)) *
                                  isdmr) -
                       mins1_r * eer;

  const double sqrtrol  = std::sqrt(rolst);
  const double sqrtror  = std::sqrt(rorst);
  const double abbx     = std::abs(bxs);
  const double slst     = sm - abbx / sqrtrol;
  const double srst     = sm + abbx / sqrtror;
  const double signbx   = sign_unit(bxs);
  const double sign1_b  = sign_unit(abbx - eps);
  const double maxs1_b  = std::max(0.0, sign1_b);
  const double mins1_b  = -std::min(0.0, sign1_b);
  const double invsumro = maxs1_b / (sqrtrol + sqrtror);

  const double roldst = rolst;
  const double rordst = rorst;
  const double rxldst = rxlst;
  const double rxrdst = rxrst;
  const double vxldst = vxlst;
  const double vxrdst = vxrst;

  const double vy_shared =
      invsumro * (sqrtrol * vylst + sqrtror * vyrst + signbx * (byrst - bylst));
  const double vyldst = vylst * mins1_b + vy_shared;
  const double vyrdst = vyrst * mins1_b + vy_shared;
  const double ryldst = rylst * mins1_b + roldst * vy_shared;
  const double ryrdst = ryrst * mins1_b + rordst * vy_shared;

  const double vz_shared =
      invsumro * (sqrtrol * vzlst + sqrtror * vzrst + signbx * (bzrst - bzlst));
  const double vzldst = vzlst * mins1_b + vz_shared;
  const double vzrdst = vzrst * mins1_b + vz_shared;
  const double rzldst = rzlst * mins1_b + roldst * vz_shared;
  const double rzrdst = rzrst * mins1_b + rordst * vz_shared;

  const double by_shared =
      invsumro * (sqrtrol * byrst + sqrtror * bylst + signbx * sqrtrol * sqrtror * (vyrst - vylst));
  const double byldst = bylst * mins1_b + by_shared;
  const double byrdst = byrst * mins1_b + by_shared;

  const double bz_shared =
      invsumro * (sqrtrol * bzrst + sqrtror * bzlst + signbx * sqrtrol * sqrtror * (vzrst - vzlst));
  const double bzldst = bzlst * mins1_b + bz_shared;
  const double bzrdst = bzrst * mins1_b + bz_shared;

  const double temp_dst = sm * bxs + vyldst * byldst + vzldst * bzldst;
  const double eeldst   = eelst - sqrtrol * signbx * (vdbstl - temp_dst) * maxs1_b;
  const double eerdst   = eerst + sqrtror * signbx * (vdbstr - temp_dst) * maxs1_b;

  const double sign1       = sign_unit(sm);
  const double maxs1       = std::max(0.0, sign1);
  const double mins1       = -std::min(0.0, sign1);
  const double msl         = std::min(sl, 0.0);
  const double mslst       = std::min(slst, 0.0);
  const double msrst       = std::max(srst, 0.0);
  const double msr         = std::max(sr, 0.0);
  const double temp_flux_l = mslst - msl;
  const double temp_flux_r = msrst - msr;

  return StateVector{
      (fql[0] - msl * rol - rolst * temp_flux_l + roldst * mslst) * maxs1 +
          (fqr[0] - msr * ror - rorst * temp_flux_r + rordst * msrst) * mins1,
      (fql[1] - msl * rxl - rxlst * temp_flux_l + rxldst * mslst) * maxs1 +
          (fqr[1] - msr * rxr - rxrst * temp_flux_r + rxrdst * msrst) * mins1,
      (fql[2] - msl * ryl - rylst * temp_flux_l + ryldst * mslst) * maxs1 +
          (fqr[2] - msr * ryr - ryrst * temp_flux_r + ryrdst * msrst) * mins1,
      (fql[3] - msl * rzl - rzlst * temp_flux_l + rzldst * mslst) * maxs1 +
          (fqr[3] - msr * rzr - rzrst * temp_flux_r + rzrdst * msrst) * mins1,
      (fql[4] - msl * eel - eelst * temp_flux_l + eeldst * mslst) * maxs1 +
          (fqr[4] - msr * eer - eerst * temp_flux_r + eerdst * msrst) * mins1,
      (fql[5] - msl * byl - bylst * temp_flux_l + byldst * mslst) * maxs1 +
          (fqr[5] - msr * byr - byrst * temp_flux_r + byrdst * msrst) * mins1,
      (fql[6] - msl * bzl - bzlst * temp_flux_l + bzldst * mslst) * maxs1 +
          (fqr[6] - msr * bzr - bzrst * temp_flux_r + bzrdst * msrst) * mins1,
  };
}

inline StateVector hlld_flux_from_conservative(const StateVector& left, const StateVector& right,
                                               double bx, double gamma)
{
  const auto to_primitive = [bx, gamma](const StateVector& state) {
    const double rho      = state[0];
    const double u        = state[1] / rho;
    const double v        = state[2] / rho;
    const double w        = state[3] / rho;
    const double by       = state[5];
    const double bz       = state[6];
    const double kinetic  = 0.5 * rho * (u * u + v * v + w * w);
    const double magnetic = 0.5 * (bx * bx + by * by + bz * bz);
    const double p        = (gamma - 1.0) * (state[4] - kinetic - magnetic);
    return StateVector{rho, u, v, w, p, by, bz};
  };

  return hlld_flux_from_primitive(to_primitive(left), to_primitive(right), bx, gamma);
}

} // namespace hidden_reference
