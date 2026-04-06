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
        """When FILE_WATCHER_ENABLED=false, the watcher is cleaned up at shutdown."""
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

        # The watcher is cleaned up in the finally block at shutdown.
        # With the new fix, _setup_file_monitoring() skips starting when
        # disabled, so only the finally cleanup calls stop_monitoring.
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


class TestExcludePatternsUsedByIndexing(unittest.TestCase):
    """Verify _get_exclude_patterns() reads project-level additional_exclude_patterns."""

    def _make_mock_ctx(self, config_data):
        """Create a mock MCP context whose settings.load_config() returns config_data."""
        mock_settings = MagicMock()
        mock_settings.load_config.return_value = config_data
        mock_settings.get_file_watcher_config.return_value = {
            "enabled": True,
            "debounce_seconds": 6.0,
            "monitored_extensions": [],
            "observer_type": "auto",
        }
        ctx = MagicMock()
        ctx.request_context.lifespan_context.settings = mock_settings
        ctx.request_context.lifespan_context.base_path = "/tmp/project"
        ctx.request_context.lifespan_context.file_count = 0
        ctx.request_context.lifespan_context.file_watcher_service = None
        return ctx

    @patch("code_index_mcp.services.project_management_service.get_index_manager")
    @patch("code_index_mcp.services.project_management_service.get_shallow_index_manager")
    def test_project_management_reads_project_level_patterns(self, mock_shallow, mock_deep):
        """Env-configured exclude patterns are returned by _get_exclude_patterns()."""
        from code_index_mcp.services.project_management_service import ProjectManagementService

        config = {"additional_exclude_patterns": ["vendor", ".cache"]}
        ctx = self._make_mock_ctx(config)
        svc = ProjectManagementService(ctx)
        patterns = svc._get_exclude_patterns()
        self.assertIn("vendor", patterns)
        self.assertIn(".cache", patterns)

    @patch("code_index_mcp.services.project_management_service.get_index_manager")
    @patch("code_index_mcp.services.project_management_service.get_shallow_index_manager")
    def test_project_management_reads_fw_level_exclude_patterns(self, mock_shallow, mock_deep):
        """File-watcher-level exclude_patterns are also returned."""
        from code_index_mcp.services.project_management_service import ProjectManagementService

        config = {"file_watcher": {"exclude_patterns": ["build", "dist"]}}
        ctx = self._make_mock_ctx(config)
        svc = ProjectManagementService(ctx)
        patterns = svc._get_exclude_patterns()
        self.assertIn("build", patterns)
        self.assertIn("dist", patterns)

    @patch("code_index_mcp.services.project_management_service.get_index_manager")
    @patch("code_index_mcp.services.project_management_service.get_shallow_index_manager")
    def test_project_management_merges_both_pattern_sources(self, mock_shallow, mock_deep):
        """Both project-level and file-watcher-level patterns are merged."""
        from code_index_mcp.services.project_management_service import ProjectManagementService

        config = {
            "additional_exclude_patterns": ["vendor"],
            "file_watcher": {"exclude_patterns": ["build"]},
        }
        ctx = self._make_mock_ctx(config)
        svc = ProjectManagementService(ctx)
        patterns = svc._get_exclude_patterns()
        self.assertIn("vendor", patterns)
        self.assertIn("build", patterns)

    @patch("code_index_mcp.services.index_management_service.get_index_manager")
    @patch("code_index_mcp.services.index_management_service.get_shallow_index_manager")
    @patch("code_index_mcp.services.index_management_service.DeepIndexManager")
    def test_index_management_reads_project_level_patterns(
        self, mock_deep_wrapper, mock_shallow, mock_deep
    ):
        """IndexManagementService._get_exclude_patterns() reads project-level patterns."""
        from code_index_mcp.services.index_management_service import IndexManagementService

        config = {"additional_exclude_patterns": ["vendor", ".cache"]}
        ctx = self._make_mock_ctx(config)
        svc = IndexManagementService(ctx)
        patterns = svc._get_exclude_patterns()
        self.assertIn("vendor", patterns)
        self.assertIn(".cache", patterns)


