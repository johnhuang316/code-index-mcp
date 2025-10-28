"""
Code indexing utilities for the MCP server.

Deep indexing now relies exclusively on the SQLite backend.
"""

from .qualified_names import generate_qualified_name, normalize_file_path
from .json_index_builder import JSONIndexBuilder, IndexMetadata
from .sqlite_index_builder import SQLiteIndexBuilder
from .sqlite_index_manager import SQLiteIndexManager
from .shallow_index_manager import ShallowIndexManager, get_shallow_index_manager
from .deep_index_manager import DeepIndexManager
from .models import SymbolInfo, FileInfo

_sqlite_index_manager = SQLiteIndexManager()


def get_index_manager() -> SQLiteIndexManager:
    """Return the singleton SQLite index manager."""
    return _sqlite_index_manager


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
    "DeepIndexManager",
    "SymbolInfo",
    "FileInfo",
]
