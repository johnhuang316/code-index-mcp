"""Tests for index exclusion patterns.

Verify that additional_excludes parameter correctly filters directories
during both shallow and deep indexing operations.
"""

from pathlib import Path

from code_index_mcp.indexing.sqlite_index_manager import SQLiteIndexManager
from code_index_mcp.indexing.shallow_index_manager import ShallowIndexManager


def test_sqlite_index_manager_respects_exclude_patterns(tmp_path):
    """Verify additional_excludes filters directories during deep indexing."""
    # Create test structure using directory names NOT in default exclusions
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def foo(): pass")
    (tmp_path / "custom_libs").mkdir()
    (tmp_path / "custom_libs" / "lib.py").write_text("def bar(): pass")

    # Without exclusions - both files indexed
    manager1 = SQLiteIndexManager()
    assert manager1.set_project_path(str(tmp_path))
    assert manager1.build_index()
    stats1 = manager1.get_index_stats()
    assert stats1["indexed_files"] == 2

    # With exclusions - custom_libs directory excluded
    manager2 = SQLiteIndexManager()
    assert manager2.set_project_path(str(tmp_path), additional_excludes=["custom_libs"])
    assert manager2.build_index()
    stats2 = manager2.get_index_stats()
    assert stats2["indexed_files"] == 1


def test_shallow_index_manager_respects_exclude_patterns(tmp_path):
    """Verify additional_excludes filters directories during shallow indexing."""
    # Create test structure
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("def foo(): pass")
    (tmp_path / "excluded_dir").mkdir()
    (tmp_path / "excluded_dir" / "other.py").write_text("def bar(): pass")

    # Without exclusions
    manager1 = ShallowIndexManager()
    assert manager1.set_project_path(str(tmp_path))
    assert manager1.build_index()
    files1 = manager1.get_file_list()
    assert len(files1) == 2

    # With exclusions
    manager2 = ShallowIndexManager()
    assert manager2.set_project_path(
        str(tmp_path), additional_excludes=["excluded_dir"]
    )
    assert manager2.build_index()
    files2 = manager2.get_file_list()
    assert len(files2) == 1
    # Verify the correct file is kept (normalize path separators)
    assert any("src" in f and "main.py" in f for f in files2)


def test_multiple_exclude_patterns(tmp_path):
    """Verify multiple exclusion patterns work together."""
    # Create test structure with multiple directories to exclude
    # Use names NOT in default exclusions to test additional_excludes specifically
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def app(): pass")
    (tmp_path / "custom_modules").mkdir()
    (tmp_path / "custom_modules" / "pkg.py").write_text("def pkg(): pass")
    (tmp_path / "third_party").mkdir()
    (tmp_path / "third_party" / "lib.py").write_text("def lib(): pass")
    (tmp_path / "generated").mkdir()
    (tmp_path / "generated" / "auto.py").write_text("def auto(): pass")

    # Exclude multiple directories via additional_excludes
    manager = ShallowIndexManager()
    assert manager.set_project_path(
        str(tmp_path),
        additional_excludes=["custom_modules", "third_party", "generated"],
    )
    assert manager.build_index()
    files = manager.get_file_list()

    # Only src/app.py should be indexed
    assert len(files) == 1
    assert any("app.py" in f for f in files)


def test_exclude_patterns_with_nested_directories(tmp_path):
    """Verify exclusions work with nested directory structures."""
    # Create nested structure using names NOT in default exclusions
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "core").mkdir()
    (tmp_path / "src" / "core" / "main.py").write_text("def main(): pass")
    (tmp_path / "src" / "external_deps").mkdir()
    (tmp_path / "src" / "external_deps" / "helper.py").write_text("def ext(): pass")

    # Exclude external_deps at any level
    manager = ShallowIndexManager()
    assert manager.set_project_path(
        str(tmp_path), additional_excludes=["external_deps"]
    )
    assert manager.build_index()
    files = manager.get_file_list()

    # Only src/core/main.py should be indexed
    assert len(files) == 1
    assert any("main.py" in f for f in files)
