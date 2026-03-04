#!/usr/bin/env python3

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = REPO_ROOT / "docker" / "Dockerfile"

FLAP_VERSION = "1.2.16"
MDSPAN_REF = "mdspan-0.6.0"
XTL_REF = "0.8.2"
XSIMD_REF = "14.0.0"
XTENSOR_REF = "0.27.1"
FACE_REV = "1455c549ae0c1ead96961ca61a73131d8176b6a4"
PENF_REV = "a519e6cb58873efa85a81b4cf0a547870f510629"
FLAP_INSTALL_SHA256 = "c99e294dda30fc9c69d9ec796c954a05b79cc1874110f10178432f217aee3663"


def _cmd_str(cmd: list[str]) -> str:
    return shlex.join(cmd)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Build the benchmark Docker image")
    p.add_argument("--tag", default="scibench:0.1", help="Docker image tag")
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
        f"MDSPAN_REF={MDSPAN_REF}",
        "--build-arg",
        f"XTL_REF={XTL_REF}",
        "--build-arg",
        f"XSIMD_REF={XSIMD_REF}",
        "--build-arg",
        f"XTENSOR_REF={XTENSOR_REF}",
        "--build-arg",
        f"FACE_REV={FACE_REV}",
        "--build-arg",
        f"PENF_REV={PENF_REV}",
        "--build-arg",
        f"FLAP_INSTALL_SHA256={FLAP_INSTALL_SHA256}",
    ]
    if args.no_cache:
        cmd.append("--no-cache")
    cmd.append(str(REPO_ROOT))

    print(_cmd_str(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
