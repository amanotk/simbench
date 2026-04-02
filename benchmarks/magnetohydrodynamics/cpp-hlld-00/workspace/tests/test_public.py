import subprocess
from pathlib import Path


def _build_public_tests() -> Path:
    subprocess.run(["cmake", "-S", ".", "-B", "build"], check=True)
    subprocess.run(
        ["cmake", "--build", "build", "--target", "hlld_public_tests"], check=True
    )
    exe = Path("build/tests/hlld_public_tests")
    assert exe.exists()
    return exe


def test_catch2_public_suite() -> None:
    exe = _build_public_tests()
    proc = subprocess.run(
        [str(exe), "--reporter", "compact"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
