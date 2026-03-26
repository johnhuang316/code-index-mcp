"""
Project Configuration Tool - Pure technical component for project configuration operations.

This tool handles low-level project configuration operations without any business logic.
"""

import os
from typing import Dict, Any, Optional
from pathlib import Path

from ...project_settings import ProjectSettings


class ProjectConfigTool:
    """
    Pure technical component for project configuration operations.

    This tool provides low-level configuration management capabilities
    without any business logic or decision making.
    """

    def __init__(self):
        self._settings: Optional[ProjectSettings] = None
        self._project_path: Optional[str] = None

    def initialize_settings(self, project_path: str) -> ProjectSettings:
        """
        Initialize project settings for the given path.

        Args:
            project_path: Absolute path to the project directory

        Returns:
            ProjectSettings instance

        Raises:
            ValueError: If project path is invalid
        """
        if not Path(project_path).exists():
            raise ValueError(f"Project path does not exist: {project_path}")

        if not Path(project_path).is_dir():
            raise ValueError(f"Project path is not a directory: {project_path}")

        self._project_path = project_path
        self._settings = ProjectSettings(project_path, skip_load=False)

        return self._settings

    def load_existing_index(self) -> Optional[Dict[str, Any]]:
        """
        Load existing index data if available.

        Returns:
            Index data dictionary or None if not available

        Raises:
            RuntimeError: If settings not initialized
        """
        if not self._settings:
            raise RuntimeError("Settings not initialized. Call initialize_settings() first.")

        try:
            return self._settings.load_index()
        except Exception:
            return None

    def save_project_config(self, config_data: Dict[str, Any]) -> None:
        """
        Save project configuration data.

        Args:
            config_data: Configuration data to save

        Raises:
            RuntimeError: If settings not initialized
        """
        if not self._settings:
            raise RuntimeError("Settings not initialized")

        self._settings.save_config(config_data)

    def save_index_data(self, index_data: Dict[str, Any]) -> None:
        """
        Save index data to persistent storage.

        Args:
            index_data: Index data to save

        Raises:
            RuntimeError: If settings not initialized
        """
        if not self._settings:
            raise RuntimeError("Settings not initialized")

        self._settings.save_index(index_data)

    def check_index_version(self) -> bool:
        """
        Check whether the current deep index is present and loaded.

        Returns:
            True if a deep index exists and is loaded, False if it needs rebuild

        Raises:
            RuntimeError: If settings not initialized
        """
        if not self._settings:
            raise RuntimeError("Settings not initialized")

        # Check if the deep index exists and is loaded
        from ...indexing import get_index_manager
        index_manager = get_index_manager()
        
        # Set project path if available
        if self._settings.base_path:
            index_manager.set_project_path(self._settings.base_path)
            stats = index_manager.get_index_stats()
            return stats.get('status') == 'loaded'
        
        return False

    def cleanup_legacy_files(self) -> None:
        """
        Clean up legacy index files.

        Raises:
            RuntimeError: If settings not initialized
        """
        if not self._settings:
            raise RuntimeError("Settings not initialized")

        self._settings.cleanup_legacy_files()

    def get_search_tool_info(self) -> Dict[str, Any]:
        """
        Get information about available search tools.

        Returns:
            Dictionary with search tool information

        Raises:
            RuntimeError: If settings not initialized
        """
        if not self._settings:
            raise RuntimeError("Settings not initialized")

        search_tool = self._settings.get_preferred_search_tool()
        return {
            'available': search_tool is not None,
            'name': search_tool.name if search_tool else None,
            'description': "Advanced search enabled" if search_tool else "Basic search available"
        }

    def get_file_watcher_config(self) -> Dict[str, Any]:
        """
        Get file watcher configuration.

        Returns:
            File watcher configuration dictionary

        Raises:
            RuntimeError: If settings not initialized
        """
        if not self._settings:
            raise RuntimeError("Settings not initialized")

        return self._settings.get_file_watcher_config()

    def create_default_config(self, project_path: str) -> Dict[str, Any]:
        """
        Create default project configuration.

        Args:
            project_path: Project path for the configuration

        Returns:
            Default configuration dictionary
        """
        from ...utils import FileFilter
        
        file_filter = FileFilter()
        return {
            "base_path": project_path,
            "supported_extensions": list(file_filter.supported_extensions),
            "last_indexed": None,
            "file_watcher": self.get_file_watcher_config() if self._settings else {}
        }

    def validate_project_path(self, path: str) -> Optional[str]:
        """
        Validate project path.

        Args:
            path: Path to validate

        Returns:
            Error message if invalid, None if valid
        """
        if not path or not path.strip():
            return "Project path cannot be empty"

        try:
            norm_path = os.path.normpath(path)
            abs_path = os.path.abspath(norm_path)
        except (OSError, ValueError) as e:
            return f"Invalid path format: {str(e)}"

        if not os.path.exists(abs_path):
            return f"Path does not exist: {abs_path}"

        if not os.path.isdir(abs_path):
            return f"Path is not a directory: {abs_path}"

        return None

    def normalize_project_path(self, path: str) -> str:
        """
        Normalize and get absolute project path.

        Args:
            path: Path to normalize

        Returns:
            Normalized absolute path
        """
        norm_path = os.path.normpath(path)
        return os.path.abspath(norm_path)

    def get_settings_path(self) -> Optional[str]:
        """
        Get the settings directory path.

        Returns:
            Settings directory path or None if not initialized
        """
        return self._settings.settings_path if self._settings else None

    def get_project_path(self) -> Optional[str]:
        """
        Get the current project path.

        Returns:
            Project path or None if not set
        """
        return self._project_path

    def get_basic_project_structure(self, project_path: str) -> Dict[str, Any]:
        """
        Get basic project directory structure.

        Args:
            project_path: Path to analyze

        Returns:
            Basic directory structure dictionary
        """
        from ...utils import FileFilter
        
        file_filter = FileFilter()
        
        def build_tree(path: str, max_depth: int = 3, current_depth: int = 0) -> Dict[str, Any]:
            """Build directory tree with limited depth using centralized filtering."""
            if current_depth >= max_depth:
                return {"type": "directory", "truncated": True}

            try:
                items = []
                path_obj = Path(path)

                for item in sorted(path_obj.iterdir()):
                    if item.is_dir():
                        # Use centralized directory filtering
                        if not file_filter.should_exclude_directory(item.name):
                            items.append({
                                "name": item.name,
                                "type": "directory",
                                "children": build_tree(str(item), max_depth, current_depth + 1)
                            })
                    else:
                        # Use centralized file filtering
                        if not file_filter.should_exclude_file(item):
                            items.append({
                                "name": item.name,
                                "type": "file",
                                "size": item.stat().st_size if item.exists() else 0
                            })

                return {"type": "directory", "children": items}

            except (OSError, PermissionError):
                return {"type": "directory", "error": "Access denied"}

        try:
            root_name = Path(project_path).name
            structure = {
                "name": root_name,
                "path": project_path,
                "type": "directory",
                "children": build_tree(project_path)["children"]
            }
            return structure

        except Exception as e:
            return {
                "error": f"Failed to build project structure: {e}",
                "path": project_path
            }