class TestFileWatcherDisabledPreventsStartup(unittest.TestCase):
    """Verify FILE_WATCHER_ENABLED=false prevents watcher from starting."""

    @patch("code_index_mcp.services.project_management_service.get_index_manager")
    @patch("code_index_mcp.services.project_management_service.get_shallow_index_manager")
    def test_setup_file_monitoring_skips_when_disabled(self, mock_shallow, mock_deep):
        """_setup_file_monitoring returns 'monitoring_disabled' without calling start_monitoring."""
        from code_index_mcp.services.project_management_service import ProjectManagementService

        mock_settings = MagicMock()
        mock_settings.get_file_watcher_config.return_value = {
            "enabled": False,
            "debounce_seconds": 6.0,
            "monitored_extensions": [],
            "observer_type": "auto",
        }
        mock_settings.load_config.return_value = {"file_watcher": {"enabled": False}}

        ctx = MagicMock()
        ctx.request_context.lifespan_context.settings = mock_settings
        ctx.request_context.lifespan_context.base_path = "/tmp/project"
        ctx.request_context.lifespan_context.file_count = 0
        ctx.request_context.lifespan_context.file_watcher_service = None

        svc = ProjectManagementService(ctx)
        # Replace watcher tool with a mock so we can verify it's never called
        mock_watcher_tool = MagicMock()
        svc._watcher_tool = mock_watcher_tool

        result = svc._setup_file_monitoring("/tmp/project")

        self.assertEqual(result, "monitoring_disabled")
        # start_monitoring must NOT have been called on the watcher tool
        mock_watcher_tool.start_monitoring.assert_not_called()

    @patch("code_index_mcp.services.project_management_service.get_index_manager")
    @patch("code_index_mcp.services.project_management_service.get_shallow_index_manager")
    def test_setup_file_monitoring_proceeds_when_enabled(self, mock_shallow, mock_deep):
        """_setup_file_monitoring proceeds normally when enabled=True."""
        from code_index_mcp.services.project_management_service import ProjectManagementService

        mock_settings = MagicMock()
        mock_settings.get_file_watcher_config.return_value = {
            "enabled": True,
            "debounce_seconds": 6.0,
            "monitored_extensions": [],
            "observer_type": "auto",
        }
        mock_settings.load_config.return_value = {"file_watcher": {"enabled": True}}

        ctx = MagicMock()
        ctx.request_context.lifespan_context.settings = mock_settings
        ctx.request_context.lifespan_context.base_path = "/tmp/project"
        ctx.request_context.lifespan_context.file_count = 0
        ctx.request_context.lifespan_context.file_watcher_service = None

        svc = ProjectManagementService(ctx)
        # Mock the watcher tool to return success
        svc._watcher_tool = MagicMock()
        svc._watcher_tool.start_monitoring.return_value = True
        result = svc._setup_file_monitoring("/tmp/project")

        self.assertEqual(result, "monitoring_active")
        svc._watcher_tool.start_monitoring.assert_called_once()


class TestBootstrapSettingsIdentity(unittest.TestCase):
    """Verify the lifespan context.settings is the SAME instance that has env config."""

    def setUp(self):
        self._orig_project_path = _CLI_CONFIG.project_path
        self._orig_fw_enabled = _CLI_CONFIG.file_watcher_enabled
        self._orig_exclude = _CLI_CONFIG.additional_exclude_patterns

    def tearDown(self):
        _CLI_CONFIG.project_path = self._orig_project_path
        _CLI_CONFIG.file_watcher_enabled = self._orig_fw_enabled
        _CLI_CONFIG.additional_exclude_patterns = self._orig_exclude

    @patch("code_index_mcp.server.ProjectManagementService")
    @patch("code_index_mcp.server.ProjectSettings")
    def test_context_settings_is_pre_settings_after_env_config(
        self, mock_settings_cls, mock_pms_cls
    ):
        """After env config is applied, context.settings must be the pre_settings instance."""
        _CLI_CONFIG.project_path = "/tmp/test_project"
        _CLI_CONFIG.additional_exclude_patterns = ["vendor"]
        _CLI_CONFIG.file_watcher_enabled = False

        mock_pre_settings = MagicMock(name="pre_settings")
        mock_lifespan_settings = MagicMock(name="lifespan_settings")

        def settings_side_effect(path, skip_load=True):
            if skip_load:
                return mock_lifespan_settings
            return mock_pre_settings

        mock_settings_cls.side_effect = settings_side_effect

        mock_pms_instance = MagicMock()
        mock_pms_instance.initialize_project.return_value = "ok"
        mock_pms_cls.return_value = mock_pms_instance

        captured_context = None

        async def _run():
            nonlocal captured_context
            async with indexer_lifespan(mcp) as ctx:
                captured_context = ctx

        asyncio.run(_run())

        # The context.settings must be the pre_settings (env-configured) instance,
        # NOT the original lifespan_settings (empty, skip_load=True).
        self.assertIs(captured_context.settings, mock_pre_settings)

    @patch("code_index_mcp.server.ProjectManagementService")
    @patch("code_index_mcp.server.ProjectSettings")
    def test_service_receives_env_configured_settings(
        self, mock_settings_cls, mock_pms_cls
    ):
        """The ProjectManagementService constructed during bootstrap must see env config
        in context.settings, so _get_exclude_patterns() returns the right values."""
        _CLI_CONFIG.project_path = "/tmp/test_project"
        _CLI_CONFIG.additional_exclude_patterns = ["vendor", ".cache"]
        _CLI_CONFIG.file_watcher_enabled = False

        mock_pre_settings = MagicMock(name="pre_settings")
        mock_lifespan_settings = MagicMock(name="lifespan_settings")

        def settings_side_effect(path, skip_load=True):
            if skip_load:
                return mock_lifespan_settings
            return mock_pre_settings

        mock_settings_cls.side_effect = settings_side_effect

        # Capture the context that ProjectManagementService is constructed with
        captured_bootstrap_settings = []

        def capture_pms(bootstrap_ctx):
            settings = bootstrap_ctx.request_context.lifespan_context.settings
            captured_bootstrap_settings.append(settings)
            mock_instance = MagicMock()
            mock_instance.initialize_project.return_value = "ok"
            return mock_instance

        mock_pms_cls.side_effect = capture_pms

        async def _run():
            async with indexer_lifespan(mcp) as ctx:
                pass

        asyncio.run(_run())

        # The settings seen by ProjectManagementService must be the pre_settings
        self.assertEqual(len(captured_bootstrap_settings), 1)
        self.assertIs(captured_bootstrap_settings[0], mock_pre_settings)

    @patch("code_index_mcp.server.ProjectManagementService")
    @patch("code_index_mcp.server.ProjectSettings")
    def test_watcher_disabled_config_on_context_settings(
        self, mock_settings_cls, mock_pms_cls
    ):
        """When FILE_WATCHER_ENABLED=false, update_file_watcher_config is called on the
        instance that ends up in context.settings."""
        _CLI_CONFIG.project_path = "/tmp/test_project"
        _CLI_CONFIG.file_watcher_enabled = False
        _CLI_CONFIG.additional_exclude_patterns = None

        mock_pre_settings = MagicMock(name="pre_settings")
        mock_lifespan_settings = MagicMock(name="lifespan_settings")

        def settings_side_effect(path, skip_load=True):
            if skip_load:
                return mock_lifespan_settings
            return mock_pre_settings

        mock_settings_cls.side_effect = settings_side_effect

        mock_pms_instance = MagicMock()
        mock_pms_instance.initialize_project.return_value = "ok"
        mock_pms_cls.return_value = mock_pms_instance

        captured_context = None

        async def _run():
            nonlocal captured_context
            async with indexer_lifespan(mcp) as ctx:
                captured_context = ctx

        asyncio.run(_run())

        self.assertIs(captured_context.settings, mock_pre_settings)
        mock_pre_settings.update_file_watcher_config.assert_called_once_with(
            {"enabled": False}
        )


