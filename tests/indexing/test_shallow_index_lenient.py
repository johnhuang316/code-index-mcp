from pathlib import Path

import pytest

from code_index_mcp.indexing.shallow_index_manager import ShallowIndexManager


@pytest.fixture()
def temp_manager(tmp_path):
    project = Path("test/sample-projects/python/user_management").resolve()
    m = ShallowIndexManager()
    assert m.set_project_path(str(project))
    assert m.build_index()
    assert m.load_index()
    yield m
    m.cleanup()


def test_simple_filename_triggers_recursive(temp_manager):
    res = temp_manager.find_files("user.py")
    assert "models/user.py" in res


def test_case_insensitive(temp_manager):
    res = temp_manager.find_files("USER.PY")
    assert "models/user.py" in [p.lower() for p in res]


def test_pattern_with_slash_not_lenient(temp_manager):
    res = temp_manager.find_files("models/user.py")
    assert res == ["models/user.py"]


def test_wildcard_all_unchanged(temp_manager):
    res = temp_manager.find_files("*")
    # sample project has 12 files
    assert len(res) == 12


def test_non_string_returns_empty(temp_manager):
    assert temp_manager.find_files(None) == []  # type: ignore[arg-type]
