"""
JSON Index Manager - Manages the lifecycle of the JSON-based index.

This replaces the SCIP unified_index_manager with a simpler approach
focused on fast JSON-based indexing and querying.
"""

import hashlib
import json
import logging
import os
import re
import tempfile
import threading
import fnmatch
from pathlib import Path
from typing import Dict, List, Optional, Any

from .json_index_builder import JSONIndexBuilder
from ..constants import SETTINGS_DIR, INDEX_FILE, INDEX_FILE_SHALLOW

logger = logging.getLogger(__name__)


class JSONIndexManager:
    """Manages JSON-based code index lifecycle and storage."""

    def __init__(self):
        self.project_path: Optional[str] = None
        self.index_builder: Optional[JSONIndexBuilder] = None
        self.temp_dir: Optional[str] = None
        self.index_path: Optional[str] = None
        self.shallow_index_path: Optional[str] = None
        self._shallow_file_list: Optional[List[str]] = None
        self._lock = threading.RLock()
        logger.info("Initialized JSON Index Manager")

    def set_project_path(self, project_path: str) -> bool:
        """Set the project path and initialize index storage."""
        with self._lock:
            try:
                # Input validation
                if not project_path or not isinstance(project_path, str):
                    logger.error(f"Invalid project path: {project_path}")
                    return False

                project_path = project_path.strip()
                if not project_path:
                    logger.error("Project path cannot be empty")
                    return False

                if not os.path.isdir(project_path):
                    logger.error(f"Project path does not exist: {project_path}")
                    return False

                self.project_path = project_path
                self.index_builder = JSONIndexBuilder(project_path)

                # Create temp directory for index storage
                project_hash = hashlib.md5(project_path.encode()).hexdigest()[:12]
                self.temp_dir = os.path.join(tempfile.gettempdir(), SETTINGS_DIR, project_hash)
                os.makedirs(self.temp_dir, exist_ok=True)

                self.index_path = os.path.join(self.temp_dir, INDEX_FILE)
                self.shallow_index_path = os.path.join(self.temp_dir, INDEX_FILE_SHALLOW)

                logger.info(f"Set project path: {project_path}")
                logger.info(f"Index storage: {self.index_path}")
                return True

            except Exception as e:
                logger.error(f"Failed to set project path: {e}")
                return False

    def build_index(self, force_rebuild: bool = False) -> bool:
        """Build or rebuild the index."""
        with self._lock:
            if not self.index_builder or not self.project_path:
                logger.error("Index builder not initialized")
                return False

            try:
                # Check if we need to rebuild
                if not force_rebuild and self._is_index_fresh():
                    logger.info("Index is fresh, skipping rebuild")
                    return True

                logger.info("Building JSON index...")
                index = self.index_builder.build_index()

                # Save to disk
                self.index_builder.save_index(index, self.index_path)

                logger.info(f"Successfully built index with {len(index['symbols'])} symbols")
                return True

            except Exception as e:
                logger.error(f"Failed to build index: {e}")
                return False

    def load_index(self) -> bool:
        """Load existing index from disk."""
        with self._lock:
            if not self.index_builder or not self.index_path:
                logger.error("Index manager not initialized")
                return False

            try:
                index = self.index_builder.load_index(self.index_path)
                if index:
                    logger.info(f"Loaded index with {len(index['symbols'])} symbols")
                    return True
                else:
                    logger.warning("No existing index found")
                    return False

            except Exception as e:
                logger.error(f"Failed to load index: {e}")
                return False

    def build_shallow_index(self) -> bool:
        """Build and save the minimal shallow index (file list)."""
        with self._lock:
            if not self.index_builder or not self.project_path or not self.shallow_index_path:
                logger.error("Index builder not initialized for shallow index")
                return False

            try:
                file_list = self.index_builder.build_shallow_file_list()
                # Persist as a JSON array for minimal overhead
                with open(self.shallow_index_path, 'w', encoding='utf-8') as f:
                    json.dump(file_list, f, ensure_ascii=False)
                self._shallow_file_list = file_list
                logger.info(f"Saved shallow index with {len(file_list)} files to {self.shallow_index_path}")
                return True
            except Exception as e:
                logger.error(f"Failed to build shallow index: {e}")
                return False

    def load_shallow_index(self) -> bool:
        """Load shallow index (file list) from disk into memory."""
        with self._lock:
            try:
                if not self.shallow_index_path or not os.path.exists(self.shallow_index_path):
                    logger.warning("No existing shallow index found")
                    return False
                with open(self.shallow_index_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if not isinstance(data, list):
                        logger.error("Shallow index format invalid (expected list)")
                        return False
                    # Normalize paths
                    normalized = []
                    for p in data:
                        if isinstance(p, str):
                            q = p.replace('\\\\', '/').replace('\\', '/')
                            if q.startswith('./'):
                                q = q[2:]
                            normalized.append(q)
                    self._shallow_file_list = normalized
                    logger.info(f"Loaded shallow index with {len(normalized)} files")
                    return True
            except Exception as e:
                logger.error(f"Failed to load shallow index: {e}")
                return False

    def refresh_index(self) -> bool:
        """Refresh the index (rebuild and reload)."""
        with self._lock:
            logger.info("Refreshing index...")
            if self.build_index(force_rebuild=True):
                return self.load_index()
            return False

    def find_files(self, pattern: str = "*") -> List[str]:
        """
        Find files matching a glob pattern using the SHALLOW file list only.

        Notes:
            - '*' does not cross '/'
            - '**' matches across directories
            - Always sources from the shallow index for consistency and speed
        """
        with self._lock:
            # Input validation
            if not isinstance(pattern, str):
                logger.error(f"Pattern must be a string, got {type(pattern)}")
                return []

            pattern = pattern.strip()
            if not pattern:
                pattern = "*"

            # Normalize to forward slashes
            norm_pattern = pattern.replace('\\\\', '/').replace('\\', '/')

            # Build glob regex: '*' does not cross '/', '**' crosses directories
            regex = self._compile_glob_regex(norm_pattern)

            # Always use shallow index for file discovery
            try:
                if self._shallow_file_list is None:
                    # Try load existing shallow index; if missing, build then load
                    if not self.load_shallow_index():
                        # If still not available, attempt to build
                        if self.build_shallow_index():
                            self.load_shallow_index()

                files = list(self._shallow_file_list or [])

                if norm_pattern == "*":
                    return files

                return [f for f in files if regex.match(f) is not None]

            except Exception as e:
                logger.error(f"Error finding files: {e}")
                return []

    def get_file_summary(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Get summary information for a file.

        This method attempts to retrieve comprehensive file information including
        symbol counts, functions, classes, methods, and imports. If the index
        is not loaded, it will attempt auto-initialization to restore from the
        most recent index state.

        Args:
            file_path: Relative path to the file

        Returns:
            Dictionary containing file summary information, or None if not found
        """
        with self._lock:
            # Input validation
            if not isinstance(file_path, str):
                logger.error(f"File path must be a string, got {type(file_path)}")
                return None

            file_path = file_path.strip()
            if not file_path:
                logger.error("File path cannot be empty")
                return None

            # Try to load cached index if not ready
            if not self.index_builder or not self.index_builder.in_memory_index:
                if not self._try_load_cached_index():
                    logger.warning("Index not loaded and no cached index available")
                    return None

            try:
                # Normalize file path
                file_path = file_path.replace('\\', '/')
                if file_path.startswith('./'):
                    file_path = file_path[2:]

                # Get file info
                file_info = self.index_builder.in_memory_index["files"].get(file_path)
                if not file_info:
                    logger.warning(f"File not found in index: {file_path}")
                    return None

                # Get symbols in file
                symbols = self.index_builder.get_file_symbols(file_path)

                # Categorize symbols by signature
                functions = []
                classes = []
                methods = []

                for s in symbols:
                    signature = s.get("signature", "")
                    if signature:
                        if signature.startswith("def ") and "::" in signature:
                            # Method: contains class context
                            methods.append(s)
                        elif signature.startswith("def "):
                            # Function: starts with def but no class context
                            functions.append(s)
                        elif signature.startswith("class ") or signature is None:
                            # Class: starts with class or has no signature
                            classes.append(s)
                        else:
                            # Default to function for unknown signatures
                            functions.append(s)
                    else:
                        # No signature - try to infer from name patterns or default to function
                        name = s.get("name", "")
                        if name and name[0].isupper():
                            # Capitalized names are likely classes
                            classes.append(s)
                        else:
                            # Default to function
                            functions.append(s)

                return {
                    "file_path": file_path,
                    "language": file_info["language"],
                    "line_count": file_info["line_count"],
                    "symbol_count": len(symbols),
                    "functions": functions,
                    "classes": classes,
                    "methods": methods,
                    "imports": file_info.get("imports", []),
                    "exports": file_info.get("exports", [])
                }

            except Exception as e:
                logger.error(f"Error getting file summary: {e}")
                return None

    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the current index."""
        with self._lock:
            if not self.index_builder or not self.index_builder.in_memory_index:
                return {"status": "not_loaded"}

            try:
                index = self.index_builder.in_memory_index
                metadata = index["metadata"]

                symbol_counts = {}
                for symbol_data in index["symbols"].values():
                    symbol_type = symbol_data.get("type", "unknown")
                    symbol_counts[symbol_type] = symbol_counts.get(symbol_type, 0) + 1

                return {
                    "status": "loaded",
                    "project_path": metadata["project_path"],
                    "indexed_files": metadata["indexed_files"],
                    "total_symbols": len(index["symbols"]),
                    "symbol_types": symbol_counts,
                    "languages": metadata["languages"],
                    "index_version": metadata["index_version"],
                    "timestamp": metadata["timestamp"]
                }

            except Exception as e:
                logger.error(f"Error getting index stats: {e}")
                return {"status": "error", "error": str(e)}

    def _is_index_fresh(self) -> bool:
        """Check if the current index is fresh."""
        if not self.index_path or not os.path.exists(self.index_path):
            return False

        try:
            from code_index_mcp.utils.file_filter import FileFilter as _FileFilter  # pylint: disable=C0415
            file_filter = _FileFilter()

            # Simple freshness check - index exists and is recent
            index_mtime = os.path.getmtime(self.index_path)
            base_path = Path(self.project_path)

            # Check if any source files are newer than index
            for root, dirs, files in os.walk(self.project_path):
                # Filter directories using centralized logic
                dirs[:] = [d for d in dirs if not file_filter.should_exclude_directory(d)]

                for file in files:
                    file_path = Path(root) / file
                    if file_filter.should_process_path(file_path, base_path):
                        if os.path.getmtime(str(file_path)) > index_mtime:
                            return False

            return True

        except Exception as e:
            logger.warning(f"Error checking index freshness: {e}")
            return False

    def _try_load_cached_index(self, expected_project_path: Optional[str] = None) -> bool:
        """
        Try to load a cached index file if available.

        This is a simplified version of auto-initialization that only loads
        a cached index if we can verify it matches the expected project.

        Args:
            expected_project_path: Optional path to verify against cached index

        Returns:
            True if cached index was loaded successfully, False otherwise.
        """
        try:
            # First try to load from current index_path if set
            if self.index_path and os.path.exists(self.index_path):
                return self.load_index()

            # If expected project path provided, try to find its cache
            if expected_project_path:
                project_hash = hashlib.md5(expected_project_path.encode()).hexdigest()[:12]
                temp_dir = os.path.join(tempfile.gettempdir(), SETTINGS_DIR, project_hash)
                index_path = os.path.join(temp_dir, INDEX_FILE)

                if os.path.exists(index_path):
                    # Verify the cached index matches the expected project
                    with open(index_path, 'r', encoding='utf-8') as f:
                        index_data = json.load(f)
                        cached_project = index_data.get('metadata', {}).get('project_path')

                    if cached_project == expected_project_path:
                        self.temp_dir = temp_dir
                        self.index_path = index_path
                        return self.load_index()
                    else:
                        logger.warning(f"Cached index project mismatch: {cached_project} != {expected_project_path}")

            return False

        except Exception as e:
            logger.debug(f"Failed to load cached index: {e}")
            return False

    def cleanup(self):
        """Clean up resources."""
        with self._lock:
            self.project_path = None
            self.index_builder = None
            self.temp_dir = None
            self.index_path = None
            logger.info("Cleaned up JSON Index Manager")

    @staticmethod
    def _compile_glob_regex(pattern: str) -> re.Pattern:
        """
        Compile a glob pattern where '*' does not match '/', and '**' matches across directories.

        Examples:
            src/*.py  -> direct children .py under src
            **/*.py   -> .py at any depth
        """
        # Translate glob to regex
        i = 0
        out = []
        special = ".^$+{}[]|()"
        while i < len(pattern):
            c = pattern[i]
            if c == '*':
                if i + 1 < len(pattern) and pattern[i + 1] == '*':
                    # '**' -> match across directories
                    out.append('.*')
                    i += 2
                    continue
                else:
                    out.append('[^/]*')
            elif c == '?':
                out.append('[^/]')
            elif c in special:
                out.append('\\' + c)
            else:
                out.append(c)
            i += 1
        regex_str = '^' + ''.join(out) + '$'
        return re.compile(regex_str)


# Global instance
_index_manager = JSONIndexManager()


def get_index_manager() -> JSONIndexManager:
    """Get the global index manager instance."""
    return _index_manager
