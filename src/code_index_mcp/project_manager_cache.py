"""
Project Manager Cache - Per-project index manager instances.

This module provides caching of index managers by project path,
enabling multiple projects to be indexed simultaneously without interference.
"""

from __future__ import annotations

import logging
import threading
from typing import Dict, Optional, Tuple

from .indexing.shallow_index_manager import ShallowIndexManager
from .indexing.sqlite_index_manager import SQLiteIndexManager
from .request_context import get_request_project_path

logger = logging.getLogger(__name__)


class ProjectManagerCache:
    """Cache of index managers keyed by project path.

    This enables multiple projects to maintain independent index state
    when accessed through the shared MCP daemon.
    """

    def __init__(self):
        self._shallow_managers: Dict[str, ShallowIndexManager] = {}
        self._sqlite_managers: Dict[str, SQLiteIndexManager] = {}
        self._lock = threading.RLock()

        # Fallback managers for when no project path is set
        self._default_shallow = ShallowIndexManager()
        self._default_sqlite = SQLiteIndexManager()

    def get_shallow_manager(self, project_path: Optional[str] = None) -> ShallowIndexManager:
        """Get or create a ShallowIndexManager for the given project path.

        Args:
            project_path: Explicit project path, or None to use request context

        Returns:
            ShallowIndexManager for the project
        """
        # Use request context if no explicit path provided
        path = project_path or get_request_project_path()

        if not path:
            return self._default_shallow

        with self._lock:
            if path not in self._shallow_managers:
                logger.info(f"[Cache] Creating ShallowIndexManager for: {path}")
                manager = ShallowIndexManager()
                self._shallow_managers[path] = manager
            return self._shallow_managers[path]

    def get_sqlite_manager(self, project_path: Optional[str] = None) -> SQLiteIndexManager:
        """Get or create a SQLiteIndexManager for the given project path.

        Args:
            project_path: Explicit project path, or None to use request context

        Returns:
            SQLiteIndexManager for the project
        """
        # Use request context if no explicit path provided
        path = project_path or get_request_project_path()

        if not path:
            return self._default_sqlite

        with self._lock:
            if path not in self._sqlite_managers:
                logger.info(f"[Cache] Creating SQLiteIndexManager for: {path}")
                manager = SQLiteIndexManager()
                self._sqlite_managers[path] = manager
            return self._sqlite_managers[path]

    def get_managers(self, project_path: Optional[str] = None) -> Tuple[ShallowIndexManager, SQLiteIndexManager]:
        """Get both managers for a project path.

        Args:
            project_path: Explicit project path, or None to use request context

        Returns:
            Tuple of (ShallowIndexManager, SQLiteIndexManager)
        """
        return (
            self.get_shallow_manager(project_path),
            self.get_sqlite_manager(project_path)
        )

    def clear_project(self, project_path: str) -> None:
        """Clear cached managers for a specific project.

        Args:
            project_path: Project path to clear
        """
        with self._lock:
            if project_path in self._shallow_managers:
                self._shallow_managers[project_path].cleanup()
                del self._shallow_managers[project_path]
            if project_path in self._sqlite_managers:
                self._sqlite_managers[project_path].cleanup()
                del self._sqlite_managers[project_path]
            logger.info(f"[Cache] Cleared managers for: {project_path}")

    def clear_all(self) -> None:
        """Clear all cached managers."""
        with self._lock:
            for manager in self._shallow_managers.values():
                manager.cleanup()
            for manager in self._sqlite_managers.values():
                manager.cleanup()
            self._shallow_managers.clear()
            self._sqlite_managers.clear()
            self._default_shallow.cleanup()
            self._default_sqlite.cleanup()
            self._default_shallow = ShallowIndexManager()
            self._default_sqlite = SQLiteIndexManager()
            logger.info("[Cache] Cleared all managers")

    def get_cached_projects(self) -> list:
        """Get list of currently cached project paths.

        Returns:
            List of project paths with cached managers
        """
        with self._lock:
            # Union of both caches
            paths = set(self._shallow_managers.keys())
            paths.update(self._sqlite_managers.keys())
            return sorted(paths)


# Global singleton cache
_manager_cache = ProjectManagerCache()


def get_manager_cache() -> ProjectManagerCache:
    """Get the global manager cache singleton."""
    return _manager_cache


def get_shallow_index_manager_for_request() -> ShallowIndexManager:
    """Get ShallowIndexManager for the current request context.

    This is the preferred way to get a manager in request handlers.
    """
    return _manager_cache.get_shallow_manager()


def get_index_manager_for_request() -> SQLiteIndexManager:
    """Get SQLiteIndexManager for the current request context.

    This is the preferred way to get a manager in request handlers.
    """
    return _manager_cache.get_sqlite_manager()
