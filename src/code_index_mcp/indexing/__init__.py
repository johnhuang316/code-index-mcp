"""
Code indexing utilities for the MCP server.

This module provides simple JSON-based indexing optimized for LLM consumption.
"""

# Import utility functions that are still used
from .qualified_names import (
    generate_qualified_name,
    normalize_file_path
)

# New JSON-based indexing system
from .json_index_builder import JSONIndexBuilder, IndexMetadata
from .json_index_manager import JSONIndexManager, get_index_manager
from .shallow_index_manager import ShallowIndexManager, get_shallow_index_manager
from .deep_index_manager import DeepIndexManager
from .models import SymbolInfo, FileInfo

__all__ = [
    'generate_qualified_name',
    'normalize_file_path',
    'JSONIndexBuilder',
    'JSONIndexManager',
    'get_index_manager',
    'ShallowIndexManager',
    'get_shallow_index_manager',
    'DeepIndexManager',
    'SymbolInfo',
    'FileInfo', 
    'IndexMetadata'
]