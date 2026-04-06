"""Tests for environment variable configuration support (Issue #28)."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add src to path if not already there
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from code_index_mcp.server import _CLI_CONFIG, _parse_args, main


class TestEnvVarProjectPath(unittest.TestCase):
    """Tests for PROJECT_PATH environment variable support."""

    def setUp(self):
        # Save original CLI config state
        self._orig_project_path = _CLI_CONFIG.project_path
        self._orig_fw_enabled = _CLI_CONFIG.file_watcher_enabled
        self._orig_exclude = _CLI_CONFIG.additional_exclude_patterns

    def tearDown(self):
        # Restore CLI config state
        _CLI_CONFIG.project_path = self._orig_project_path
        _CLI_CONFIG.file_watcher_enabled = self._orig_fw_enabled
        _CLI_CONFIG.additional_exclude_patterns = self._orig_exclude

    @patch("code_index_mcp.server.mcp.run")
    def test_project_path_from_env(self, mock_run):
        """PROJECT_PATH env var sets the project path."""
        with patch.dict(os.environ, {"PROJECT_PATH": "/tmp/my_project"}, clear=False):
            main([])
        self.assertEqual(_CLI_CONFIG.project_path, "/tmp/my_project")

    @patch("code_index_mcp.server.mcp.run")
    def test_cli_project_path_overrides_env(self, mock_run):
        """CLI --project-path takes precedence over PROJECT_PATH env var."""
        with patch.dict(
            os.environ, {"PROJECT_PATH": "/tmp/env_project"}, clear=False
        ):
            main(["--project-path", "/tmp/cli_project"])
        self.assertEqual(_CLI_CONFIG.project_path, "/tmp/cli_project")

    @patch("code_index_mcp.server.mcp.run")
    def test_no_project_path(self, mock_run):
        """No project path when neither CLI nor env var is set."""
        env = os.environ.copy()
        env.pop("PROJECT_PATH", None)
        with patch.dict(os.environ, env, clear=True):
            main([])
        self.assertIsNone(_CLI_CONFIG.project_path)


class TestEnvVarFileWatcher(unittest.TestCase):
    """Tests for FILE_WATCHER_ENABLED environment variable support."""

    def setUp(self):
        self._orig_project_path = _CLI_CONFIG.project_path
        self._orig_fw_enabled = _CLI_CONFIG.file_watcher_enabled
        self._orig_exclude = _CLI_CONFIG.additional_exclude_patterns

    def tearDown(self):
        _CLI_CONFIG.project_path = self._orig_project_path
        _CLI_CONFIG.file_watcher_enabled = self._orig_fw_enabled
        _CLI_CONFIG.additional_exclude_patterns = self._orig_exclude

    @patch("code_index_mcp.server.mcp.run")
    def test_file_watcher_enabled_true(self, mock_run):
        """FILE_WATCHER_ENABLED=true sets file watcher enabled."""
        with patch.dict(os.environ, {"FILE_WATCHER_ENABLED": "true"}, clear=False):
            main([])
        self.assertTrue(_CLI_CONFIG.file_watcher_enabled)

    @patch("code_index_mcp.server.mcp.run")
    def test_file_watcher_enabled_yes(self, mock_run):
        """FILE_WATCHER_ENABLED=yes is recognized as truthy."""
        with patch.dict(os.environ, {"FILE_WATCHER_ENABLED": "yes"}, clear=False):
            main([])
        self.assertTrue(_CLI_CONFIG.file_watcher_enabled)

    @patch("code_index_mcp.server.mcp.run")
    def test_file_watcher_enabled_one(self, mock_run):
        """FILE_WATCHER_ENABLED=1 is recognized as truthy."""
        with patch.dict(os.environ, {"FILE_WATCHER_ENABLED": "1"}, clear=False):
            main([])
        self.assertTrue(_CLI_CONFIG.file_watcher_enabled)

    @patch("code_index_mcp.server.mcp.run")
    def test_file_watcher_enabled_false(self, mock_run):
        """FILE_WATCHER_ENABLED=false sets file watcher disabled."""
        with patch.dict(os.environ, {"FILE_WATCHER_ENABLED": "false"}, clear=False):
            main([])
        self.assertFalse(_CLI_CONFIG.file_watcher_enabled)

    @patch("code_index_mcp.server.mcp.run")
    def test_file_watcher_enabled_no(self, mock_run):
        """FILE_WATCHER_ENABLED=no is recognized as falsy."""
        with patch.dict(os.environ, {"FILE_WATCHER_ENABLED": "no"}, clear=False):
            main([])
        self.assertFalse(_CLI_CONFIG.file_watcher_enabled)

    @patch("code_index_mcp.server.mcp.run")
    def test_file_watcher_enabled_zero(self, mock_run):
        """FILE_WATCHER_ENABLED=0 is recognized as falsy."""
        with patch.dict(os.environ, {"FILE_WATCHER_ENABLED": "0"}, clear=False):
            main([])
        self.assertFalse(_CLI_CONFIG.file_watcher_enabled)

    @patch("code_index_mcp.server.mcp.run")
    def test_file_watcher_enabled_unset(self, mock_run):
        """Unset FILE_WATCHER_ENABLED results in None."""
        env = os.environ.copy()
        env.pop("FILE_WATCHER_ENABLED", None)
        with patch.dict(os.environ, env, clear=True):
            main([])
        self.assertIsNone(_CLI_CONFIG.file_watcher_enabled)

    @patch("code_index_mcp.server.mcp.run")
    def test_file_watcher_enabled_invalid(self, mock_run):
        """Invalid FILE_WATCHER_ENABLED value results in None."""
        with patch.dict(
            os.environ, {"FILE_WATCHER_ENABLED": "maybe"}, clear=False
        ):
            main([])
        self.assertIsNone(_CLI_CONFIG.file_watcher_enabled)


class TestEnvVarExcludePatterns(unittest.TestCase):
    """Tests for ADDITIONAL_EXCLUDE_PATTERNS environment variable support."""

    def setUp(self):
        self._orig_project_path = _CLI_CONFIG.project_path
        self._orig_fw_enabled = _CLI_CONFIG.file_watcher_enabled
        self._orig_exclude = _CLI_CONFIG.additional_exclude_patterns

    def tearDown(self):
        _CLI_CONFIG.project_path = self._orig_project_path
        _CLI_CONFIG.file_watcher_enabled = self._orig_fw_enabled
        _CLI_CONFIG.additional_exclude_patterns = self._orig_exclude

    @patch("code_index_mcp.server.mcp.run")
    def test_exclude_patterns_single(self, mock_run):
        """Single exclude pattern is parsed correctly."""
        with patch.dict(
            os.environ, {"ADDITIONAL_EXCLUDE_PATTERNS": "node_modules"}, clear=False
        ):
            main([])
        self.assertEqual(_CLI_CONFIG.additional_exclude_patterns, ["node_modules"])

    @patch("code_index_mcp.server.mcp.run")
    def test_exclude_patterns_multiple(self, mock_run):
        """Multiple comma-separated exclude patterns are parsed correctly."""
        with patch.dict(
            os.environ,
            {"ADDITIONAL_EXCLUDE_PATTERNS": "node_modules,dist,.cache"},
            clear=False,
        ):
            main([])
        self.assertEqual(
            _CLI_CONFIG.additional_exclude_patterns,
            ["node_modules", "dist", ".cache"],
        )

    @patch("code_index_mcp.server.mcp.run")
    def test_exclude_patterns_with_spaces(self, mock_run):
        """Whitespace around patterns is trimmed."""
        with patch.dict(
            os.environ,
            {"ADDITIONAL_EXCLUDE_PATTERNS": " node_modules , dist , .cache "},
            clear=False,
        ):
            main([])
        self.assertEqual(
            _CLI_CONFIG.additional_exclude_patterns,
            ["node_modules", "dist", ".cache"],
        )

    @patch("code_index_mcp.server.mcp.run")
    def test_exclude_patterns_empty(self, mock_run):
        """Empty ADDITIONAL_EXCLUDE_PATTERNS results in None."""
        with patch.dict(
            os.environ, {"ADDITIONAL_EXCLUDE_PATTERNS": ""}, clear=False
        ):
            main([])
        self.assertIsNone(_CLI_CONFIG.additional_exclude_patterns)

    @patch("code_index_mcp.server.mcp.run")
    def test_exclude_patterns_unset(self, mock_run):
        """Unset ADDITIONAL_EXCLUDE_PATTERNS results in None."""
        env = os.environ.copy()
        env.pop("ADDITIONAL_EXCLUDE_PATTERNS", None)
        with patch.dict(os.environ, env, clear=True):
            main([])
        self.assertIsNone(_CLI_CONFIG.additional_exclude_patterns)

    @patch("code_index_mcp.server.mcp.run")
    def test_exclude_patterns_empty_items_filtered(self, mock_run):
        """Empty items from consecutive commas are filtered out."""
        with patch.dict(
            os.environ,
            {"ADDITIONAL_EXCLUDE_PATTERNS": "node_modules,,dist,,,"},
            clear=False,
        ):
            main([])
        self.assertEqual(
            _CLI_CONFIG.additional_exclude_patterns,
            ["node_modules", "dist"],
        )


if __name__ == "__main__":
    unittest.main()
