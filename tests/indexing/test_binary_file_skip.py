"""Tests for skipping binary files during deep indexing."""

from code_index_mcp.indexing.sqlite_index_manager import SQLiteIndexManager


def test_sqlite_index_manager_skips_files_containing_nul_bytes(tmp_path):
    (tmp_path / "main.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
    (tmp_path / "binary.index").write_bytes(b"\x00binary-content")

    manager = SQLiteIndexManager()
    assert manager.set_project_path(str(tmp_path))
    assert manager.build_index()

    stats = manager.get_index_stats()
    assert stats["indexed_files"] == 1
