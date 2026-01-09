"""
Project Settings Management

This module provides functionality for managing project settings and persistent data
for the Code Index MCP server.
"""

import hashlib
import json
import os
import tempfile
from datetime import datetime

from .constants import CONFIG_FILE, INDEX_FILE, SETTINGS_DIR
from .search.ag import AgStrategy
from .search.base import SearchStrategy
from .search.basic import BasicSearchStrategy
from .search.grep import GrepStrategy
from .search.ripgrep import RipgrepStrategy
from .search.ugrep import UgrepStrategy

# Prioritized list of search strategies
SEARCH_STRATEGY_CLASSES = [
    UgrepStrategy,
    RipgrepStrategy,
    AgStrategy,
    GrepStrategy,
    BasicSearchStrategy,
]


def _get_available_strategies() -> list[SearchStrategy]:
    """
    Detect and return a list of available search strategy instances,
    ordered by preference.
    """
    available = []
    for strategy_class in SEARCH_STRATEGY_CLASSES:
        try:
            strategy = strategy_class()
            if strategy.is_available():
                available.append(strategy)
        except Exception:
            pass
    return available


class ProjectSettings:
    """Class for managing project settings and index data"""

    custom_index_root: str | None = None

    def __init__(self, base_path, skip_load=False):
        """Initialize project settings

        Args:
            base_path (str): Base path of the project
            skip_load (bool): Whether to skip loading files
        """
        self.base_path = base_path
        self.skip_load = skip_load
        self.available_strategies: list[SearchStrategy] = []
        self.refresh_available_strategies()

        # Ensure the base path of the temporary directory exists
        try:
            # Check for custom index root
            if hasattr(self, "custom_index_root") and self.custom_index_root:
                temp_base_dir = self.custom_index_root
            else:
                # Get system temporary directory
                system_temp = tempfile.gettempdir()

                # Check if the system temporary directory exists and is writable
                if not os.path.exists(system_temp):
                    # Try using project directory as fallback if available
                    if base_path and os.path.exists(base_path):
                        system_temp = base_path
                    else:
                        # Use user's home directory as last resort
                        system_temp = os.path.expanduser("~")

                if not os.access(system_temp, os.W_OK):
                    # Try using project directory as fallback if available
                    if (
                        base_path
                        and os.path.exists(base_path)
                        and os.access(base_path, os.W_OK)
                    ):
                        system_temp = base_path
                    else:
                        # Use user's home directory as last resort
                        system_temp = os.path.expanduser("~")

                # Create code_indexer directory
                temp_base_dir = os.path.join(system_temp, SETTINGS_DIR)

            if not os.path.exists(temp_base_dir):
                os.makedirs(temp_base_dir, exist_ok=True)
            else:
                pass
        except Exception:
            # If unable to create temporary directory, use .code_indexer in project directory if available
            if base_path and os.path.exists(base_path):
                temp_base_dir = os.path.join(base_path, ".code_indexer")

            else:
                # Use home directory as last resort
                temp_base_dir = os.path.join(os.path.expanduser("~"), ".code_indexer")

            if not os.path.exists(temp_base_dir):
                os.makedirs(temp_base_dir, exist_ok=True)

        # Use system temporary directory to store index data
        try:
            if base_path:
                # Use hash of project path as unique identifier
                path_hash = hashlib.md5(base_path.encode()).hexdigest()
                self.settings_path = os.path.join(temp_base_dir, path_hash)
            else:
                # If no base path provided, use a default directory
                self.settings_path = os.path.join(temp_base_dir, "default")

            self.ensure_settings_dir()
        except Exception:
            # If error occurs, use .code_indexer in project or home directory as fallback
            if base_path and os.path.exists(base_path):
                fallback_dir = os.path.join(
                    base_path,
                    ".code_indexer",
                    hashlib.md5(base_path.encode()).hexdigest(),
                )
            else:
                fallback_dir = os.path.join(
                    os.path.expanduser("~"),
                    ".code_indexer",
                    "default"
                    if not base_path
                    else hashlib.md5(base_path.encode()).hexdigest(),
                )

            self.settings_path = fallback_dir
            if not os.path.exists(fallback_dir):
                os.makedirs(fallback_dir, exist_ok=True)

    def ensure_settings_dir(self):
        """Ensure settings directory exists"""

        try:
            if not os.path.exists(self.settings_path):
                # Create directory structure
                os.makedirs(self.settings_path, exist_ok=True)
            else:
                pass

            # Check if directory is writable
            if not os.access(self.settings_path, os.W_OK):
                # If directory is not writable, use .code_indexer in project or home directory as fallback
                if (
                    self.base_path
                    and os.path.exists(self.base_path)
                    and os.access(self.base_path, os.W_OK)
                ):
                    fallback_dir = os.path.join(
                        self.base_path,
                        ".code_indexer",
                        os.path.basename(self.settings_path),
                    )
                else:
                    fallback_dir = os.path.join(
                        os.path.expanduser("~"),
                        ".code_indexer",
                        os.path.basename(self.settings_path),
                    )

                self.settings_path = fallback_dir
                if not os.path.exists(fallback_dir):
                    os.makedirs(fallback_dir, exist_ok=True)
        except Exception:
            # If unable to create settings directory, use .code_indexer in project or home directory
            if self.base_path and os.path.exists(self.base_path):
                fallback_dir = os.path.join(
                    self.base_path,
                    ".code_indexer",
                    hashlib.md5(self.base_path.encode()).hexdigest(),
                )
            else:
                fallback_dir = os.path.join(
                    os.path.expanduser("~"),
                    ".code_indexer",
                    "default"
                    if not self.base_path
                    else hashlib.md5(self.base_path.encode()).hexdigest(),
                )

            self.settings_path = fallback_dir
            if not os.path.exists(fallback_dir):
                os.makedirs(fallback_dir, exist_ok=True)

    def get_config_path(self):
        """Get the path to the configuration file"""
        try:
            path = os.path.join(self.settings_path, CONFIG_FILE)
            # Ensure directory exists
            os.makedirs(os.path.dirname(path), exist_ok=True)
            return path
        except Exception:
            # If error occurs, use file in project or home directory as fallback
            if self.base_path and os.path.exists(self.base_path):
                return os.path.join(self.base_path, CONFIG_FILE)
            else:
                return os.path.join(os.path.expanduser("~"), CONFIG_FILE)

    def _get_timestamp(self):
        """Get current timestamp"""
        return datetime.now().isoformat()

    def save_config(self, config):
        """Save configuration data

        Args:
            config (dict): Configuration data
        """
        try:
            config_path = self.get_config_path()
            # Add timestamp
            config["last_updated"] = self._get_timestamp()

            # Ensure directory exists
            os.makedirs(os.path.dirname(config_path), exist_ok=True)

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            return config
        except Exception:
            return config

    def load_config(self):
        """Load configuration data

        Returns:
            dict: Configuration data, or empty dict if file doesn't exist
        """
        # If skip_load is set, return empty dict directly
        if self.skip_load:
            return {}

        try:
            config_path = self.get_config_path()
            if os.path.exists(config_path):
                try:
                    with open(config_path, encoding="utf-8") as f:
                        config = json.load(f)
                    return config
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # If file is corrupted, return empty dict
                    return {}
            else:
                pass
            return {}
        except Exception:
            return {}

    def save_index(self, index_data):
        """Save code index in JSON format

        Args:
            index_data: Index data as dictionary or JSON string
        """
        try:
            index_path = self.get_index_path()

            # Ensure directory exists
            dir_path = os.path.dirname(index_path)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)

            # Check if directory is writable
            if not os.access(dir_path, os.W_OK):
                # Use project or home directory as fallback
                if self.base_path and os.path.exists(self.base_path):
                    index_path = os.path.join(self.base_path, INDEX_FILE)
                else:
                    index_path = os.path.join(os.path.expanduser("~"), INDEX_FILE)

            # Convert to JSON string if it's an object with to_json method
            if hasattr(index_data, "to_json"):
                json_data = index_data.to_json()
            elif isinstance(index_data, str):
                json_data = index_data
            else:
                # Assume it's a dictionary and convert to JSON
                json_data = json.dumps(index_data, indent=2, default=str)

            with open(index_path, "w", encoding="utf-8") as f:
                f.write(json_data)

        except Exception:
            # Try saving to project or home directory
            try:
                if self.base_path and os.path.exists(self.base_path):
                    fallback_path = os.path.join(self.base_path, INDEX_FILE)
                else:
                    fallback_path = os.path.join(os.path.expanduser("~"), INDEX_FILE)

                # Convert to JSON string if it's an object with to_json method
                if hasattr(index_data, "to_json"):
                    json_data = index_data.to_json()
                elif isinstance(index_data, str):
                    json_data = index_data
                else:
                    json_data = json.dumps(index_data, indent=2, default=str)

                with open(fallback_path, "w", encoding="utf-8") as f:
                    f.write(json_data)
            except Exception:
                pass

    def load_index(self):
        """Load code index from JSON format

        Returns:
            dict: Index data, or None if file doesn't exist or has errors
        """
        # If skip_load is set, return None directly
        if self.skip_load:
            return None

        try:
            index_path = self.get_index_path()

            if os.path.exists(index_path):
                try:
                    with open(index_path, encoding="utf-8") as f:
                        index_data = json.load(f)
                    return index_data
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # If file is corrupted, return None
                    return None
                except Exception:
                    return None
            else:
                # Try loading from project or home directory
                if self.base_path and os.path.exists(self.base_path):
                    fallback_path = os.path.join(self.base_path, INDEX_FILE)
                else:
                    fallback_path = os.path.join(os.path.expanduser("~"), INDEX_FILE)
            if os.path.exists(fallback_path):
                try:
                    with open(fallback_path, encoding="utf-8") as f:
                        index_data = json.load(f)
                    return index_data
                except Exception:
                    pass
            return None
        except Exception:
            return None

    def cleanup_legacy_files(self) -> None:
        """Clean up any legacy index files found."""
        try:
            legacy_files = [
                os.path.join(self.settings_path, "file_index.pickle"),
                os.path.join(self.settings_path, "content_cache.pickle"),
                os.path.join(self.settings_path, INDEX_FILE),  # Legacy JSON
            ]

            for legacy_file in legacy_files:
                if os.path.exists(legacy_file):
                    try:
                        os.remove(legacy_file)
                    except Exception:
                        pass
        except Exception:
            pass

    def clear(self):
        """Clear config and index files"""
        try:
            if os.path.exists(self.settings_path):
                # Check if directory is writable
                if not os.access(self.settings_path, os.W_OK):
                    return

                # Delete specific files only (config.json and index.json)
                files_to_delete = [CONFIG_FILE, INDEX_FILE]

                for filename in files_to_delete:
                    file_path = os.path.join(self.settings_path, filename)
                    try:
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                    except Exception:
                        pass

            else:
                pass
        except Exception:
            pass

    def get_stats(self):
        """Get statistics for the settings directory

        Returns:
            dict: Dictionary containing file sizes and update times
        """
        try:
            stats = {
                "settings_path": self.settings_path,
                "exists": os.path.exists(self.settings_path),
                "is_directory": os.path.isdir(self.settings_path)
                if os.path.exists(self.settings_path)
                else False,
                "writable": os.access(self.settings_path, os.W_OK)
                if os.path.exists(self.settings_path)
                else False,
                "files": {},
                "temp_dir": tempfile.gettempdir(),
                "base_path": self.base_path,
            }

            if stats["exists"] and stats["is_directory"]:
                try:
                    # Get all files in the directory
                    all_files = os.listdir(self.settings_path)
                    stats["all_files"] = all_files

                    # Get details for specific files
                    for filename in [CONFIG_FILE, INDEX_FILE]:
                        file_path = os.path.join(self.settings_path, filename)
                        if os.path.exists(file_path):
                            try:
                                file_stats = os.stat(file_path)
                                stats["files"][filename] = {
                                    "path": file_path,
                                    "size_bytes": file_stats.st_size,
                                    "last_modified": datetime.fromtimestamp(
                                        file_stats.st_mtime
                                    ).isoformat(),
                                    "readable": os.access(file_path, os.R_OK),
                                    "writable": os.access(file_path, os.W_OK),
                                }
                            except Exception as e:
                                stats["files"][filename] = {
                                    "path": file_path,
                                    "error": str(e),
                                }
                except Exception as e:
                    stats["list_error"] = str(e)

            # Check fallback path
            if self.base_path and os.path.exists(self.base_path):
                fallback_dir = os.path.join(self.base_path, ".code_indexer")
            else:
                fallback_dir = os.path.join(os.path.expanduser("~"), ".code_indexer")
            stats["fallback_path"] = fallback_dir
            stats["fallback_exists"] = os.path.exists(fallback_dir)
            stats["fallback_is_directory"] = (
                os.path.isdir(fallback_dir) if os.path.exists(fallback_dir) else False
            )

            return stats
        except Exception as e:
            return {
                "error": str(e),
                "settings_path": self.settings_path,
                "temp_dir": tempfile.gettempdir(),
                "base_path": self.base_path,
            }

    def get_search_tools_config(self):
        """Get the configuration of available search tools.

        Returns:
            dict: A dictionary containing the list of available tool names.
        """
        return {
            "available_tools": [s.name for s in self.available_strategies],
            "preferred_tool": self.get_preferred_search_tool().name
            if self.available_strategies
            else None,
        }

    def get_preferred_search_tool(self) -> SearchStrategy | None:
        """Get the preferred search tool based on availability and priority.

        Returns:
            SearchStrategy: An instance of the preferred search strategy, or None.
        """
        if not self.available_strategies:
            self.refresh_available_strategies()

        return self.available_strategies[0] if self.available_strategies else None

    def refresh_available_strategies(self):
        """
        Force a refresh of the available search tools list.
        """

        self.available_strategies = _get_available_strategies()

    def get_file_watcher_config(self) -> dict:
        """
        Get file watcher specific configuration.

        Returns:
            dict: File watcher configuration with defaults
        """
        config = self.load_config()
        default_config = {
            "enabled": True,
            "debounce_seconds": 6.0,
            "additional_exclude_patterns": [],
            "monitored_extensions": [],  # Empty = use all supported extensions
            "exclude_patterns": [
                ".git",
                ".svn",
                ".hg",
                "node_modules",
                "__pycache__",
                ".venv",
                "venv",
                ".DS_Store",
                "Thumbs.db",
                "dist",
                "build",
                "target",
                ".idea",
                ".vscode",
                ".pytest_cache",
                ".coverage",
                ".tox",
                "bin",
                "obj",
            ],
        }

        # Merge with loaded config
        file_watcher_config = config.get("file_watcher", {})
        for key, default_value in default_config.items():
            if key not in file_watcher_config:
                file_watcher_config[key] = default_value

        return file_watcher_config

    def update_file_watcher_config(self, updates: dict) -> None:
        """
        Update file watcher configuration.

        Args:
            updates: Dictionary of configuration updates
        """
        config = self.load_config()
        if "file_watcher" not in config:
            config["file_watcher"] = self.get_file_watcher_config()

        config["file_watcher"].update(updates)
        self.save_config(config)
