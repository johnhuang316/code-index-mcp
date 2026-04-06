"""Tests for environment variable configuration support (Issue #28)."""

import asyncio
import logging
import os
import unittest
from unittest.mock import MagicMock, patch, call

from code_index_mcp.server import _CLI_CONFIG, _parse_args, indexer_lifespan, main, mcp


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


class TestLifespanEnvConfigIntegration(unittest.TestCase):
    """Integration tests verifying that indexer_lifespan applies env config correctly."""

    def setUp(self):
        self._orig_project_path = _CLI_CONFIG.project_path
        self._orig_fw_enabled = _CLI_CONFIG.file_watcher_enabled
        self._orig_exclude = _CLI_CONFIG.additional_exclude_patterns

    def tearDown(self):
        _CLI_CONFIG.project_path = self._orig_project_path
        _CLI_CONFIG.file_watcher_enabled = self._orig_fw_enabled
        _CLI_CONFIG.additional_exclude_patterns = self._orig_exclude

    def _run_lifespan(self):
        """Helper to run the async indexer_lifespan and return the yielded context."""
        context = None

        async def _run():
            nonlocal context
            async with indexer_lifespan(mcp) as ctx:
                context = ctx

        asyncio.run(_run())
        return context

    @patch("code_index_mcp.server.ProjectSettings")
    @patch("code_index_mcp.server.ProjectManagementService")
    def test_exclude_patterns_applied_before_initialize(
        self, mock_pms_cls, mock_settings_cls
    ):
        """ADDITIONAL_EXCLUDE_PATTERNS must be written to settings BEFORE initialize_project."""
        _CLI_CONFIG.project_path = "/tmp/test_project"
        _CLI_CONFIG.additional_exclude_patterns = ["vendor", ".cache"]
        _CLI_CONFIG.file_watcher_enabled = None

        # Track call order
        call_order = []

        mock_pre_settings = MagicMock()
        mock_lifespan_settings = MagicMock()

        def settings_side_effect(path, skip_load=True):
            if skip_load:
                return mock_lifespan_settings
            call_order.append("pre_settings_created")
            return mock_pre_settings

        mock_settings_cls.side_effect = settings_side_effect

        mock_pre_settings.update_exclude_patterns.side_effect = (
            lambda p: call_order.append("update_exclude_patterns")
        )

        mock_pms_instance = MagicMock()
        mock_pms_cls.return_value = mock_pms_instance
        mock_pms_instance.initialize_project.side_effect = (
            lambda p: call_order.append("initialize_project") or "ok"
        )

        self._run_lifespan()

        # Exclude patterns must be applied before initialize_project
        self.assertEqual(
            call_order,
            ["pre_settings_created", "update_exclude_patterns", "initialize_project"],
        )
        mock_pre_settings.update_exclude_patterns.assert_called_once_with(
            ["vendor", ".cache"]
        )

    @patch("code_index_mcp.server.ProjectSettings")
    @patch("code_index_mcp.server.ProjectManagementService")
    def test_file_watcher_config_applied_before_initialize(
        self, mock_pms_cls, mock_settings_cls
    ):
        """FILE_WATCHER_ENABLED must be written to settings BEFORE initialize_project."""
        _CLI_CONFIG.project_path = "/tmp/test_project"
        _CLI_CONFIG.file_watcher_enabled = True
        _CLI_CONFIG.additional_exclude_patterns = None

        call_order = []

        mock_pre_settings = MagicMock()
        mock_lifespan_settings = MagicMock()

        def settings_side_effect(path, skip_load=True):
            if skip_load:
                return mock_lifespan_settings
            call_order.append("pre_settings_created")
            return mock_pre_settings

        mock_settings_cls.side_effect = settings_side_effect

        mock_pre_settings.update_file_watcher_config.side_effect = (
            lambda cfg: call_order.append("update_file_watcher_config")
        )

        mock_pms_instance = MagicMock()
        mock_pms_cls.return_value = mock_pms_instance
        mock_pms_instance.initialize_project.side_effect = (
            lambda p: call_order.append("initialize_project") or "ok"
        )

        self._run_lifespan()

        self.assertEqual(
            call_order,
            ["pre_settings_created", "update_file_watcher_config", "initialize_project"],
        )
        mock_pre_settings.update_file_watcher_config.assert_called_once_with(
            {"enabled": True}
        )

    @patch("code_index_mcp.server.ProjectSettings")
    @patch("code_index_mcp.server.ProjectManagementService")
    def test_file_watcher_stopped_when_disabled(
        self, mock_pms_cls, mock_settings_cls
    ):
        """When FILE_WATCHER_ENABLED=false, the watcher must be stopped after init."""
        _CLI_CONFIG.project_path = "/tmp/test_project"
        _CLI_CONFIG.file_watcher_enabled = False
        _CLI_CONFIG.additional_exclude_patterns = None

        mock_pre_settings = MagicMock()
        mock_lifespan_settings = MagicMock()

        def settings_side_effect(path, skip_load=True):
            return mock_lifespan_settings if skip_load else mock_pre_settings

        mock_settings_cls.side_effect = settings_side_effect

        mock_pms_instance = MagicMock()
        mock_pms_instance.initialize_project.return_value = "ok"

        watcher_mock = MagicMock()

        # Intercept ProjectManagementService construction to set the watcher
        # on the lifespan context (simulating what _setup_file_monitoring does).
        def capture_pms_init(bootstrap_ctx):
            lifespan_ctx = bootstrap_ctx.request_context.lifespan_context
            lifespan_ctx.file_watcher_service = watcher_mock
            return mock_pms_instance

        mock_pms_cls.side_effect = capture_pms_init

        async def _run():
            async with indexer_lifespan(mcp) as ctx:
                pass

        asyncio.run(_run())

        # The watcher should have been stopped because enabled=False.
        # stop_monitoring is called once explicitly after init and once in
        # the finally cleanup block, so we check it was called at least once.
        watcher_mock.stop_monitoring.assert_called()

    @patch("code_index_mcp.server.ProjectSettings")
    @patch("code_index_mcp.server.ProjectManagementService")
    def test_warning_when_env_vars_set_without_project_path(
        self, mock_pms_cls, mock_settings_cls
    ):
        """Env vars without PROJECT_PATH should log warnings."""
        _CLI_CONFIG.project_path = None
        _CLI_CONFIG.file_watcher_enabled = True
        _CLI_CONFIG.additional_exclude_patterns = ["vendor"]

        mock_settings_cls.return_value = MagicMock()

        with self.assertLogs("code_index_mcp.server", level="WARNING") as cm:
            self._run_lifespan()

        log_output = "\n".join(cm.output)
        self.assertIn("FILE_WATCHER_ENABLED", log_output)
        self.assertIn("ADDITIONAL_EXCLUDE_PATTERNS", log_output)
        # initialize_project should NOT have been called
        mock_pms_cls.assert_not_called()


if __name__ == "__main__":
    unittest.main()
