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
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure src is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from code_index_mcp.project_settings import ProjectSettings
from code_index_mcp.utils.file_filter import FileFilter
from code_index_mcp.indexing.shallow_index_manager import ShallowIndexManager
from code_index_mcp.indexing.sqlite_index_manager import SQLiteIndexManager


# --- ProjectSettings ---


class TestProjectSettingsExtraExtensions(unittest.TestCase):
    """Test extra_extensions persistence in ProjectSettings."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_update_and_get_extra_extensions(self):
        settings = ProjectSettings(self.tmp_dir)
        settings.update_extra_extensions([".rsc", ".conf", "rules"])
        result = settings.get_extra_extensions()
        self.assertIn(".rsc", result)
        self.assertIn(".conf", result)
        self.assertIn(".rules", result)  # auto-prefixed with dot

    def test_get_extra_extensions_empty_by_default(self):
        settings = ProjectSettings(self.tmp_dir)
        self.assertEqual(settings.get_extra_extensions(), [])

    def test_extra_extensions_normalized_lowercase(self):
        settings = ProjectSettings(self.tmp_dir)
        settings.update_extra_extensions([".RSC", ".Conf"])
        result = settings.get_extra_extensions()
        self.assertIn(".rsc", result)
        self.assertIn(".conf", result)

    def test_extra_extensions_deduplication(self):
        settings = ProjectSettings(self.tmp_dir)
        settings.update_extra_extensions([".rsc", ".rsc", ".conf"])
        result = settings.get_extra_extensions()
        self.assertEqual(result.count(".rsc"), 1)

    @patch.dict(os.environ, {"EXTRA_EXTENSIONS": ".rsc,.conf,.rules"})
    def test_extra_extensions_from_env_variable(self):
        settings = ProjectSettings(self.tmp_dir)
        result = settings.get_extra_extensions()
        self.assertIn(".rsc", result)
        self.assertIn(".conf", result)
        self.assertIn(".rules", result)

    @patch.dict(os.environ, {"EXTRA_EXTENSIONS": ".env_ext"})
    def test_extra_extensions_merged_config_and_env(self):
        settings = ProjectSettings(self.tmp_dir)
        settings.update_extra_extensions([".config_ext"])
        result = settings.get_extra_extensions()
        self.assertIn(".config_ext", result)
        self.assertIn(".env_ext", result)

    @patch.dict(os.environ, {"EXTRA_EXTENSIONS": "rsc,conf"})
    def test_extra_extensions_env_without_dots(self):
        settings = ProjectSettings(self.tmp_dir)
        result = settings.get_extra_extensions()
        self.assertIn(".rsc", result)
        self.assertIn(".conf", result)


# --- FileFilter ---


class TestFileFilterExtraExtensions(unittest.TestCase):
    """Test FileFilter includes extra extensions."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_extra_extension_accepted(self):
        ff = FileFilter(extra_extensions=[".rsc"])
        self.assertIn(".rsc", ff.supported_extensions)

    def test_extra_extension_file_not_excluded(self):
        ff = FileFilter(extra_extensions=[".rsc"])
        test_file = Path(self.tmp_dir) / "script.rsc"
        test_file.write_text("# router script")
        self.assertFalse(ff.should_exclude_file(test_file))

    def test_without_extra_extension_file_excluded(self):
        ff = FileFilter()
        test_file = Path(self.tmp_dir) / "script.rsc"
        test_file.write_text("# router script")
        self.assertTrue(ff.should_exclude_file(test_file))

    def test_extra_extension_normalizes_case(self):
        ff = FileFilter(extra_extensions=[".RSC"])
        self.assertIn(".rsc", ff.supported_extensions)

    def test_extra_extension_adds_dot_prefix(self):
        ff = FileFilter(extra_extensions=["rsc"])
        self.assertIn(".rsc", ff.supported_extensions)

    def test_should_process_path_with_extra_extension(self):
        ff = FileFilter(extra_extensions=[".rsc"])
        tmp_path = Path(self.tmp_dir)
        test_file = tmp_path / "script.rsc"
        test_file.write_text("# content")
        self.assertTrue(ff.should_process_path(test_file, tmp_path))


# --- ShallowIndexManager ---


