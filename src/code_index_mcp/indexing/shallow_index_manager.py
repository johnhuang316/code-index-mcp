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
from typing import List, Optional
import re

from .json_index_builder import JSONIndexBuilder
from ..constants import SETTINGS_DIR, INDEX_FILE_SHALLOW

logger = logging.getLogger(__name__)


class ShallowIndexManager:
    """Manage shallow (file-list) index lifecycle and storage."""

    def __init__(self) -> None:
        self.project_path: Optional[str] = None
        self.index_builder: Optional[JSONIndexBuilder] = None
        self.temp_dir: Optional[str] = None
        self.index_path: Optional[str] = None
        self._file_list: Optional[List[str]] = None
        self._lock = threading.RLock()

    def set_project_path(self, project_path: str, additional_excludes: Optional[List[str]] = None) -> bool:
        """Configure project path for shallow indexing.

        Args:
            project_path: Path to the project directory to index
            additional_excludes: Optional list of additional directory/file
                patterns to exclude from indexing (e.g., ['vendor', 'custom_deps'])

        Returns:
            True if configuration succeeded, False otherwise
        """
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
                self.index_builder = JSONIndexBuilder(project_path, additional_excludes)

                project_hash = hashlib.md5(project_path.encode()).hexdigest()[:12]
                self.temp_dir = os.path.join(tempfile.gettempdir(), SETTINGS_DIR, project_hash)
                os.makedirs(self.temp_dir, exist_ok=True)
                self.index_path = os.path.join(self.temp_dir, INDEX_FILE_SHALLOW)
                if additional_excludes:
                    logger.info("Shallow index additional excludes: %s", additional_excludes)
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

    def find_files(self, pattern: str = "*") -> List[str]:
        with self._lock:
            if not isinstance(pattern, str):
                return []
            norm = (pattern.strip() or "*").replace('\\\\','/').replace('\\','/')
            files = self._file_list or []

            # Fast path: wildcard all
            if norm == "*":
                return list(files)

            # 1) Exact, case-sensitive
            exact_regex = self._compile_glob_regex(norm)
            exact_hits = [f for f in files if exact_regex.match(f) is not None]
            if exact_hits or '/' in norm:
                return exact_hits

            # 2) Recursive **/ fallback (case-sensitive)
            recursive_pattern = f"**/{norm}"
            rec_regex = self._compile_glob_regex(recursive_pattern)
            rec_hits = [f for f in files if rec_regex.match(f) is not None]
            if rec_hits:
                return self._dedupe_preserve_order(exact_hits + rec_hits)

            # 3) Case-insensitive (root only)
            ci_regex = self._compile_glob_regex(norm, ignore_case=True)
            ci_hits = [f for f in files if ci_regex.match(f) is not None]
            if ci_hits:
                return self._dedupe_preserve_order(exact_hits + rec_hits + ci_hits)

            # 4) Case-insensitive recursive
            rec_ci_regex = self._compile_glob_regex(recursive_pattern, ignore_case=True)
            rec_ci_hits = [f for f in files if rec_ci_regex.match(f) is not None]
            if rec_ci_hits:
                return self._dedupe_preserve_order(
                    exact_hits + rec_hits + ci_hits + rec_ci_hits
                )

            return []

    @staticmethod
    def _compile_glob_regex(pattern: str, ignore_case: bool = False) -> re.Pattern:
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
        flags = re.IGNORECASE if ignore_case else 0
        return re.compile('^' + ''.join(out) + '$', flags=flags)

    @staticmethod
    def _dedupe_preserve_order(items: List[str]) -> List[str]:
        seen = set()
        result = []
        for item in items:
            if item not in seen:
                seen.add(item)
                result.append(item)
        return result

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