class TestWatcherRebuildExcludePatterns(unittest.TestCase):
    """Verify watcher rebuild callback passes exclude patterns."""

    @patch("code_index_mcp.services.project_management_service.get_index_manager")
    @patch("code_index_mcp.services.project_management_service.get_shallow_index_manager")
    def test_rebuild_callback_passes_exclude_patterns(self, mock_shallow_fn, mock_deep_fn):
        """The watcher rebuild callback must pass exclude patterns to set_project_path."""
        from code_index_mcp.services.project_management_service import ProjectManagementService

        mock_settings = MagicMock()
        mock_settings.get_file_watcher_config.return_value = {
            "enabled": True,
            "debounce_seconds": 6.0,
            "monitored_extensions": [],
            "observer_type": "auto",
        }
        mock_settings.load_config.return_value = {
            "additional_exclude_patterns": ["vendor", ".cache"],
            "file_watcher": {"exclude_patterns": ["build"]},
        }

        ctx = MagicMock()
        ctx.request_context.lifespan_context.settings = mock_settings
        ctx.request_context.lifespan_context.base_path = "/tmp/project"
        ctx.request_context.lifespan_context.file_count = 0
        ctx.request_context.lifespan_context.file_watcher_service = None

        svc = ProjectManagementService(ctx)

        # Mock watcher tool to capture the callback
        mock_watcher_tool = MagicMock()
        mock_watcher_tool.start_monitoring.return_value = True
        svc._watcher_tool = mock_watcher_tool

        # Mock shallow manager
        mock_shallow = MagicMock()
        mock_shallow.set_project_path.return_value = True
        mock_shallow.build_index.return_value = True
        mock_shallow.get_file_list.return_value = ["a.py", "b.py"]
        svc._shallow_manager = mock_shallow

        svc._setup_file_monitoring("/tmp/project")

        # Extract the rebuild callback that was passed to start_monitoring
        mock_watcher_tool.start_monitoring.assert_called_once()
        rebuild_callback = mock_watcher_tool.start_monitoring.call_args[0][1]

        # Reset the mock so we can track the callback's call
        mock_shallow.reset_mock()
        mock_shallow.set_project_path.return_value = True
        mock_shallow.build_index.return_value = True
        mock_shallow.get_file_list.return_value = ["a.py"]

        # Invoke the callback (simulating a file change)
        rebuild_callback()

        # Verify set_project_path was called WITH exclude patterns
        mock_shallow.set_project_path.assert_called_once()
        call_args = mock_shallow.set_project_path.call_args
        # Should have excludes as second positional arg
        excludes_arg = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("excludes", [])
        self.assertIn("vendor", excludes_arg)
        self.assertIn(".cache", excludes_arg)
        self.assertIn("build", excludes_arg)


if __name__ == "__main__":
    unittest.main()