class TestShallowIndexExtraExtensions(unittest.TestCase):
    """Test that shallow indexing picks up files with custom extensions."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_shallow_index_includes_extra_extension_files(self):
        # Create files: one standard, one custom extension
        with open(os.path.join(self.tmp_dir, "main.py"), "w") as f:
            f.write("print('hello')")
        with open(os.path.join(self.tmp_dir, "router.rsc"), "w") as f:
            f.write("/ip address add")

        # Without extra_extensions: only .py is indexed
        mgr1 = ShallowIndexManager()
        self.assertTrue(mgr1.set_project_path(self.tmp_dir))
        self.assertTrue(mgr1.build_index())
        files1 = mgr1.get_file_list()
        self.assertTrue(any(f.endswith(".py") for f in files1))
        self.assertFalse(any(f.endswith(".rsc") for f in files1))

        # With extra_extensions: .rsc is also indexed
        mgr2 = ShallowIndexManager()
        self.assertTrue(mgr2.set_project_path(self.tmp_dir, extra_extensions=[".rsc"]))
        self.assertTrue(mgr2.build_index())
        files2 = mgr2.get_file_list()
        self.assertTrue(any(f.endswith(".py") for f in files2))
        self.assertTrue(any(f.endswith(".rsc") for f in files2))

    def test_shallow_find_files_with_custom_extension(self):
        with open(os.path.join(self.tmp_dir, "config.myext"), "w") as f:
            f.write("key=value")
        mgr = ShallowIndexManager()
        self.assertTrue(mgr.set_project_path(self.tmp_dir, extra_extensions=[".myext"]))
        self.assertTrue(mgr.build_index())
        found = mgr.find_files("*.myext")
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0].endswith("config.myext"))


# --- SQLiteIndexManager ---


class TestSQLiteIndexExtraExtensions(unittest.TestCase):
    """Test that deep indexing picks up files with custom extensions."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_deep_index_includes_extra_extension_files(self):
        with open(os.path.join(self.tmp_dir, "main.py"), "w") as f:
            f.write("def foo(): pass")
        with open(os.path.join(self.tmp_dir, "router.rsc"), "w") as f:
            f.write("/ip address add address=10.0.0.1")

        # Without extra_extensions
        mgr1 = SQLiteIndexManager()
        self.assertTrue(mgr1.set_project_path(self.tmp_dir))
        self.assertTrue(mgr1.build_index())
        stats1 = mgr1.get_index_stats()
        self.assertEqual(stats1["indexed_files"], 1)

        # With extra_extensions
        mgr2 = SQLiteIndexManager()
        self.assertTrue(mgr2.set_project_path(self.tmp_dir, extra_extensions=[".rsc"]))
        self.assertTrue(mgr2.build_index())
        stats2 = mgr2.get_index_stats()
        self.assertEqual(stats2["indexed_files"], 2)


# --- CLI argument parsing ---


class TestCLIExtraExtensions(unittest.TestCase):
    """Test --extra-extensions CLI flag parsing."""

    def test_parse_extra_extensions_flag(self):
        from code_index_mcp.server import _parse_args
        args = _parse_args(["--extra-extensions", ".rsc,.conf,.rules"])
        self.assertEqual(args.extra_extensions, ".rsc,.conf,.rules")

    def test_parse_extra_extensions_default_none(self):
        from code_index_mcp.server import _parse_args
        args = _parse_args([])
        self.assertIsNone(args.extra_extensions)


# --- Clearing stored extensions ---


