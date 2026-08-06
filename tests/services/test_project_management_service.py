from unittest.mock import MagicMock

from code_index_mcp.indexing.sqlite_index_manager import SQLiteIndexManager
from code_index_mcp.services.project_management_service import ProjectManagementService


def test_project_initialization_loads_persisted_deep_index(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "code_index_mcp.indexing.sqlite_index_manager.tempfile.gettempdir",
        lambda: str(tmp_path),
    )
    project_path = tmp_path / "project"
    project_path.mkdir()
    (project_path / "example.py").write_text("def example():\n    return True\n")

    persisted_manager = SQLiteIndexManager()
    assert persisted_manager.set_project_path(str(project_path))
    assert persisted_manager.build_index(max_workers=1)

    restarted_manager = SQLiteIndexManager()
    shallow_manager = MagicMock()
    shallow_manager.set_project_path.return_value = True
    shallow_manager.load_index.return_value = True
    shallow_manager.get_file_list.return_value = ["example.py"]

    service = ProjectManagementService.__new__(ProjectManagementService)
    service._index_manager = restarted_manager
    service._shallow_manager = shallow_manager
    service._get_exclude_patterns = lambda: []
    service.helper = MagicMock()

    service._initialize_shallow_index_manager(str(project_path))

    summary = restarted_manager.get_file_summary("example.py")
    assert summary is not None
    assert summary["file_path"] == "example.py"
