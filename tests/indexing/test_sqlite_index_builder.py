from concurrent.futures import TimeoutError as FutureTimeoutError

import pytest

from code_index_mcp.indexing.models import FileInfo, SymbolInfo
from code_index_mcp.indexing.sqlite_index_builder import SQLiteIndexBuilder
from code_index_mcp.indexing.sqlite_store import SQLiteIndexStore


class StubFuture:
    def __init__(self, result=None, cancel_result=True):
        self._result = result
        self._cancel_result = cancel_result
        self.cancel_called = False

    def result(self, timeout=None):
        return self._result

    def cancel(self):
        self.cancel_called = True
        return self._cancel_result


class StubExecutor:
    def __init__(self, futures):
        self._futures = list(futures)
        self.shutdown_calls = []

    def submit(self, fn, *args, **kwargs):
        return self._futures.pop(0)

    def shutdown(self, wait=True, cancel_futures=False):
        self.shutdown_calls.append(
            {"wait": wait, "cancel_futures": cancel_futures}
        )
        return None


def make_builder(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    store = SQLiteIndexStore(str(tmp_path / "index.db"))
    builder = SQLiteIndexBuilder(str(project_dir), store)
    return builder, store


def make_completed_result():
    return (
        {
            "done.py::finished": SymbolInfo(
                type="function",
                file="done.py",
                line=1,
                signature="def finished():",
            )
        },
        {
            "done.py": FileInfo(
                language="python",
                line_count=1,
                symbols={"functions": ["finished"], "classes": []},
                imports=[],
            )
        },
        "python",
        True,
    )


def test_build_index_keeps_completed_results_when_parallel_timeout_hits(tmp_path, monkeypatch, caplog):
    builder, store = make_builder(tmp_path)
    completed_future = StubFuture(make_completed_result())
    unfinished_future = StubFuture()
    executor = StubExecutor([completed_future, unfinished_future])

    monkeypatch.setattr(builder, "_get_supported_files", lambda: ["done.py", "stuck.py"])
    monkeypatch.setattr(
        "code_index_mcp.indexing.sqlite_index_builder.ThreadPoolExecutor",
        lambda max_workers: executor,
    )

    def fake_as_completed(future_to_file, timeout=None):
        yield completed_future
        raise FutureTimeoutError()

    monkeypatch.setattr("code_index_mcp.indexing.sqlite_index_builder.as_completed", fake_as_completed)

    with caplog.at_level("WARNING"):
        stats = builder.build_index(parallel=True, max_workers=2)

    assert stats["files"] == 1
    assert stats["symbols"] == 1
    assert stats["languages"] == 1
    assert stats["timed_out"] is True
    assert stats["total_files"] == 2
    assert unfinished_future.cancel_called is True
    assert "Cancelled timed-out files: stuck.py" in caplog.text
    assert executor.shutdown_calls == [{"wait": False, "cancel_futures": False}]

    with store.connect() as conn:
        files = list(conn.execute("SELECT path FROM files"))
        symbols = list(conn.execute("SELECT symbol_id FROM symbols"))

    assert [row["path"] for row in files] == ["done.py"]
    assert [row["symbol_id"] for row in symbols] == ["done.py::finished"]


def test_build_index_logs_uncancellable_running_future_on_timeout(tmp_path, monkeypatch, caplog):
    builder, _ = make_builder(tmp_path)
    completed_future = StubFuture(make_completed_result())
    running_future = StubFuture(cancel_result=False)
    executor = StubExecutor([completed_future, running_future])

    monkeypatch.setattr(builder, "_get_supported_files", lambda: ["done.py", "running.py"])
    monkeypatch.setattr(
        "code_index_mcp.indexing.sqlite_index_builder.ThreadPoolExecutor",
        lambda max_workers: executor,
    )

    def fake_as_completed(future_to_file, timeout=None):
        yield completed_future
        raise FutureTimeoutError()

    monkeypatch.setattr("code_index_mcp.indexing.sqlite_index_builder.as_completed", fake_as_completed)

    with caplog.at_level("WARNING"):
        stats = builder.build_index(parallel=True, max_workers=2)

    assert stats["files"] == 1
    assert stats["symbols"] == 1
    assert stats["languages"] == 1
    assert stats["timed_out"] is True
    assert stats["total_files"] == 2
    assert running_future.cancel_called is True
    assert "Still running after timeout and could not be cancelled: running.py" in caplog.text
    assert executor.shutdown_calls == [{"wait": False, "cancel_futures": False}]


def test_build_index_always_shuts_down_executor_when_later_processing_raises(tmp_path, monkeypatch):
    builder, _ = make_builder(tmp_path)
    completed_future = StubFuture(make_completed_result())
    second_future = StubFuture(make_completed_result())
    executor = StubExecutor([completed_future, second_future])

    monkeypatch.setattr(builder, "_get_supported_files", lambda: ["done.py", "other.py"])
    monkeypatch.setattr(
        "code_index_mcp.indexing.sqlite_index_builder.ThreadPoolExecutor",
        lambda max_workers: executor,
    )
    monkeypatch.setattr(
        "code_index_mcp.indexing.sqlite_index_builder.as_completed",
        lambda future_to_file, timeout=None: iter([completed_future]),
    )
    monkeypatch.setattr(builder, "_insert_file", lambda conn, path, file_info: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(RuntimeError, match="boom"):
        builder.build_index(parallel=True, max_workers=1)

    assert executor.shutdown_calls == [{"wait": True, "cancel_futures": False}]
