import subprocess
from pathlib import Path


def _build_hidden_tests() -> Path:
    hidden_source = Path("/eval/tests/cpp/test_hidden.cpp")
    subprocess.run(
        [
            "cmake",
            "-S",
            ".",
            "-B",
            "build",
            "-DSCIBENCH_ENABLE_HIDDEN_TESTS=ON",
            f"-DSCIBENCH_HIDDEN_TEST_SOURCE={hidden_source}",
        ],
        check=True,
    )
    subprocess.run(
        ["cmake", "--build", "build", "--target", "hlld_hidden_tests"], check=True
    )
    exe = Path("build/tests/hlld_hidden_tests")
    assert exe.exists()
    return exe


def test_hidden_catch2_suite() -> None:
    exe = _build_hidden_tests()
    proc = subprocess.run(
        [str(exe), "--reporter", "compact"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
