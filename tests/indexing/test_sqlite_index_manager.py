from pathlib import Path

from code_index_mcp.indexing.sqlite_index_manager import SQLiteIndexManager


def test_sqlite_index_manager_builds_and_queries(tmp_path):
    sample_project = (
        Path(__file__).resolve().parents[2]
        / "test"
        / "sample-projects"
        / "python"
        / "user_management"
    )
    assert sample_project.exists()

    manager = SQLiteIndexManager()
    assert manager.set_project_path(str(sample_project))

    assert manager.build_index()
    assert manager.load_index()

    summary = manager.get_file_summary("services/user_manager.py")
    assert summary is not None
    assert summary["file_path"] == "services/user_manager.py"
    assert summary["language"].lower() == "python"
    assert summary["symbol_count"] > 0

    stats = manager.get_index_stats()
    assert stats["status"] == "loaded"
    assert stats["indexed_files"] > 0
