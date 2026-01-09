import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Add src to path if not already there
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from code_index_mcp.project_settings import ProjectSettings
from code_index_mcp.server import main


class TestServerConfig(unittest.TestCase):
    def setUp(self):
        # Reset ProjectSettings custom root before each test
        if hasattr(ProjectSettings, "custom_index_root"):
            ProjectSettings.custom_index_root = None

    def tearDown(self):
        # Clean up ProjectSettings custom root after each test
        if hasattr(ProjectSettings, "custom_index_root"):
            ProjectSettings.custom_index_root = None

    def test_custom_indexer_path(self):
        """Test that --indexer-path sets the custom index root."""
        custom_root = tempfile.mkdtemp()
        try:
            # Mock sys.argv
            test_args = ["--indexer-path", custom_root]

            # Mock mcp.run to avoid starting server
            with patch("code_index_mcp.server.mcp.run"):
                main(test_args)

            # Verify ProjectSettings was updated
            self.assertEqual(ProjectSettings.custom_index_root, custom_root)

            # Verify ProjectSettings uses it
            settings = ProjectSettings("test_project", skip_load=True)
            self.assertTrue(settings.settings_path.startswith(custom_root))

            # Verify no 'code_indexer' subdir was created inside
            # Expected path: custom_root/hash
            # NOT: custom_root/code_indexer/hash
            # Verify no 'code_indexer' subdir was created inside
            # Expected path: custom_root/hash
            # NOT: custom_root/code_indexer/hash
            self.assertEqual(os.path.dirname(settings.settings_path), custom_root)

        finally:
            shutil.rmtree(custom_root)

    def test_indexer_path_creates_directory(self):
        """Test that the indexer path directory is created if it doesn't exist."""
        temp_dir = tempfile.mkdtemp()
        custom_root = os.path.join(temp_dir, "new_index_root")
        try:
            test_args = ["--indexer-path", custom_root]
            with patch("code_index_mcp.server.mcp.run"):
                main(test_args)

            self.assertTrue(os.path.exists(custom_root))
        finally:
            shutil.rmtree(temp_dir)

    def test_settings_reporting(self):
        """Test that settings reporting reflects custom index root."""
        custom_root = tempfile.mkdtemp()
        ProjectSettings.custom_index_root = custom_root
        try:
            # Import service here to ensure it sees the updated ProjectSettings
            from code_index_mcp.services.settings_service import (
                SettingsService,
                manage_temp_directory,
            )

            # Test manage_temp_directory
            result = manage_temp_directory("check")
            self.assertEqual(result["temp_directory"], custom_root)

            # Test SettingsService
            ctx = MagicMock()
            service = SettingsService(ctx)
            # Mock helper to provide base_path and settings (simulating BaseService behavior)
            service.helper = MagicMock()
            service.helper.base_path = "/tmp"
            service.helper.settings = MagicMock()

            info = service.get_settings_info()
            self.assertEqual(info["temp_directory"], custom_root)

        finally:
            shutil.rmtree(custom_root)

    @patch("code_index_mcp.server.mcp")
    def test_tool_prefix(self, mock_mcp):
        """Test that --tool-prefix renames tools."""

        # Setup mock tools
        mock_tools = {
            "test_tool": MagicMock(name="test_tool"),
            "other_tool": MagicMock(name="other_tool"),
        }
        # Configure names
        mock_tools["test_tool"].name = "test_tool"
        mock_tools["other_tool"].name = "other_tool"

        # Structure the mock to have _tool_manager._tools
        mock_mcp._tool_manager._tools = mock_tools
        mock_mcp._tools = None  # ensure it uses manager

        test_args = ["--tool-prefix", "myctx:"]

        with patch("code_index_mcp.server.mcp.run", MagicMock()):
            # Run main logic
            main(test_args)

            # Check tool renaming in the MOCK object
            # Note: The code modifies existing tools in place AND creates new registry
            # We want to check if the registry was updated

            new_registry = mock_mcp._tool_manager._tools

            # Check keys
            self.assertIn("myctx:test_tool", new_registry)
            self.assertIn("myctx:other_tool", new_registry)
            self.assertNotIn("test_tool", new_registry)  # old keys gone

            # Check names
            self.assertEqual(new_registry["myctx:test_tool"].name, "myctx:test_tool")


if __name__ == "__main__":
    unittest.main()
