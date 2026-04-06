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
        assert stats_seq["timed_out"] is False
        assert stats_par["timed_out"] is False
        assert stats_seq["total_files"] == stats_seq["files"]
        assert stats_par["total_files"] == stats_par["files"]

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
        assert stats["timed_out"] is False
        assert stats["total_files"] == 1


# ---------------------------------------------------------------------------
# Parameter validation
# ---------------------------------------------------------------------------


class TestParameterValidation:
    """Verify max_workers and timeout reject invalid values."""

    def test_build_index_rejects_zero_max_workers(self, tmp_path):
        builder, _ = _make_builder(tmp_path)
        with pytest.raises(ValueError, match="max_workers must be >= 1"):
            builder.build_index(parallel=True, max_workers=0)

    def test_build_index_rejects_negative_max_workers(self, tmp_path):
        builder, _ = _make_builder(tmp_path)
        with pytest.raises(ValueError, match="max_workers must be >= 1"):
            builder.build_index(parallel=True, max_workers=-1)

    def test_build_index_rejects_negative_timeout(self, tmp_path):
        builder, _ = _make_builder(tmp_path)
        with pytest.raises(ValueError, match="timeout must be >= 1"):
            builder.build_index(parallel=True, timeout=-5)

    def test_build_index_rejects_zero_timeout(self, tmp_path):
        """timeout=0 causes as_completed to return nothing; reject it."""
        builder, _ = _make_builder(tmp_path)
        with pytest.raises(ValueError, match="timeout must be >= 1"):
            builder.build_index(parallel=True, timeout=0)


# ---------------------------------------------------------------------------
# Settings-merge override logic
# ---------------------------------------------------------------------------


class TestSettingsMergeOverride:
    """Verify explicit params override settings values in _execute_rebuild_workflow."""

    def test_explicit_params_override_settings(self, tmp_path):
        from code_index_mcp.services.index_management_service import IndexManagementService

        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        (project_dir / "a.py").write_text("x = 1\n")

        service = IndexManagementService.__new__(IndexManagementService)

        # Mock the helper that provides base_path and settings
        mock_helper = MagicMock()
        mock_helper.base_path = str(project_dir)
        mock_helper.settings.get_indexing_config.return_value = {
            "max_workers": 2,
            "timeout_seconds": 60,
        }
        mock_helper.settings.get_file_watcher_config.return_value = {}
        service.helper = mock_helper

        # Mock the index manager to capture passed params
        captured = {}
        mock_mgr = MagicMock()
        mock_mgr.set_project_path.return_value = True
        mock_mgr.get_index_stats.return_value = {
            "files": 1, "symbols": 0, "languages": 0,
        }

        def fake_refresh(max_workers=None, timeout=None):
            captured["max_workers"] = max_workers
            captured["timeout"] = timeout
            return True

        mock_mgr.refresh_index.side_effect = fake_refresh
        service._index_manager = mock_mgr

        # Shallow manager stub
        service._shallow_manager = MagicMock()

        # Call with explicit override
        service._execute_rebuild_workflow(max_workers=8)

        # Explicit max_workers=8 should override settings' 2
        assert captured["max_workers"] == 8
        # timeout was not passed explicitly, so settings' 60 should be used
        assert captured["timeout"] == 60


# ---------------------------------------------------------------------------
# Indexing config round-trip
# ---------------------------------------------------------------------------


class TestIndexingConfigRoundTrip:
    """Verify indexing config persists and loads correctly."""

    def test_update_and_get_indexing_config(self, tmp_path):
        from code_index_mcp.project_settings import ProjectSettings

        settings = ProjectSettings(str(tmp_path))
        settings.update_indexing_config({"max_workers": 8})
        config = settings.get_indexing_config()
        assert config["max_workers"] == 8

    def test_indexing_config_has_no_parallel_field(self, tmp_path):
        from code_index_mcp.project_settings import ProjectSettings

        settings = ProjectSettings(str(tmp_path))
        config = settings.get_indexing_config()
        assert "parallel" not in config


# ---------------------------------------------------------------------------
# Partial build message propagation
# ---------------------------------------------------------------------------


class TestPartialBuildMessage:
    """Verify _execute_rebuild_workflow surfaces timeout info."""

    def test_partial_build_produces_partial_status(self, tmp_path):
        from code_index_mcp.services.index_management_service import IndexManagementService

        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        (project_dir / "a.py").write_text("x = 1\n")

        service = IndexManagementService.__new__(IndexManagementService)

        mock_helper = MagicMock()
        mock_helper.base_path = str(project_dir)
        mock_helper.settings.get_indexing_config.return_value = {
            "max_workers": None,
            "timeout_seconds": None,
        }
        mock_helper.settings.get_file_watcher_config.return_value = {}
        service.helper = mock_helper

        mock_mgr = MagicMock()
        mock_mgr.set_project_path.return_value = True
        # refresh_index returns False when timed out
        mock_mgr.refresh_index.return_value = False
        mock_mgr.get_index_stats.return_value = {
            "indexed_files": 3,
            "total_symbols": 10,
        }
        service._index_manager = mock_mgr
        service._shallow_manager = MagicMock()

        result = service._execute_rebuild_workflow()
        assert result.status == "partial"
        assert "partial" in result.message.lower()
        assert "3" in result.message
