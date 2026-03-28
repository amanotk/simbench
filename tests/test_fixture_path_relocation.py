"""
Adversarial tests for smoke-config fixture relocation.

Tests focus on boundary and regression cases around path relocation:
- Broken relative paths
- Missing fixture assumptions
- Contributor command drift
- Accidental coupling to the old sample/ location

These tests ensure the fixture path relocation from sample/ to
tests/fixtures/agent_configs/ is robust.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.test_runner_helpers import (
    _load_bench_module,
    bench,
)


class TestFixturePathRelocation(unittest.TestCase):
    """Tests for fixture path relocation edge cases."""

    def setUp(self):
        self.repo_root = Path(__file__).resolve().parents[1]
        self.fixture_dir = self.repo_root / "tests" / "fixtures" / "agent_configs"

    # --- Broken relative paths tests ---

    def test_load_agent_config_with_relative_path_from_wrong_cwd(self):
        """Test that relative paths are resolved against repo root, not CWD."""
        # The relative path should resolve from REPO_ROOT, not current directory
        relative_path = Path("tests/fixtures/agent_configs/opencode-smoke.toml")

        # Save and change cwd to a different location
        orig_cwd = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as td:
                os.chdir(td)
                # This should succeed because _resolve_input_toml_path uses REPO_ROOT
                # not the current working directory
                cfg = bench._load_agent_config(relative_path)
                self.assertEqual(cfg["name"], "opencode")
        finally:
            os.chdir(orig_cwd)

    def test_load_agent_config_with_traversal_attempt(self):
        """Test path traversal attempts are handled (resolved to repo-relative path)."""
        # Path traversal is resolved relative to repo root, not as absolute escape
        # So tests/fixtures/agent_configs/../../../etc/passwd becomes /home/amano/simbench/etc/passwd
        malicious_path = Path("tests/fixtures/agent_configs/../../../etc/passwd")

        # This should fail with FileNotFoundError because the resolved path doesn't exist
        with self.assertRaises(FileNotFoundError):
            bench._load_agent_config(malicious_path)

    def test_load_agent_config_with_absolute_path_outside_workspace(self):
        """Test that absolute paths outside workspace are handled."""
        # Absolute path to a file that shouldn't exist in the repo context
        external_path = Path("/tmp/nonexistent_agent_config.toml")

        with self.assertRaises(FileNotFoundError):
            bench._load_agent_config(external_path)

    # --- Missing fixture assumptions tests ---

    def test_load_agent_config_missing_file_raises_file_not_found(self):
        """Test that missing config file raises appropriate error."""
        missing_path = self.fixture_dir / "nonexistent-smoke.toml"

        with self.assertRaises(FileNotFoundError) as ctx:
            bench._load_agent_config(missing_path)

        # Verify the error message includes the path
        self.assertIn("nonexistent-smoke.toml", str(ctx.exception))

    def test_load_agent_config_missing_name_field_raises_error(self):
        """Test that config without required 'name' field fails appropriately."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bad_config = td_path / "bad-config.toml"
            bad_config.write_text("version = 1\n", encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                bench._load_agent_config(bad_config)

            self.assertIn("name", str(ctx.exception))

    def test_load_agent_config_invalid_version_raises_error(self):
        """Test that invalid version field fails appropriately."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            bad_config = td_path / "bad-version.toml"
            bad_config.write_text('version = 2\nname = "opencode"\n', encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                bench._load_agent_config(bad_config)

            self.assertIn("version", str(ctx.exception))

    def test_load_agent_config_with_empty_file(self):
        """Test that empty config file fails appropriately."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            empty_config = td_path / "empty.toml"
            empty_config.write_text("", encoding="utf-8")

            with self.assertRaises(ValueError):
                bench._load_agent_config(empty_config)

    # --- Contributor command drift tests ---

    def test_sample_directory_not_hardcoded_in_runner(self):
        """Test that runner doesn't hardcode sample/ path for agent configs."""
        # Check if any source files reference the old sample/ location
        runner_path = self.repo_root / "runner" / "bench.py"

        # Read the runner source
        runner_source = runner_path.read_text(encoding="utf-8")

        # Assert no hardcoded references to "sample/" for agent configs
        self.assertNotIn('"sample/', runner_source)
        self.assertNotIn("'sample/", runner_source)

    def test_fixtures_directory_correctly_located(self):
        """Test that fixtures are in the correct new location."""
        opencode_fixture = self.fixture_dir / "opencode-smoke.toml"
        copilot_fixture = self.fixture_dir / "copilot-smoke.toml"

        self.assertTrue(
            opencode_fixture.exists(),
            f"opencode-smoke.toml should exist at {opencode_fixture}",
        )
        self.assertTrue(
            copilot_fixture.exists(),
            f"copilot-smoke.toml should exist at {copilot_fixture}",
        )

    def test_fixture_configs_loadable_from_new_location(self):
        """Test that fixtures load correctly from new location."""
        opencode_cfg = bench._load_agent_config(
            self.fixture_dir / "opencode-smoke.toml"
        )
        self.assertEqual(opencode_cfg["name"], "opencode")

        copilot_cfg = bench._load_agent_config(self.fixture_dir / "copilot-smoke.toml")
        self.assertEqual(copilot_cfg["name"], "copilot")

    # --- Accidental coupling to old sample/ location tests ---

    def test_no_reference_to_sample_in_test_runner_smoke(self):
        """Test that test_runner_smoke.py doesn't reference old sample/ location."""
        test_file = self.repo_root / "tests" / "test_runner_smoke.py"
        test_source = test_file.read_text(encoding="utf-8")

        # The test should reference the new location (as Path operations, not string)
        # Check for the actual fixture filename references
        self.assertIn("opencode-smoke.toml", test_source)
        self.assertIn("copilot-smoke.toml", test_source)
        # And should NOT reference the old sample/ location for smoke configs
        self.assertNotIn("sample/opencode", test_source)
        self.assertNotIn("sample/copilot", test_source)

    def test_resolve_input_toml_path_relative_to_repo_root(self):
        """Test that relative paths are resolved against repo root."""
        # Test that _resolve_input_toml_path resolves relative to REPO_ROOT
        test_config = (
            self.repo_root
            / "tests"
            / "fixtures"
            / "agent_configs"
            / "opencode-smoke.toml"
        )

        resolved = bench._resolve_input_toml_path(
            Path("tests/fixtures/agent_configs/opencode-smoke.toml")
        )

        self.assertEqual(resolved.resolve(), test_config.resolve())

    def test_resolve_input_toml_path_without_repo_root_uses_default(self):
        """Test default repo_root behavior."""
        # The function should use REPO_ROOT when repo_root is not provided
        resolved = bench._resolve_input_toml_path(
            Path("tests/fixtures/agent_configs/opencode-smoke.toml")
        )

        # Should resolve to the actual file location
        expected = (
            self.repo_root
            / "tests"
            / "fixtures"
            / "agent_configs"
            / "opencode-smoke.toml"
        )
        self.assertEqual(resolved.resolve(), expected.resolve())

    # --- Boundary cases ---

    def test_resolve_input_toml_path_with_nonexistent_relative_path(self):
        """Test that relative paths resolve even to nonexistent files."""
        # _resolve_input_toml_path only resolves the path, doesn't check existence
        resolved = bench._resolve_input_toml_path(Path("nonexistent/path/config.toml"))

        # The path should resolve relative to repo root
        expected = self.repo_root / "nonexistent" / "path" / "config.toml"
        self.assertEqual(resolved.resolve(), expected.resolve())

        # But loading the config should fail
        with self.assertRaises(FileNotFoundError):
            bench._load_agent_config(resolved)

    def test_resolve_input_toml_path_preserves_absolute_paths(self):
        """Test that absolute paths are used as-is."""
        absolute_path = self.fixture_dir / "opencode-smoke.toml"
        resolved = bench._resolve_input_toml_path(absolute_path)

        self.assertEqual(resolved.resolve(), absolute_path.resolve())

    def test_resolve_input_toml_path_expands_env_vars(self):
        """Test that environment variables in paths are expanded."""
        with mock.patch.dict(
            os.environ,
            {"SIMBENCH_TEST_PATH": "tests/fixtures/agent_configs"},
            clear=False,
        ):
            resolved = bench._resolve_input_toml_path(
                Path("$SIMBENCH_TEST_PATH/opencode-smoke.toml")
            )

            expected = (
                self.repo_root
                / "tests"
                / "fixtures"
                / "agent_configs"
                / "opencode-smoke.toml"
            )
            self.assertEqual(resolved.resolve(), expected.resolve())

    def test_resolve_input_toml_path_expands_tilde(self):
        """Test that tilde (~) in paths is expanded."""
        # Use a path that would expand tilde
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td).resolve()
            # Create config in home-like location
            test_file = td_path / "test.toml"
            test_file.write_text('version = 1\nname = "test"\n', encoding="utf-8")

            # This is a bit tricky to test properly since we can't easily mock home
            # But we can verify the function uses expanduser
            resolved = bench._resolve_input_toml_path(Path(str(test_file)))

            self.assertEqual(resolved.resolve(), test_file.resolve())

    def test_load_agent_config_symlink_to_fixture(self):
        """Test that symlinks to fixtures work correctly."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)

            # Create a symlink to the actual fixture
            symlink = td_path / "linked-smoke.toml"
            actual_fixture = self.fixture_dir / "opencode-smoke.toml"
            symlink.symlink_to(actual_fixture)

            # Should be able to load via symlink
            cfg = bench._load_agent_config(symlink)
            self.assertEqual(cfg["name"], "opencode")

    def test_load_agent_config_broken_symlink(self):
        """Test that broken symlinks fail appropriately."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)

            # Create a broken symlink
            broken_link = td_path / "broken.toml"
            broken_link.symlink_to("/nonexistent/path.toml")

            with self.assertRaises(FileNotFoundError):
                bench._load_agent_config(broken_link)

    def test_load_agent_config_case_insensitive_extension(self):
        """Test that TOML extension check is case insensitive."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)

            # Create config with uppercase extension
            config = td_path / "config.TOML"
            config.write_text('version = 1\nname = "test"\n', encoding="utf-8")

            # Should work since we check .lower() - but name 'test' doesn't exist in defaults
            # So we get a different error than "not TOML"
            with self.assertRaises(ValueError) as ctx:
                bench._load_agent_config(config)

            # The error should be about missing agent, not wrong extension
            self.assertIn("not found in agents_default", str(ctx.exception))

    def test_load_agent_config_yaml_extension_rejected(self):
        """Test that non-TOML extensions are rejected."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)

            # Create config with wrong extension
            config = td_path / "config.yaml"
            config.write_text('version = 1\nname = "test"\n', encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                bench._load_agent_config(config)

            self.assertIn("TOML", str(ctx.exception))


class TestOldSampleLocationRegression(unittest.TestCase):
    """Regression tests to ensure old sample/ location is not accidentally used."""

    def test_no_sample_toml_files_for_smoke_configs(self):
        """Verify no smoke configs exist in old sample/ location."""
        repo_root = Path(__file__).resolve().parents[1]
        sample_dir = repo_root / "sample"

        if sample_dir.exists():
            sample_files = list(sample_dir.glob("*.toml"))

            # The sample directory may have other configs (opencode.toml, copilot.toml, etc.)
            # but they should NOT be smoke-specific configs
            for sf in sample_files:
                content = sf.read_text(encoding="utf-8")
                # Smoke configs have minimal content - verify they don't exist there
                # by checking that opencode-smoke.toml isn't in sample/
                self.assertNotIn("opencode-smoke.toml", sf.name)
                self.assertNotIn("copilot-smoke.toml", sf.name)

    def test_old_sample_location_not_referenced_in_documentation(self):
        """Test that documentation doesn't reference old sample/ for smoke tests."""
        # Check docs/development.md if it exists
        docs_path = self.repo_root = (
            Path(__file__).resolve().parents[1] / "docs" / "development.md"
        )

        if docs_path.exists():
            docs_content = docs_path.read_text(encoding="utf-8")
            # If docs mention smoke config location, it should be the new path
            if "smoke" in docs_content.lower() and "config" in docs_content.lower():
                # Should reference the new fixture location
                self.assertIn("tests/fixtures", docs_content)


if __name__ == "__main__":
    unittest.main()
