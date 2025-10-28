"""
SQLite-backed index builder leveraging existing strategy pipeline.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Iterable, List, Optional, Tuple

from .json_index_builder import JSONIndexBuilder
from .sqlite_store import SQLiteIndexStore
from .models import FileInfo, SymbolInfo

logger = logging.getLogger(__name__)


class SQLiteIndexBuilder(JSONIndexBuilder):
    """
    Build the deep index directly into SQLite storage.

    Inherits scanning/strategy utilities from JSONIndexBuilder but writes rows
    to the provided SQLiteIndexStore instead of assembling large dictionaries.
    """

    def __init__(
        self,
        project_path: str,
        store: SQLiteIndexStore,
        additional_excludes: Optional[List[str]] = None,
    ):
        super().__init__(project_path, additional_excludes)
        self.store = store

    def build_index(
        self,
        parallel: bool = True,
        max_workers: Optional[int] = None,
    ) -> Dict[str, int]:
        """
        Build the SQLite index and return lightweight statistics.

        Args:
            parallel: Whether to parse files in parallel.
            max_workers: Optional override for worker count.

        Returns:
            Dictionary with totals for files, symbols, and languages.
        """
        logger.info("Building SQLite index (parallel=%s)...", parallel)
        start_time = time.time()

        files_to_process = self._get_supported_files()
        total_files = len(files_to_process)
        if total_files == 0:
            logger.warning("No files to process")
            with self.store.connect(for_build=True) as conn:
                self._reset_database(conn)
                self._persist_metadata(conn, 0, 0, [], 0, 0, {})
            return {
                "files": 0,
                "symbols": 0,
                "languages": 0,
            }

        specialized_extensions = set(self.strategy_factory.get_specialized_extensions())

        results_iter: Iterable[Tuple[Dict[str, SymbolInfo], Dict[str, FileInfo], str, bool]]

        executor = None

        if parallel and total_files > 1:
            if max_workers is None:
                max_workers = min(os.cpu_count() or 4, total_files)
            logger.info("Using ThreadPoolExecutor with %s workers", max_workers)
            executor = ThreadPoolExecutor(max_workers=max_workers)
            future_to_file = {
                executor.submit(self._process_file, file_path, specialized_extensions): file_path
                for file_path in files_to_process
            }

            def _iter_results():
                for future in as_completed(future_to_file):
                    result = future.result()
                    if result:
                        yield result

            results_iter = _iter_results()
        else:
            logger.info("Using sequential processing")

            def _iter_results_sequential():
                for file_path in files_to_process:
                    result = self._process_file(file_path, specialized_extensions)
                    if result:
                        yield result

            results_iter = _iter_results_sequential()

        languages = set()
        specialized_count = 0
        fallback_count = 0
        pending_calls: List[Tuple[str, str]] = []
        total_symbols = 0
        symbol_types: Dict[str, int] = {}
        processed_files = 0

        self.store.initialize_schema()
        with self.store.connect(for_build=True) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            self._reset_database(conn)

            for symbols, file_info_dict, language, is_specialized in results_iter:
                file_path, file_info = next(iter(file_info_dict.items()))
                file_id = self._insert_file(conn, file_path, file_info)
                file_pending = getattr(file_info, "pending_calls", [])
                if file_pending:
                    pending_calls.extend(file_pending)
                symbol_rows = self._prepare_symbol_rows(symbols, file_id)

                if symbol_rows:
                    conn.executemany(
                        """
                        INSERT INTO symbols(
                            symbol_id,
                            file_id,
                            type,
                            line,
                            signature,
                            docstring,
                            called_by,
                            short_name
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        symbol_rows,
                    )

                languages.add(language)
                processed_files += 1
                total_symbols += len(symbol_rows)

                if is_specialized:
                    specialized_count += 1
                else:
                    fallback_count += 1

                for _, _, symbol_type, _, _, _, _, _ in symbol_rows:
                    key = symbol_type or "unknown"
                    symbol_types[key] = symbol_types.get(key, 0) + 1

            self._persist_metadata(
                conn,
                processed_files,
                total_symbols,
                sorted(languages),
                specialized_count,
                fallback_count,
                symbol_types,
            )
            self._resolve_pending_calls_sqlite(conn, pending_calls)
            try:
                conn.execute("PRAGMA optimize")
            except Exception:  # pragma: no cover - best effort
                pass

        if executor:
            executor.shutdown(wait=True)

        elapsed = time.time() - start_time
        logger.info(
            "SQLite index built: files=%s symbols=%s languages=%s elapsed=%.2fs",
            processed_files,
            total_symbols,
            len(languages),
            elapsed,
        )

        return {
            "files": processed_files,
            "symbols": total_symbols,
            "languages": len(languages),
        }

    # Internal helpers -------------------------------------------------

    def _reset_database(self, conn):
        conn.execute("DELETE FROM symbols")
        conn.execute("DELETE FROM files")
        conn.execute(
            "DELETE FROM metadata WHERE key NOT IN ('schema_version')"
        )

    def _insert_file(self, conn, path: str, file_info: FileInfo) -> int:
        params = (
            path,
            file_info.language,
            file_info.line_count,
            json.dumps(file_info.imports or []),
            json.dumps(file_info.exports or []),
            file_info.package,
            file_info.docstring,
        )
        cur = conn.execute(
            """
            INSERT INTO files(
                path,
                language,
                line_count,
                imports,
                exports,
                package,
                docstring
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            params,
        )
        return cur.lastrowid

    def _prepare_symbol_rows(
        self,
        symbols: Dict[str, SymbolInfo],
        file_id: int,
    ) -> List[Tuple[str, int, Optional[str], Optional[int], Optional[str], Optional[str], str, str]]:
        rows: List[Tuple[str, int, Optional[str], Optional[int], Optional[str], Optional[str], str, str]] = []
        for symbol_id, symbol_info in symbols.items():
            called_by = json.dumps(symbol_info.called_by or [])
            short_name = symbol_id.split("::")[-1]
            rows.append(
                (
                    symbol_id,
                    file_id,
                    symbol_info.type,
                    symbol_info.line,
                    symbol_info.signature,
                    symbol_info.docstring,
                    called_by,
                    short_name,
                )
            )
        return rows

    def _persist_metadata(
        self,
        conn,
        file_count: int,
        symbol_count: int,
        languages: List[str],
        specialized_count: int,
        fallback_count: int,
        symbol_types: Dict[str, int],
    ) -> None:
        metadata = {
            "project_path": self.project_path,
            "indexed_files": file_count,
            "index_version": "3.0.0-sqlite",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "languages": languages,
            "total_symbols": symbol_count,
            "specialized_parsers": specialized_count,
            "fallback_files": fallback_count,
            "symbol_types": symbol_types,
        }
        self.store.set_metadata(conn, "project_path", self.project_path)
        self.store.set_metadata(conn, "index_metadata", metadata)

    def _resolve_pending_calls_sqlite(
        self,
        conn,
        pending_calls: List[Tuple[str, str]]
    ) -> None:
        """Resolve cross-file call relationships directly in SQLite storage."""
        if not pending_calls:
            return

        rows = list(
            conn.execute(
                "SELECT symbol_id, short_name, called_by FROM symbols"
            )
        )
        symbol_map = {row["symbol_id"]: row for row in rows}
        short_index: Dict[str, List[str]] = defaultdict(list)
        for row in rows:
            short_name = row["short_name"]
            if short_name:
                short_index[short_name].append(row["symbol_id"])

        updates: Dict[str, set] = defaultdict(set)

        for caller, called in pending_calls:
            target_ids: List[str] = []
            if called in symbol_map:
                target_ids = [called]
            else:
                if called in short_index:
                    target_ids = short_index[called]
                if not target_ids:
                    suffix = f".{called}"
                    matches: List[str] = []
                    for short_name, ids in short_index.items():
                        if short_name and short_name.endswith(suffix):
                            matches.extend(ids)
                    target_ids = matches

            if len(target_ids) != 1:
                continue

            updates[target_ids[0]].add(caller)

        for symbol_id, callers in updates.items():
            row = symbol_map.get(symbol_id)
            if not row:
                continue
            existing = []
            if row["called_by"]:
                try:
                    existing = json.loads(row["called_by"])
                except json.JSONDecodeError:
                    existing = []
            merged = list(dict.fromkeys(existing + list(callers)))
            conn.execute(
                "UPDATE symbols SET called_by=? WHERE symbol_id=?",
                (json.dumps(merged), symbol_id),
            )
