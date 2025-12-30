"""
SQLite-backed index manager coordinating builder and store.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from .sqlite_index_builder import SQLiteIndexBuilder
from .sqlite_store import SQLiteIndexStore, SQLiteSchemaMismatchError
from ..constants import INDEX_FILE_DB, INDEX_FILE, INDEX_FILE_SHALLOW, SETTINGS_DIR

logger = logging.getLogger(__name__)


class SQLiteIndexManager:
    """Manage lifecycle of SQLite-backed deep index."""

    def __init__(self) -> None:
        self.project_path: Optional[str] = None
        self.index_builder: Optional[SQLiteIndexBuilder] = None
        self.store: Optional[SQLiteIndexStore] = None
        self.temp_dir: Optional[str] = None
        self.index_path: Optional[str] = None
        self.shallow_index_path: Optional[str] = None
        self._shallow_file_list: Optional[List[str]] = None
        self._is_loaded = False
        self._lock = threading.RLock()
        logger.info("Initialized SQLite Index Manager")

    def set_project_path(self, project_path: str, additional_excludes: Optional[List[str]] = None) -> bool:
        """Configure project path and underlying storage location.

        Args:
            project_path: Path to the project directory to index
            additional_excludes: Optional list of additional directory/file
                patterns to exclude from indexing (e.g., ['vendor', 'custom_deps'])

        Returns:
            True if configuration succeeded, False otherwise
        """
        with self._lock:
            if not project_path or not isinstance(project_path, str):
                logger.error("Invalid project path: %s", project_path)
                return False

            project_path = project_path.strip()
            if not project_path or not os.path.isdir(project_path):
                logger.error("Project path does not exist: %s", project_path)
                return False

            self.project_path = project_path
            project_hash = _hash_project_path(project_path)
            self.temp_dir = os.path.join(tempfile.gettempdir(), SETTINGS_DIR, project_hash)
            os.makedirs(self.temp_dir, exist_ok=True)

            self.index_path = os.path.join(self.temp_dir, INDEX_FILE_DB)
            legacy_path = os.path.join(self.temp_dir, INDEX_FILE)
            if os.path.exists(legacy_path):
                try:
                    os.remove(legacy_path)
                    logger.info("Removed legacy JSON index at %s", legacy_path)
                except OSError as exc:  # pragma: no cover - best effort
                    logger.warning("Failed to remove legacy index %s: %s", legacy_path, exc)

            self.shallow_index_path = os.path.join(self.temp_dir, INDEX_FILE_SHALLOW)
            self.store = SQLiteIndexStore(self.index_path)
            self.index_builder = SQLiteIndexBuilder(project_path, self.store, additional_excludes)
            self._is_loaded = False
            logger.info("SQLite index storage: %s", self.index_path)
            if additional_excludes:
                logger.info("Additional excludes: %s", additional_excludes)
            return True

    def build_index(self, force_rebuild: bool = False) -> bool:
        """Build or rebuild the SQLite index."""
        with self._lock:
            if not self.index_builder:
                logger.error("Index builder not initialized")
                return False
            try:
                stats = self.index_builder.build_index()
                logger.info(
                    "SQLite index build complete: %s files, %s symbols",
                    stats.get("files"),
                    stats.get("symbols"),
                )
                self._is_loaded = True
                return True
            except SQLiteSchemaMismatchError:
                logger.warning("Schema mismatch detected; recreating database")
                self.store.clear()  # type: ignore[union-attr]
                stats = self.index_builder.build_index()
                logger.info(
                    "SQLite index rebuild after schema reset: %s files, %s symbols",
                    stats.get("files"),
                    stats.get("symbols"),
                )
                self._is_loaded = True
                return True
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("Failed to build SQLite index: %s", exc)
                self._is_loaded = False
                return False

    def load_index(self) -> bool:
        """Validate that an index database exists and schema is current."""
        with self._lock:
            if not self.store:
                logger.error("Index store not initialized")
                return False
            try:
                self.store.initialize_schema()
                with self.store.connect() as conn:
                    metadata = self.store.get_metadata(conn, "index_metadata")
            except SQLiteSchemaMismatchError:
                logger.info("Schema mismatch on load; forcing rebuild on next build_index()")
                self._is_loaded = False
                return False
            except Exception as exc:  # pragma: no cover
                logger.error("Failed to load SQLite index: %s", exc)
                self._is_loaded = False
                return False
            self._is_loaded = metadata is not None
            return self._is_loaded

    def refresh_index(self) -> bool:
        """Force rebuild of the SQLite index."""
        with self._lock:
            logger.info("Refreshing SQLite deep index...")
            if self.build_index(force_rebuild=True):
                return self.load_index()
            return False

    def build_shallow_index(self) -> bool:
        """Build the shallow index file list using existing builder helper."""
        with self._lock:
            if not self.index_builder or not self.project_path or not self.shallow_index_path:
                logger.error("Index builder not initialized for shallow index")
                return False
            try:
                file_list = self.index_builder.build_shallow_file_list()
                with open(self.shallow_index_path, "w", encoding="utf-8") as handle:
                    json.dump(file_list, handle, ensure_ascii=False)
                self._shallow_file_list = file_list
                return True
            except Exception as exc:  # pragma: no cover
                logger.error("Failed to build shallow index: %s", exc)
                return False

    def load_shallow_index(self) -> bool:
        """Load shallow index from disk."""
        with self._lock:
            if not self.shallow_index_path or not os.path.exists(self.shallow_index_path):
                return False
            try:
                with open(self.shallow_index_path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                if isinstance(data, list):
                    self._shallow_file_list = [_normalize_path(p) for p in data if isinstance(p, str)]
                    return True
            except Exception as exc:  # pragma: no cover
                logger.error("Failed to load shallow index: %s", exc)
            return False

    def find_files(self, pattern: str = "*") -> List[str]:
        """Find files from the shallow index using glob semantics."""
        with self._lock:
            if not isinstance(pattern, str):
                logger.error("Pattern must be a string, got %s", type(pattern))
                return []
            pattern = pattern.strip() or "*"
            norm_pattern = pattern.replace("\\\\", "/").replace("\\", "/")
            regex = _compile_glob_regex(norm_pattern)

            if self._shallow_file_list is None:
                if not self.load_shallow_index():
                    if self.build_shallow_index():
                        self.load_shallow_index()

            files = list(self._shallow_file_list or [])
            if norm_pattern == "*":
                return files
            return [f for f in files if regex.match(f)]

    def get_file_summary(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Return summary information for a file from SQLite storage."""
        with self._lock:
            if not isinstance(file_path, str):
                logger.error("File path must be a string, got %s", type(file_path))
                return None
            if not self.store or not self._is_loaded:
                if not self.load_index():
                    return None

            normalized = _normalize_path(file_path)
            with self.store.connect() as conn:
                row = conn.execute(
                    """
                    SELECT id, language, line_count, imports, exports, docstring
                    FROM files WHERE path = ?
                    """,
                    (normalized,),
                ).fetchone()

                if not row:
                    logger.warning("File not found in index: %s", normalized)
                    return None

                symbol_rows = conn.execute(
                    """
                    SELECT type, line, signature, docstring, called_by, short_name
                    FROM symbols
                    WHERE file_id = ?
                    ORDER BY line ASC
                    """,
                    (row["id"],),
                ).fetchall()

            imports = _safe_json_loads(row["imports"])
            exports = _safe_json_loads(row["exports"])

            categorized = _categorize_symbols(symbol_rows)

            return {
                "file_path": normalized,
                "language": row["language"],
                "line_count": row["line_count"],
                "symbol_count": len(symbol_rows),
                "functions": categorized["functions"],
                "classes": categorized["classes"],
                "methods": categorized["methods"],
                "imports": imports,
                "exports": exports,
                "docstring": row["docstring"],
            }

    def get_index_stats(self) -> Dict[str, Any]:
        """Return basic statistics for the current index."""
        with self._lock:
            if not self.store:
                return {"status": "not_loaded"}
            try:
                with self.store.connect() as conn:
                    metadata = self.store.get_metadata(conn, "index_metadata")
            except SQLiteSchemaMismatchError:
                return {"status": "not_loaded"}
            if not metadata:
                return {"status": "not_loaded"}
            return {
                "status": "loaded" if self._is_loaded else "not_loaded",
                "indexed_files": metadata.get("indexed_files", 0),
                "total_symbols": metadata.get("total_symbols", 0),
                "symbol_types": metadata.get("symbol_types", {}),
                "languages": metadata.get("languages", []),
                "project_path": metadata.get("project_path"),
                "timestamp": metadata.get("timestamp"),
            }

    def cleanup(self) -> None:
        """Reset internal state."""
        with self._lock:
            self.project_path = None
            self.index_builder = None
            self.store = None
            self.temp_dir = None
            self.index_path = None
            self._shallow_file_list = None
            self._is_loaded = False


