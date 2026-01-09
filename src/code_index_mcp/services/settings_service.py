"""
Settings management service for the Code Index MCP server.

This service handles settings information, statistics,
temporary directory management, and settings cleanup operations.
"""

import os
import tempfile
from typing import Any

from ..constants import SETTINGS_DIR
from ..indexing import get_index_manager
from ..project_settings import ProjectSettings
from ..utils import ResponseFormatter
from .base_service import BaseService


def manage_temp_directory(action: str) -> dict[str, Any]:
    """
    Manage temporary directory operations.

    This is a standalone function that doesn't require project context.
    Handles the logic for create_temp_directory and check_temp_directory MCP tools.

    Args:
        action: The action to perform ('create' or 'check')

    Returns:
        Dictionary with directory information and operation results

    Raises:
        ValueError: If action is invalid or operation fails
    """
    if action not in ["create", "check"]:
        raise ValueError(f"Invalid action: {action}. Must be 'create' or 'check'")

    # Try to get the actual temp directory from index manager, fallback to default
    try:
        # Check ProjectSettings first
        if ProjectSettings.custom_index_root:
            temp_dir = ProjectSettings.custom_index_root
        else:
            index_manager = get_index_manager()
            temp_dir = (
                index_manager.temp_dir
                if index_manager.temp_dir
                else os.path.join(tempfile.gettempdir(), SETTINGS_DIR)
            )
    except Exception:
        temp_dir = os.path.join(tempfile.gettempdir(), SETTINGS_DIR)

    if action == "create":
        existed_before = os.path.exists(temp_dir)

        try:
            # Use ProjectSettings to handle directory creation consistently
            ProjectSettings("", skip_load=True)

            result = ResponseFormatter.directory_info_response(
                temp_directory=temp_dir,
                exists=os.path.exists(temp_dir),
                is_directory=os.path.isdir(temp_dir),
            )
            result["existed_before"] = existed_before
            result["created"] = not existed_before

            return result

        except (OSError, ValueError) as e:
            return ResponseFormatter.directory_info_response(
                temp_directory=temp_dir, exists=False, error=str(e)
            )

    else:  # action == 'check'
        result = ResponseFormatter.directory_info_response(
            temp_directory=temp_dir,
            exists=os.path.exists(temp_dir),
            is_directory=os.path.isdir(temp_dir) if os.path.exists(temp_dir) else False,
        )
        result["temp_root"] = tempfile.gettempdir()

        # If the directory exists, list its contents
        if result["exists"] and result["is_directory"]:
            try:
                contents = os.listdir(temp_dir)
                result["contents"] = contents
                result["subdirectories"] = []

                # Check each subdirectory
                for item in contents:
                    item_path = os.path.join(temp_dir, item)
                    if os.path.isdir(item_path):
                        subdir_info = {
                            "name": item,
                            "path": item_path,
                            "contents": os.listdir(item_path)
                            if os.path.exists(item_path)
                            else [],
                        }
                        result["subdirectories"].append(subdir_info)

            except (OSError, PermissionError) as e:
                result["error"] = str(e)

        return result


class SettingsService(BaseService):
    """
    Service for managing settings and directory operations.

    This service handles:
    - Settings information and statistics
    - Temporary directory management
    - Settings cleanup operations
    - Configuration data access
    """

    def get_settings_info(self) -> dict[str, Any]:
        """
        Get comprehensive settings information.

        Handles the logic for get_settings_info MCP tool.

        Returns:
            Dictionary with settings directory, config, stats, and status information
        """
        temp_dir = os.path.join(tempfile.gettempdir(), SETTINGS_DIR)

        # Get the actual index directory from the index manager
        index_manager = get_index_manager()

        # Check ProjectSettings first for custom root
        if ProjectSettings.custom_index_root:
            actual_temp_dir = ProjectSettings.custom_index_root
        else:
            actual_temp_dir = (
                index_manager.temp_dir if index_manager.temp_dir else temp_dir
            )

        # Check if base_path is set
        if not self.base_path:
            return ResponseFormatter.settings_info_response(
                settings_directory="",
                temp_directory=actual_temp_dir,
                temp_directory_exists=os.path.exists(actual_temp_dir),
                config={},
                stats={},
                exists=False,
                status="not_configured",
                message="Project path not set. Please use set_project_path to set a "
                "project directory first.",
            )

        # Get config and stats
        config = self.settings.load_config() if self.settings else {}
        stats = self.settings.get_stats() if self.settings else {}
        settings_directory = actual_temp_dir
        exists = os.path.exists(settings_directory) if settings_directory else False

        return ResponseFormatter.settings_info_response(
            settings_directory=settings_directory,
            temp_directory=actual_temp_dir,
            temp_directory_exists=os.path.exists(actual_temp_dir),
            config=config,
            stats=stats,
            exists=exists,
        )

    def clear_all_settings(self) -> str:
        """
        Clear all settings and cached data.

        Handles the logic for clear_settings MCP tool.

        Returns:
            Success message confirming settings were cleared
        """
        if self.settings:
            self.settings.clear()

        return "Project settings, index, and cache have been cleared."

    def get_settings_stats(self) -> str:
        """
        Get settings statistics as JSON string.

        Handles the logic for settings://stats MCP resource.

        Returns:
            JSON formatted settings statistics
        """
        if not self.settings:
            stats_data = {"error": "Settings not available"}
        else:
            stats_data = self.settings.get_stats()

        return ResponseFormatter.stats_response(stats_data)
