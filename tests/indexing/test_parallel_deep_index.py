"""Tests for parallel deep indexing configuration and dynamic timeout."""

import os
import threading
from unittest.mock import MagicMock, patch

import pytest

from code_index_mcp.indexing.models import FileInfo, SymbolInfo
from code_index_mcp.indexing.sqlite_index_builder import (
    SQLiteIndexBuilder,
    _compute_parallel_timeout,
    MIN_TIMEOUT_SECONDS,
    MAX_TIMEOUT_SECONDS,
    TIMEOUT_PER_FILE_SECONDS,
)
from code_index_mcp.indexing.sqlite_index_manager import SQLiteIndexManager
from code_index_mcp.indexing.sqlite_store import SQLiteIndexStore
from code_index_mcp.indexing.deep_index_manager import DeepIndexManager


# ---------------------------------------------------------------------------
# Dynamic timeout tests
# ---------------------------------------------------------------------------


class TestComputeParallelTimeout:
    """Tests for _compute_parallel_timeout helper."""

    def test_explicit_timeout_used_as_is(self):
        assert _compute_parallel_timeout(100, explicit_timeout=42) == 42.0

    def test_explicit_zero_timeout(self):
        assert _compute_parallel_timeout(9999, explicit_timeout=0) == 0.0

    def test_small_file_count_uses_minimum(self):
        # 10 files * 0.5 = 5s, but min is 30s
        result = _compute_parallel_timeout(10)
        assert result == MIN_TIMEOUT_SECONDS

    def test_moderate_file_count_scales_linearly(self):
        # 200 files * 0.5 = 100s
        result = _compute_parallel_timeout(200)
        assert result == 200 * TIMEOUT_PER_FILE_SECONDS

    def test_large_file_count_capped_at_maximum(self):
        # 5000 files * 0.5 = 2500s, but max is 600s
        result = _compute_parallel_timeout(5000)
        assert result == MAX_TIMEOUT_SECONDS

    def test_zero_files(self):
        result = _compute_parallel_timeout(0)
        assert result == MIN_TIMEOUT_SECONDS


# ---------------------------------------------------------------------------
# SQLiteIndexBuilder.build_index parameter propagation
# ---------------------------------------------------------------------------


