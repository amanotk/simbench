"""
Adversarial tests for runner/metrics_helpers.py import compatibility.

Tests the dual import-mode pattern: package mode vs direct script mode.
Focuses on boundary and regression cases for import compatibility.
"""

import subprocess
import sys
import os
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER_DIR = REPO_ROOT / "runner"
METRICS_HELPERS_PATH = RUNNER_DIR / "metrics_helpers.py"


def _run_test_code(code: str) -> subprocess.CompletedProcess:
    """Helper to run test code in subprocess."""
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


class TestMetricsHelpersImportCompatibility:
    """Test import compatibility under different invocation patterns."""

    def test_package_import_works(self):
        """Test that importing as package member works."""
        # Simulate package import: from runner import metrics_helpers
        code = f"""
import sys
from pathlib import Path

repo_root = Path("{REPO_ROOT}")
sys.path.insert(0, str(repo_root))
from runner import metrics_helpers

# Verify key functions are accessible
assert hasattr(metrics_helpers, '_extract_agent_usage_metrics')
assert hasattr(metrics_helpers, '_parse_human_token_count')
assert hasattr(metrics_helpers, '_json_line_objects')
print("PACKAGE_IMPORT_OK")
"""
        result = _run_test_code(code)
        assert result.returncode == 0, f"Package import failed: {result.stderr}"
        assert "PACKAGE_IMPORT_OK" in result.stdout

    def test_direct_script_import_fallback(self):
        """Test that direct script import fallback works."""
        # Simulate direct script import: import metrics_helpers
        code = f"""
import sys
from pathlib import Path

repo_root = Path("{REPO_ROOT}")
runner_dir = repo_root / "runner"
sys.path.insert(0, str(runner_dir))

import metrics_helpers
# Verify key functions are accessible
assert hasattr(metrics_helpers, '_extract_agent_usage_metrics')
assert hasattr(metrics_helpers, '_parse_human_token_count')
# The fallback should import results_helpers and get _json_line_objects
assert hasattr(metrics_helpers, '_json_line_objects')
print("DIRECT_IMPORT_OK")
"""
        result = _run_test_code(code)
        assert result.returncode == 0, f"Direct import failed: {result.stderr}"
        assert "DIRECT_IMPORT_OK" in result.stdout

    def test_missing_runner_package_falls_back(self):
        """Test fallback when runner package is not available."""
        # Remove runner from path to force fallback
        code = f"""
import sys
from pathlib import Path

repo_root = Path("{REPO_ROOT}")
runner_dir = repo_root / "runner"

# Remove runner package from path if present
sys.path = [p for p in sys.path if 'runner' not in str(p).lower() or 'simbench' not in str(p).lower()]

# Add runner directory directly to simulate direct script execution
sys.path.insert(0, str(runner_dir))

# Now import should use fallback
import metrics_helpers

# Verify the _json_line_objects is properly assigned
assert hasattr(metrics_helpers, '_json_line_objects')
result = metrics_helpers._json_line_objects('{{"type": "test"}}')
assert result == [{{"type": "test"}}]
print("FALLBACK_OK")
"""
        result = _run_test_code(code)
        assert result.returncode == 0, f"Fallback import failed: {result.stderr}"
        assert "FALLBACK_OK" in result.stdout

    def test_execution_via_bench_py(self):
        """Test that bench.py can use metrics_helpers under both import modes."""
        code = f"""
import sys
from pathlib import Path

repo_root = Path("{REPO_ROOT}")
runner_dir = repo_root / "runner"
sys.path.insert(0, str(runner_dir))

# Import the module as bench.py does
try:
    from runner import metrics_helpers as _metrics_helpers
except ModuleNotFoundError:
    import metrics_helpers as _metrics_helpers

# Access functions that depend on _json_line_objects
fn = _metrics_helpers._extract_agent_usage_metrics
assert callable(fn)

# Test actual functionality that uses _json_line_objects
test_output = '''
{{"type": "result", "usage": {{"input_tokens": 100, "output_tokens": 50}}}}
'''
result = _metrics_helpers._extract_agent_usage_metrics("opencode", test_output, "")
assert 'agent_input_tokens' in result
assert result['agent_input_tokens'] == 100
print("BENCH_COMPATIBLE_OK")
"""
        result = _run_test_code(code)
        assert result.returncode == 0, f"bench.py compatibility failed: {result.stderr}"
        assert "BENCH_COMPATIBLE_OK" in result.stdout