class TestClearingStoredExtensions(unittest.TestCase):
    """Test that extra_extensions=[] clears previously persisted extensions."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_empty_list_clears_stored_extensions(self):
        """Passing extra_extensions=[] should clear previously stored extensions."""
        settings = ProjectSettings(self.tmp_dir)
        settings.update_extra_extensions([".rsc", ".conf"])
        self.assertEqual(len(settings.get_extra_extensions()), 2)

        settings.update_extra_extensions([])
        self.assertEqual(settings.get_extra_extensions(), [])

    def test_none_does_not_touch_stored_extensions(self):
        """extra_extensions=None (not provided) should leave stored config intact."""
        settings = ProjectSettings(self.tmp_dir)
        settings.update_extra_extensions([".rsc"])
        self.assertEqual(len(settings.get_extra_extensions()), 1)

        # Simulate service-layer condition: None means "not provided"
        extra_extensions = None
        if extra_extensions is not None:
            settings.update_extra_extensions(extra_extensions)

        # Extensions should still be there
        self.assertEqual(settings.get_extra_extensions(), [".rsc"])


# --- Watcher rebuild preserves extensions ---


class TestWatcherRebuildPreservesExtensions(unittest.TestCase):
    """Test that watcher-triggered rebuilds preserve custom extension files."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_rebuild_preserves_custom_extension_files(self):
        """After a simulated watcher rebuild, custom-extension files must still be indexed."""
        with open(os.path.join(self.tmp_dir, "main.py"), "w") as f:
            f.write("print('hello')")
        with open(os.path.join(self.tmp_dir, "router.rsc"), "w") as f:
            f.write("/ip address add")

        extra_exts = [".rsc"]

        # Initial build with custom extensions
        mgr = ShallowIndexManager()
        self.assertTrue(mgr.set_project_path(self.tmp_dir, extra_extensions=extra_exts))
        self.assertTrue(mgr.build_index())
        files = mgr.get_file_list()
        self.assertTrue(any(f.endswith(".rsc") for f in files))

        # Simulate buggy rebuild WITHOUT extra_extensions (demonstrates the bug)
        self.assertTrue(mgr.set_project_path(self.tmp_dir))
        self.assertTrue(mgr.build_index())
        files_after_bad_rebuild = mgr.get_file_list()
        self.assertFalse(any(f.endswith(".rsc") for f in files_after_bad_rebuild))

        # Simulate correct rebuild WITH extra_extensions (the fix)
        self.assertTrue(mgr.set_project_path(self.tmp_dir, extra_extensions=extra_exts))
        self.assertTrue(mgr.build_index())
        files_after_good_rebuild = mgr.get_file_list()
        self.assertTrue(any(f.endswith(".rsc") for f in files_after_good_rebuild))


# --- CLI bootstrap _CLI_CONFIG behavior ---


class TestCLIBootstrapExtraExtensions(unittest.TestCase):
    """Test that main() correctly updates _CLI_CONFIG for extra_extensions."""

    def test_empty_string_flag_sets_empty_list(self):
        """--extra-extensions '' should set _CLI_CONFIG.extra_extensions to [] (explicit clear)."""
        from code_index_mcp.server import _CLI_CONFIG, main

        with patch("code_index_mcp.server.mcp.run"):
            main(["--extra-extensions", ""])

        self.assertEqual(_CLI_CONFIG.extra_extensions, [])

    def test_omitted_flag_sets_none(self):
        """Omitting --extra-extensions should set _CLI_CONFIG.extra_extensions to None."""
        from code_index_mcp.server import _CLI_CONFIG, main

        with patch("code_index_mcp.server.mcp.run"):
            main([])

        self.assertIsNone(_CLI_CONFIG.extra_extensions)

    def test_no_stale_leak_between_calls(self):
        """Calling main() without the flag after a call with it must not leak stale values."""
        from code_index_mcp.server import _CLI_CONFIG, main

        with patch("code_index_mcp.server.mcp.run"):
            main(["--extra-extensions", ".rsc,.conf"])

        self.assertEqual(_CLI_CONFIG.extra_extensions, [".rsc", ".conf"])

        with patch("code_index_mcp.server.mcp.run"):
            main([])

        self.assertIsNone(_CLI_CONFIG.extra_extensions)

    def test_explicit_clear_after_set(self):
        """main(['--extra-extensions', '']) after main(['--extra-extensions', '.rsc']) should clear."""
        from code_index_mcp.server import _CLI_CONFIG, main

        with patch("code_index_mcp.server.mcp.run"):
            main(["--extra-extensions", ".rsc"])

        self.assertEqual(_CLI_CONFIG.extra_extensions, [".rsc"])

        with patch("code_index_mcp.server.mcp.run"):
            main(["--extra-extensions", ""])

        self.assertEqual(_CLI_CONFIG.extra_extensions, [])


if __name__ == "__main__":
    unittest.main()