def _make_builder(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    store = SQLiteIndexStore(str(tmp_path / "index.db"))
    builder = SQLiteIndexBuilder(str(project_dir), store)
    return builder, store


def _make_result():
    return (
        {
            "f.py::func": SymbolInfo(
                type="function",
                file="f.py",
                line=1,
                signature="def func():",
            )
        },
        {
            "f.py": FileInfo(
                language="python",
                line_count=1,
                symbols={"functions": ["func"], "classes": []},
                imports=[],
            )
        },
        "python",
        True,
    )


class TestSQLiteIndexBuilderMaxWorkers:
    """Verify max_workers is forwarded to ThreadPoolExecutor."""

    def test_max_workers_passed_to_executor(self, tmp_path, monkeypatch):
        builder, _ = _make_builder(tmp_path)
        monkeypatch.setattr(builder, "_get_supported_files", lambda: ["a.py", "b.py"])

        captured_workers = {}

        class FakeExecutor:
            def __init__(self, max_workers):
                captured_workers["value"] = max_workers

            def submit(self, fn, *args, **kwargs):
                future = MagicMock()
                future.result.return_value = None  # skip processing
                return future

            def shutdown(self, wait=True, cancel_futures=False):
                pass

        monkeypatch.setattr(
            "code_index_mcp.indexing.sqlite_index_builder.ThreadPoolExecutor",
            FakeExecutor,
        )
        monkeypatch.setattr(
            "code_index_mcp.indexing.sqlite_index_builder.as_completed",
            lambda fmap, timeout=None: iter(fmap.keys()),
        )

        builder.build_index(parallel=True, max_workers=8)
        assert captured_workers["value"] == 8

    def test_timeout_passed_to_as_completed(self, tmp_path, monkeypatch):
        builder, _ = _make_builder(tmp_path)
        monkeypatch.setattr(builder, "_get_supported_files", lambda: ["a.py", "b.py"])

        captured_timeout = {}

        class FakeExecutor:
            def __init__(self, max_workers):
                pass

            def submit(self, fn, *args, **kwargs):
                future = MagicMock()
                future.result.return_value = None  # skip processing
                return future

            def shutdown(self, wait=True, cancel_futures=False):
                pass

        def fake_as_completed(fmap, timeout=None):
            captured_timeout["value"] = timeout
            return iter(fmap.keys())

        monkeypatch.setattr(
            "code_index_mcp.indexing.sqlite_index_builder.ThreadPoolExecutor",
            FakeExecutor,
        )
        monkeypatch.setattr(
            "code_index_mcp.indexing.sqlite_index_builder.as_completed",
            fake_as_completed,
        )

        builder.build_index(parallel=True, max_workers=2, timeout=120)
        assert captured_timeout["value"] == 120.0


# ---------------------------------------------------------------------------
# SQLiteIndexManager parameter pass-through
# ---------------------------------------------------------------------------


class TestSQLiteIndexManagerPassThrough:
    """Verify max_workers/timeout flow through SQLiteIndexManager."""

    def test_build_index_passes_params_to_builder(self, tmp_path):
        mgr = SQLiteIndexManager()
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        mgr.set_project_path(str(project_dir))

        # Patch the builder's build_index
        captured = {}
        original_build = mgr.index_builder.build_index

        def spy_build(**kwargs):
            captured.update(kwargs)
            return original_build(**kwargs)

        mgr.index_builder.build_index = spy_build

        mgr.build_index(max_workers=6, timeout=99)
        assert captured["max_workers"] == 6
        assert captured["timeout"] == 99

    def test_refresh_index_passes_params_to_build(self, tmp_path):
        mgr = SQLiteIndexManager()
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        mgr.set_project_path(str(project_dir))

        captured = {}
        original_build = mgr.build_index

        def spy_build(**kwargs):
            captured.update(kwargs)
            return original_build(**kwargs)

        mgr.build_index = spy_build

        mgr.refresh_index(max_workers=3, timeout=60)
        assert captured["max_workers"] == 3
        assert captured["timeout"] == 60


# ---------------------------------------------------------------------------
# DeepIndexManager parameter pass-through
# ---------------------------------------------------------------------------


class TestDeepIndexManagerPassThrough:
    """Verify DeepIndexManager passes params to underlying SQLiteIndexManager."""

    def test_build_index_delegates_params(self):
        dm = DeepIndexManager()
        captured = {}

        def fake_build(force_rebuild=False, max_workers=None, timeout=None):
            captured["max_workers"] = max_workers
            captured["timeout"] = timeout
            return True

        dm._mgr.build_index = fake_build
        dm.build_index(max_workers=12, timeout=300)
        assert captured == {"max_workers": 12, "timeout": 300}

    def test_refresh_index_delegates_params(self):
        dm = DeepIndexManager()
        captured = {}

        def fake_refresh(max_workers=None, timeout=None):
            captured["max_workers"] = max_workers
            captured["timeout"] = timeout
            return True

        dm._mgr.refresh_index = fake_refresh
        dm.refresh_index(max_workers=4, timeout=120)
        assert captured == {"max_workers": 4, "timeout": 120}


# ---------------------------------------------------------------------------
# Concurrency safety: parallel file processing doesn't corrupt state
# ---------------------------------------------------------------------------


class TestParallelBuildConcurrencySafety:
    """Ensure parallel builds produce consistent results."""

    def test_parallel_and_sequential_produce_same_file_count(self, tmp_path):
        """Build the same project sequentially and in parallel; compare stats."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create a handful of tiny Python files
        for i in range(10):
            (project_dir / f"mod_{i}.py").write_text(
                f"def func_{i}():\n    pass\n"
            )

        # Sequential build
        store_seq = SQLiteIndexStore(str(tmp_path / "seq.db"))
        builder_seq = SQLiteIndexBuilder(str(project_dir), store_seq)
        stats_seq = builder_seq.build_index(parallel=False)

        # Parallel build
        store_par = SQLiteIndexStore(str(tmp_path / "par.db"))
        builder_par = SQLiteIndexBuilder(str(project_dir), store_par)
        stats_par = builder_par.build_index(parallel=True, max_workers=4)

        assert stats_seq["files"] == stats_par["files"]
        assert stats_seq["symbols"] == stats_par["symbols"]
        assert stats_seq["languages"] == stats_par["languages"]

    def test_parallel_build_with_many_workers(self, tmp_path):
        """Stress test: more workers than files should still work."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "one.py").write_text("x = 1\n")

        store = SQLiteIndexStore(str(tmp_path / "test.db"))
        builder = SQLiteIndexBuilder(str(project_dir), store)
        # max_workers > file count is fine; builder clamps to file count
        stats = builder.build_index(parallel=True, max_workers=16)
        assert stats["files"] == 1
