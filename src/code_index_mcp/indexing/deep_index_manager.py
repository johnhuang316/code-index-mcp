"""
Deep Index Manager - Wrapper around the SQLite index manager.

This class provides a clear semantic separation from the shallow manager while
delegating operations to the SQLite-backed implementation.
"""

from __future__ import annotations

from typing import Optional, Dict, Any, List

from .sqlite_index_manager import SQLiteIndexManager


class DeepIndexManager:
    """Thin wrapper over SQLiteIndexManager to expose deep-index API."""

    def __init__(self) -> None:
        self._mgr = SQLiteIndexManager()

    # Expose a subset of API to keep callers simple
    def set_project_path(self, project_path: str) -> bool:
        return self._mgr.set_project_path(project_path)

    def build_index(self, force_rebuild: bool = False) -> bool:
        return self._mgr.build_index(force_rebuild=force_rebuild)

    def load_index(self) -> bool:
        return self._mgr.load_index()

    def refresh_index(self) -> bool:
        return self._mgr.refresh_index()

    def find_files(self, pattern: str = "*") -> List[str]:
        return self._mgr.find_files(pattern)

    def get_file_summary(self, file_path: str) -> Optional[Dict[str, Any]]:
        return self._mgr.get_file_summary(file_path)

    def get_index_stats(self) -> Dict[str, Any]:
        return self._mgr.get_index_stats()

    def cleanup(self) -> None:
        self._mgr.cleanup()