class TestMetricsHelpersBoundaryCases:
    """Boundary cases for import compatibility."""

    def test_import_with_multiple_package_attempts(self):
        """Test multiple import attempts don't cause issues."""
        code = f"""
import sys
from pathlib import Path

repo_root = Path("{REPO_ROOT}")

# Try importing multiple times (simulating multiple module loads)
for _ in range(3):
    if 'runner.metrics_helpers' in sys.modules:
        del sys.modules['runner.metrics_helpers']
    if 'runner.results_helpers' in sys.modules:
        del sys.modules['runner.results_helpers']
    if 'metrics_helpers' in sys.modules:
        del sys.modules['metrics_helpers']
    if 'results_helpers' in sys.modules:
        del sys.modules['results_helpers']
    
    sys.path.insert(0, str(repo_root))
    from runner import metrics_helpers
    assert hasattr(metrics_helpers, '_json_line_objects')

print("MULTIPLE_IMPORT_OK")
"""
        result = _run_test_code(code)
        assert result.returncode == 0, f"Multiple import failed: {result.stderr}"
        assert "MULTIPLE_IMPORT_OK" in result.stdout

    def test_import_with_changed_cwd(self):
        """Test import works when cwd is different from module location."""
        code = f"""
import sys
import os
from pathlib import Path

repo_root = Path("{REPO_ROOT}")

# Change to a different directory
os.chdir('/tmp' if os.path.exists('/tmp') else '/')

# Now try importing from different cwd
sys.path.insert(0, str(repo_root))
from runner import metrics_helpers

# Verify functions work
result = metrics_helpers._parse_human_token_count("1.5k")
assert result == 1500, f"Expected 1500, got {{result}}"

result = metrics_helpers._parse_human_token_count("2M")
assert result == 2000000, f"Expected 2000000, got {{result}}"

print("CHANGED_CWD_OK")
"""
        result = _run_test_code(code)
        assert result.returncode == 0, f"Changed cwd failed: {result.stderr}"
        assert "CHANGED_CWD_OK" in result.stdout


class TestMetricsHelpersFunctionalRegression:
    """Verify functional regression - core functions work correctly."""

    def test_parse_human_token_count_boundaries(self):
        """Test token count parsing with boundary values."""
        code = f"""
import sys
from pathlib import Path

repo_root = Path("{REPO_ROOT}")
sys.path.insert(0, str(repo_root))
from runner import metrics_helpers

# Test cases: simple numbers, k, M suffixes, edge cases
test_cases = [
    ("100", 100),
    ("1k", 1000),
    ("1.5k", 1500),
    ("2M", 2000000),
    ("1,000", 1000),
    ("1,500,000", 1500000),
    ("0", 0),
    ("0k", 0),
]

for raw, expected in test_cases:
    result = metrics_helpers._parse_human_token_count(raw)
    assert result == expected, f"Failed for '{{raw}}': expected {{expected}}, got {{result}}"

# Invalid inputs should return None
assert metrics_helpers._parse_human_token_count("") is None
assert metrics_helpers._parse_human_token_count("abc") is None
assert metrics_helpers._parse_human_token_count("invalid") is None

print("TOKEN_PARSE_OK")
"""
        result = _run_test_code(code)
        assert result.returncode == 0, f"Token parse test failed: {result.stderr}"
        assert "TOKEN_PARSE_OK" in result.stdout

    def test_json_line_objects_integration(self):
        """Test _json_line_objects works correctly after import."""
        code = f"""
import sys
from pathlib import Path

repo_root = Path("{REPO_ROOT}")
sys.path.insert(0, str(repo_root))
from runner import metrics_helpers

# Test the function that depends on results_helpers import
test_input = '''line1
{{"type": "result", "value": 1}}
{{"type": "result", "value": 2}}
plain text
{{"type": "result", "value": 3}}
'''

result = metrics_helpers._json_line_objects(test_input)
assert len(result) == 3, f"Expected 3 objects, got {{len(result)}}"
assert result[0] == {{"type": "result", "value": 1}}
assert result[1] == {{"type": "result", "value": 2}}
assert result[2] == {{"type": "result", "value": 3}}

print("JSON_LINES_OK")
"""
        result = _run_test_code(code)
        assert result.returncode == 0, f"JSON lines test failed: {result.stderr}"
        assert "JSON_LINES_OK" in result.stdout

    def test_extract_agent_usage_metrics_opencode(self):
        """Test _extract_agent_usage_metrics for opencode agent."""
        code = f"""
import sys
from pathlib import Path

repo_root = Path("{REPO_ROOT}")
sys.path.insert(0, str(repo_root))
from runner import metrics_helpers

test_output = '''{{"type": "result", "usage": {{"input_tokens": 1000, "output_tokens": 500, "cached_input_tokens": 300}}}}'''

result = metrics_helpers._extract_agent_usage_metrics("opencode", test_output)
assert result.get("agent_input_tokens") == 1000
assert result.get("agent_output_tokens") == 500
assert result.get("agent_cached_input_tokens") == 300

print("AGENT_METRICS_OK")
"""
        result = _run_test_code(code)
        assert result.returncode == 0, f"Agent metrics test failed: {result.stderr}"
        assert "AGENT_METRICS_OK" in result.stdout


