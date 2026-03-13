#!/usr/bin/env python3

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = REPO_ROOT / "docker" / "Dockerfile"

FLAP_VERSION = "1.2.16"
CATCH2_REF = "v3.13.0"
MDSPAN_REF = "mdspan-0.6.0"
XTL_REF = "0.8.2"
XSIMD_REF = "14.0.0"
XTENSOR_REF = "0.27.1"
TOML11_REF = "v4.4.0"
FORTRAN_STDLIB_REF = "v0.6.1"
TOML_F_REF = "v0.4.2"
FACE_REV = "1455c549ae0c1ead96961ca61a73131d8176b6a4"
PENF_REV = "a519e6cb58873efa85a81b4cf0a547870f510629"


def _cmd_str(cmd: list[str]) -> str:
    return shlex.join(cmd)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Build the benchmark Docker image")
    p.add_argument("--tag", default="simbench:0.1", help="Docker image tag")
    p.add_argument(
        "--no-cache", action="store_true", help="Pass --no-cache to docker build"
    )
    args = p.parse_args(argv)

    cmd = [
        "docker",
        "build",
        "-t",
        args.tag,
        "-f",
        str(DOCKERFILE),
        "--build-arg",
        f"FLAP_VERSION={FLAP_VERSION}",
        "--build-arg",
        f"CATCH2_REF={CATCH2_REF}",
        "--build-arg",
        f"MDSPAN_REF={MDSPAN_REF}",
        "--build-arg",
        f"XTL_REF={XTL_REF}",
        "--build-arg",
        f"XSIMD_REF={XSIMD_REF}",
        "--build-arg",
        f"XTENSOR_REF={XTENSOR_REF}",
        "--build-arg",
        f"TOML11_REF={TOML11_REF}",
        "--build-arg",
        f"FORTRAN_STDLIB_REF={FORTRAN_STDLIB_REF}",
        "--build-arg",
        f"TOML_F_REF={TOML_F_REF}",
        "--build-arg",
        f"FACE_REV={FACE_REV}",
        "--build-arg",
        f"PENF_REV={PENF_REV}",
    ]
    if args.no_cache:
        cmd.append("--no-cache")
    cmd.append(str(REPO_ROOT))

    print(_cmd_str(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