def _hash_project_path(project_path: str) -> str:
    import hashlib

    return hashlib.md5(project_path.encode()).hexdigest()[:12]


def _compile_glob_regex(pattern: str):
    i = 0
    out = []
    special = ".^$+{}[]|()"
    while i < len(pattern):
        c = pattern[i]
        if c == "*":
            if i + 1 < len(pattern) and pattern[i + 1] == "*":
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c in special:
            out.append("\\" + c)
        else:
            out.append(c)
        i += 1
    return re.compile("^" + "".join(out) + "$")


def _normalize_path(path: str) -> str:
    result = path.replace("\\\\", "/").replace("\\", "/")
    if result.startswith("./"):
        result = result[2:]
    return result


def _safe_json_loads(value: Any) -> List[Any]:
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def _categorize_symbols(symbol_rows) -> Dict[str, List[Dict[str, Any]]]:
    functions: List[Dict[str, Any]] = []
    classes: List[Dict[str, Any]] = []
    methods: List[Dict[str, Any]] = []

    for row in symbol_rows:
        symbol_type = row["type"]
        called_by = _safe_json_loads(row["called_by"])
        info = {
            "name": row["short_name"],
            "called_by": called_by,
            "line": row["line"],
            "signature": row["signature"],
            "docstring": row["docstring"],
        }

        signature = row["signature"] or ""
        if signature.startswith("def ") and "::" in signature:
            methods.append(info)
        elif signature.startswith("def "):
            functions.append(info)
        elif signature.startswith("class ") or symbol_type == "class":
            classes.append(info)
        else:
            if symbol_type == "method":
                methods.append(info)
            elif symbol_type == "class":
                classes.append(info)
            else:
                functions.append(info)

    functions.sort(key=lambda item: item.get("line") or 0)
    classes.sort(key=lambda item: item.get("line") or 0)
    methods.sort(key=lambda item: item.get("line") or 0)

    return {
        "functions": functions,
        "classes": classes,
        "methods": methods,
    }