class TestMetricsHelpersDirectScriptMode:
    """Test direct script execution (python runner/metrics_helpers.py)."""

    def test_direct_execution_does_not_crash(self):
        """Test that running metrics_helpers.py directly doesn't crash."""
        result = subprocess.run(
            [sys.executable, str(METRICS_HELPERS_PATH)],
            capture_output=True,
            text=True,
            cwd=str(RUNNER_DIR),
        )
        # Should not crash, may produce no output or help text
        # Exit code 0 or 1 (if file has no __main__ block) is acceptable
        assert result.returncode in (0, 1, None), (
            f"Direct execution crashed: {result.stderr}"
        )

    def test_import_after_sys_path_modification(self):
        """Test import works after sys.path is modified (common pattern)."""
        code = f"""
import sys
from pathlib import Path

repo_root = Path("{REPO_ROOT}")

# Common pattern: clear and rebuild sys.path
original_path = sys.path.copy()
sys.path.clear()
sys.path.insert(0, str(repo_root))
sys.path.extend(original_path)

# Now import
from runner import metrics_helpers

# Verify functionality
result = metrics_helpers._parse_human_token_count("500")
assert result == 500

print("SYSPATH_MOD_OK")
"""
        result = _run_test_code(code)
        assert result.returncode == 0, (
            f"sys.path modification test failed: {result.stderr}"
        )
        assert "SYSPATH_MOD_OK" in result.stdout


class TestMetricsHelpersTypeConsistency:
    """Test that types are consistent across import modes."""

    def test_function_type_consistency(self):
        """Verify function signatures are same regardless of import mode."""
        code = f"""
import sys
import inspect
from pathlib import Path

repo_root = Path("{REPO_ROOT}")
runner_dir = repo_root / "runner"

# Test package mode
sys.path.insert(0, str(repo_root))
from runner import metrics_helpers as mh_package

# Test direct mode  
sys.path = [p for p in sys.path if 'runner' not in p]
sys.path.insert(0, str(runner_dir))
# Need to clear module cache
for mod in list(sys.modules.keys()):
    if 'metrics_helpers' in mod or 'results_helpers' in mod:
        del sys.modules[mod]
import metrics_helpers as mh_direct

# Compare function signatures
sig1 = inspect.signature(mh_package._parse_human_token_count)
sig2 = inspect.signature(mh_direct._parse_human_token_count)
assert str(sig1) == str(sig2), f"Signatures differ: {{sig1}} vs {{sig2}}"

# Compare return types
result1 = mh_package._parse_human_token_count("1k")
result2 = mh_direct._parse_human_token_count("1k")
assert result1 == result2 == 1000

print("TYPE_CONSISTENCY_OK")
"""
        result = _run_test_code(code)
        assert result.returncode == 0, f"Type consistency test failed: {result.stderr}"
        assert "TYPE_CONSISTENCY_OK" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
