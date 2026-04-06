"""Tests for custom file extensions configuration (Issue #81).

Verify that extra_extensions flows correctly through:
- ProjectSettings persistence and retrieval
- FileFilter extension matching
- ShallowIndexManager file discovery
- SQLiteIndexManager deep indexing
- CLI argument parsing
- Environment variable support
"""

import os
from pathlib import Path

import pytest

from code_index_mcp.project_settings import ProjectSettings
from code_index_mcp.utils.file_filter import FileFilter
from code_index_mcp.indexing.shallow_index_manager import ShallowIndexManager
from code_index_mcp.indexing.sqlite_index_manager import SQLiteIndexManager


# --- ProjectSettings ---


class TestProjectSettingsExtraExtensions:
    """Test extra_extensions persistence in ProjectSettings."""

    def test_update_and_get_extra_extensions(self, tmp_path):
        settings = ProjectSettings(str(tmp_path))
        settings.update_extra_extensions([".rsc", ".conf", "rules"])
        result = settings.get_extra_extensions()
        assert ".rsc" in result
        assert ".conf" in result
        assert ".rules" in result  # auto-prefixed with dot

    def test_get_extra_extensions_empty_by_default(self, tmp_path):
        settings = ProjectSettings(str(tmp_path))
        assert settings.get_extra_extensions() == []

    def test_extra_extensions_normalized_lowercase(self, tmp_path):
        settings = ProjectSettings(str(tmp_path))
        settings.update_extra_extensions([".RSC", ".Conf"])
        result = settings.get_extra_extensions()
        assert ".rsc" in result
        assert ".conf" in result

    def test_extra_extensions_deduplication(self, tmp_path):
        settings = ProjectSettings(str(tmp_path))
        settings.update_extra_extensions([".rsc", ".rsc", ".conf"])
        result = settings.get_extra_extensions()
        assert result.count(".rsc") == 1

    def test_extra_extensions_from_env_variable(self, tmp_path, monkeypatch):
        monkeypatch.setenv("EXTRA_EXTENSIONS", ".rsc,.conf,.rules")
        settings = ProjectSettings(str(tmp_path))
        result = settings.get_extra_extensions()
        assert ".rsc" in result
        assert ".conf" in result
        assert ".rules" in result

    def test_extra_extensions_merged_config_and_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("EXTRA_EXTENSIONS", ".env_ext")
        settings = ProjectSettings(str(tmp_path))
        settings.update_extra_extensions([".config_ext"])
        result = settings.get_extra_extensions()
        assert ".config_ext" in result
        assert ".env_ext" in result

    def test_extra_extensions_env_without_dots(self, tmp_path, monkeypatch):
        monkeypatch.setenv("EXTRA_EXTENSIONS", "rsc,conf")
        settings = ProjectSettings(str(tmp_path))
        result = settings.get_extra_extensions()
        assert ".rsc" in result
        assert ".conf" in result


# --- FileFilter ---


class TestFileFilterExtraExtensions:
    """Test FileFilter includes extra extensions."""

    def test_extra_extension_accepted(self):
        ff = FileFilter(extra_extensions=[".rsc"])
        assert ".rsc" in ff.supported_extensions

    def test_extra_extension_file_not_excluded(self, tmp_path):
        ff = FileFilter(extra_extensions=[".rsc"])
        test_file = tmp_path / "script.rsc"
        test_file.write_text("# router script")
        assert not ff.should_exclude_file(test_file)

    def test_without_extra_extension_file_excluded(self, tmp_path):
        ff = FileFilter()
        test_file = tmp_path / "script.rsc"
        test_file.write_text("# router script")
        assert ff.should_exclude_file(test_file)

    def test_extra_extension_normalizes_case(self):
        ff = FileFilter(extra_extensions=[".RSC"])
        assert ".rsc" in ff.supported_extensions

    def test_extra_extension_adds_dot_prefix(self):
        ff = FileFilter(extra_extensions=["rsc"])
        assert ".rsc" in ff.supported_extensions

    def test_should_process_path_with_extra_extension(self, tmp_path):
        ff = FileFilter(extra_extensions=[".rsc"])
        test_file = tmp_path / "script.rsc"
        test_file.write_text("# content")
        assert ff.should_process_path(test_file, tmp_path)


# --- ShallowIndexManager ---


class TestShallowIndexExtraExtensions:
    """Test that shallow indexing picks up files with custom extensions."""

    def test_shallow_index_includes_extra_extension_files(self, tmp_path):
        # Create files: one standard, one custom extension
        (tmp_path / "main.py").write_text("print('hello')")
        (tmp_path / "router.rsc").write_text("/ip address add")

        # Without extra_extensions: only .py is indexed
        mgr1 = ShallowIndexManager()
        assert mgr1.set_project_path(str(tmp_path))
        assert mgr1.build_index()
        files1 = mgr1.get_file_list()
        assert any(f.endswith(".py") for f in files1)
        assert not any(f.endswith(".rsc") for f in files1)

        # With extra_extensions: .rsc is also indexed
        mgr2 = ShallowIndexManager()
        assert mgr2.set_project_path(str(tmp_path), extra_extensions=[".rsc"])
        assert mgr2.build_index()
        files2 = mgr2.get_file_list()
        assert any(f.endswith(".py") for f in files2)
        assert any(f.endswith(".rsc") for f in files2)

    def test_shallow_find_files_with_custom_extension(self, tmp_path):
        (tmp_path / "config.myext").write_text("key=value")
        mgr = ShallowIndexManager()
        assert mgr.set_project_path(str(tmp_path), extra_extensions=[".myext"])
        assert mgr.build_index()
        found = mgr.find_files("*.myext")
        assert len(found) == 1
        assert found[0].endswith("config.myext")


# --- SQLiteIndexManager ---


class TestSQLiteIndexExtraExtensions:
    """Test that deep indexing picks up files with custom extensions."""

    def test_deep_index_includes_extra_extension_files(self, tmp_path):
        (tmp_path / "main.py").write_text("def foo(): pass")
        (tmp_path / "router.rsc").write_text("/ip address add address=10.0.0.1")

        # Without extra_extensions
        mgr1 = SQLiteIndexManager()
        assert mgr1.set_project_path(str(tmp_path))
        assert mgr1.build_index()
        stats1 = mgr1.get_index_stats()
        assert stats1["indexed_files"] == 1

        # With extra_extensions
        mgr2 = SQLiteIndexManager()
        assert mgr2.set_project_path(str(tmp_path), extra_extensions=[".rsc"])
        assert mgr2.build_index()
        stats2 = mgr2.get_index_stats()
        assert stats2["indexed_files"] == 2


# --- CLI argument parsing ---


class TestCLIExtraExtensions:
    """Test --extra-extensions CLI flag parsing."""

    def test_parse_extra_extensions_flag(self):
        from code_index_mcp.server import _parse_args
        args = _parse_args(["--extra-extensions", ".rsc,.conf,.rules"])
        assert args.extra_extensions == ".rsc,.conf,.rules"

    def test_parse_extra_extensions_default_none(self):
        from code_index_mcp.server import _parse_args
        args = _parse_args([])
        assert args.extra_extensions is None
