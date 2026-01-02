"""
Code indexing utilities for the MCP server.

Deep indexing now relies exclusively on the SQLite backend.

Per-project isolation:
- Use get_index_manager() and get_shallow_index_manager() to get
  managers for the current request's project context.
- These functions use the ProjectManagerCache to return cached,
  project-specific manager instances.
"""

from .qualified_names import generate_qualified_name, normalize_file_path
from .json_index_builder import JSONIndexBuilder, IndexMetadata
from .sqlite_index_builder import SQLiteIndexBuilder
from .sqlite_index_manager import SQLiteIndexManager
from .shallow_index_manager import ShallowIndexManager
from .deep_index_manager import DeepIndexManager
from .models import SymbolInfo, FileInfo


def get_index_manager() -> SQLiteIndexManager:
    """Return the SQLite index manager for the current request context.

    This function returns a project-specific manager when called within
    an HTTP request that has the Mcp-Project-Path header set.
    """
    # Lazy import to avoid circular dependency
    from ..project_manager_cache import get_index_manager_for_request
    return get_index_manager_for_request()


def get_shallow_index_manager() -> ShallowIndexManager:
    """Return the shallow index manager for the current request context.

    This function returns a project-specific manager when called within
    an HTTP request that has the Mcp-Project-Path header set.
    """
    # Lazy import to avoid circular dependency
    from ..project_manager_cache import get_shallow_index_manager_for_request
    return get_shallow_index_manager_for_request()


def get_manager_cache():
    """Get the global manager cache singleton.

    This is useful for cache management operations.
    """
    # Lazy import to avoid circular dependency
    from ..project_manager_cache import get_manager_cache as _get_cache
    return _get_cache()


__all__ = [
    "generate_qualified_name",
    "normalize_file_path",
    "JSONIndexBuilder",
    "IndexMetadata",
    "SQLiteIndexBuilder",
    "SQLiteIndexManager",
    "get_index_manager",
    "ShallowIndexManager",
    "get_shallow_index_manager",
    "get_manager_cache",
    "DeepIndexManager",
    "SymbolInfo",
    "FileInfo",
]
