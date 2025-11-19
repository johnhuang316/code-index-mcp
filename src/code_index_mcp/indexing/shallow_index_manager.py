"""
Shallow Index Manager - Manages a minimal file-list-only index.

This manager builds and loads a shallow index consisting of relative file
paths only. It is optimized for fast initialization and filename-based
search/browsing. Content parsing and symbol extraction are not performed.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import threading
from typing import List, Optional, Literal
from dataclasses import dataclass
import re

from .json_index_builder import JSONIndexBuilder
from ..constants import SETTINGS_DIR, INDEX_FILE_SHALLOW

logger = logging.getLogger(__name__)


@dataclass
class FileSearchResult:
    """Result of a file search operation with match quality information."""
    files: List[str]
    match_type: Literal["exact", "recursive", "case_insensitive_root", "case_insensitive_recursive", "all", "no_match", "invalid"]
    original_pattern: str
    applied_pattern: str


class ShallowIndexManager:
    """Manage shallow (file-list) index lifecycle and storage."""

    def __init__(self) -> None:
        self.project_path: Optional[str] = None
        self.index_builder: Optional[JSONIndexBuilder] = None
        self.temp_dir: Optional[str] = None
        self.index_path: Optional[str] = None
        self._file_list: Optional[List[str]] = None
        self._lock = threading.RLock()

    def set_project_path(self, project_path: str) -> bool:
        with self._lock:
            try:
                if not isinstance(project_path, str) or not project_path.strip():
                    logger.error("Invalid project path for shallow index")
                    return False
                project_path = project_path.strip()
                if not os.path.isdir(project_path):
                    logger.error(f"Project path does not exist: {project_path}")
                    return False

                self.project_path = project_path
                self.index_builder = JSONIndexBuilder(project_path)

                project_hash = hashlib.md5(project_path.encode()).hexdigest()[:12]
                self.temp_dir = os.path.join(tempfile.gettempdir(), SETTINGS_DIR, project_hash)
                os.makedirs(self.temp_dir, exist_ok=True)
                self.index_path = os.path.join(self.temp_dir, INDEX_FILE_SHALLOW)
                return True
            except Exception as e:  # noqa: BLE001 - centralized logging
                logger.error(f"Failed to set project path (shallow): {e}")
                return False

    def build_index(self) -> bool:
        """Build and persist the shallow file list index."""
        with self._lock:
            if not self.index_builder or not self.index_path:
                logger.error("ShallowIndexManager not initialized")
                return False
            try:
                file_list = self.index_builder.build_shallow_file_list()
                with open(self.index_path, 'w', encoding='utf-8') as f:
                    json.dump(file_list, f, ensure_ascii=False)
                self._file_list = file_list
                logger.info(f"Built shallow index with {len(file_list)} files")
                return True
            except Exception as e:  # noqa: BLE001
                logger.error(f"Failed to build shallow index: {e}")
                return False

    def load_index(self) -> bool:
        """Load shallow index from disk to memory."""
        with self._lock:
            try:
                if not self.index_path or not os.path.exists(self.index_path):
                    return False
                with open(self.index_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    # Normalize slashes/prefix
                    normalized: List[str] = []
                    for p in data:
                        if isinstance(p, str):
                            q = p.replace('\\\\', '/').replace('\\', '/')
                            if q.startswith('./'):
                                q = q[2:]
                            normalized.append(q)
                    self._file_list = normalized
                    return True
                return False
            except Exception as e:  # noqa: BLE001
                logger.error(f"Failed to load shallow index: {e}")
                return False

    def get_file_list(self) -> List[str]:
        with self._lock:
            return list(self._file_list or [])

    def find_files(self, pattern: str = "*") -> FileSearchResult:
        """Find files matching the given pattern with lenient search fallbacks.
        
        Args:
            pattern: Glob pattern to search for (e.g., "*.py", "test_*.js", "users.go")
            
        Returns:
            FileSearchResult containing:
            - files: List of matching file paths
            - match_type: How the files were matched ("exact", "recursive", etc.)
            - original_pattern: The pattern provided by the user
            - applied_pattern: The actual pattern used to find matches
        """
        with self._lock:
            if not isinstance(pattern, str):
                return FileSearchResult(
                    files=[],
                    match_type="invalid",
                    original_pattern=pattern if isinstance(pattern, str) else str(pattern),
                    applied_pattern=""
                )
            
            original_pattern = pattern
            norm = (pattern.strip() or "*").replace('\\\\','/').replace('\\','/')
            
            # Normalize ./ prefix (common in file paths)
            if norm.startswith('./'):
                norm = norm[2:]
            
            files = self._file_list or []
            if norm == "*":
                return FileSearchResult(
                    files=list(files),
                    match_type="all",
                    original_pattern=original_pattern,
                    applied_pattern="*"
                )
            
            # Try the pattern as-is first (case-sensitive)
            regex = self._compile_glob_regex(norm)
            results = [f for f in files if regex.match(f) is not None]
            
            if results:
                return FileSearchResult(
                    files=results,
                    match_type="exact",
                    original_pattern=original_pattern,
                    applied_pattern=norm
                )
            
            # Lenient search strategy:
            # 1. If no results and pattern has no path separators, try recursive search
            # 2. If still no results, try case-insensitive search (both original and recursive)
            if '/' not in norm and not norm.startswith('**/'):
                # Try adding **/ prefix to search recursively in all directories
                lenient_pattern = '**/' + norm
                lenient_regex = self._compile_glob_regex(lenient_pattern)
                results = [f for f in files if lenient_regex.match(f) is not None]
                
                if results:
                    return FileSearchResult(
                        files=results,
                        match_type="recursive",
                        original_pattern=original_pattern,
                        applied_pattern=lenient_pattern
                    )
                
                # Try original pattern case-insensitive (for root files)
                regex_ci = self._compile_glob_regex(norm, case_insensitive=True)
                results = [f for f in files if regex_ci.match(f) is not None]
                
                if results:
                    return FileSearchResult(
                        files=results,
                        match_type="case_insensitive_root",
                        original_pattern=original_pattern,
                        applied_pattern=f"{norm} (case-insensitive)"
                    )
                
                # Try recursive pattern case-insensitive
                lenient_regex_ci = self._compile_glob_regex(lenient_pattern, case_insensitive=True)
                results = [f for f in files if lenient_regex_ci.match(f) is not None]
                
                if results:
                    return FileSearchResult(
                        files=results,
                        match_type="case_insensitive_recursive",
                        original_pattern=original_pattern,
                        applied_pattern=f"{lenient_pattern} (case-insensitive)"
                    )
            
            # No matches found with any strategy
            return FileSearchResult(
                files=[],
                match_type="no_match",
                original_pattern=original_pattern,
                applied_pattern=norm
            )

    @staticmethod
    def _compile_glob_regex(pattern: str, case_insensitive: bool = False) -> re.Pattern:
        i = 0
        out = []
        special = ".^$+{}[]|()"
        while i < len(pattern):
            c = pattern[i]
            if c == '*':
                if i + 1 < len(pattern) and pattern[i + 1] == '*':
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
        
        flags = re.IGNORECASE if case_insensitive else 0
        return re.compile('^' + ''.join(out) + '$', flags)

    def cleanup(self) -> None:
        with self._lock:
            self.project_path = None
            self.index_builder = None
            self.temp_dir = None
            self.index_path = None
            self._file_list = None


# Global singleton
_shallow_manager = ShallowIndexManager()


def get_shallow_index_manager() -> ShallowIndexManager:
    return _shallow_manager


