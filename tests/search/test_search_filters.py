"""Tests covering shared search filtering behaviour."""
import os
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path as _TestPath
import sys

import pytest

ROOT = _TestPath(__file__).resolve().parents[2]
SRC_PATH = ROOT / 'src'
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from code_index_mcp.search.basic import BasicSearchStrategy
from code_index_mcp.search.grep import GrepStrategy
from code_index_mcp.search.ripgrep import RipgrepStrategy
from code_index_mcp.utils.file_filter import FileFilter


def test_basic_strategy_skips_excluded_directories(tmp_path):
    base = tmp_path
    src_dir = base / "src"
    src_dir.mkdir()
    (src_dir / 'app.js').write_text("const db = 'mongo';\n")

    node_modules_dir = base / "node_modules" / "pkg"
    node_modules_dir.mkdir(parents=True)
    (node_modules_dir / 'index.js').write_text("// mongo dependency\n")

    strategy = BasicSearchStrategy()
    strategy.configure_excludes(FileFilter())

    results = strategy.search("mongo", str(base), case_sensitive=False)

    included_path = os.path.join("src", "app.js")
    excluded_path = os.path.join("node_modules", "pkg", "index.js")

    assert included_path in results
    assert excluded_path not in results


def test_basic_strategy_rejects_regex_mode_without_external_tool(tmp_path):
    test_file = tmp_path / "app.py"
    test_file.write_text("hello world\n")

    strategy = BasicSearchStrategy()

    with pytest.raises(ValueError, match="external search tool"):
        strategy.search("hello.*world", str(tmp_path), regex=True)


@patch("code_index_mcp.search.ripgrep.subprocess.run")
def test_ripgrep_strategy_adds_exclude_globs(mock_run, tmp_path):
    mock_run.return_value = SimpleNamespace(returncode=0, stdout="", stderr="")

    strategy = RipgrepStrategy()
    strategy.configure_excludes(FileFilter())

    strategy.search("mongo", str(tmp_path))

    cmd = mock_run.call_args[0][0]
    glob_args = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == '--glob' and i + 1 < len(cmd)]

    assert any(value.startswith('!**/node_modules/') for value in glob_args)


@patch("code_index_mcp.search.grep.subprocess.run")
def test_grep_strategy_treats_regex_chars_as_literal_without_regex_mode(mock_run, tmp_path):
    mock_run.return_value = SimpleNamespace(returncode=0, stdout="", stderr="")

    strategy = GrepStrategy()
    strategy.search("hello.*world", str(tmp_path), regex=False)

    cmd = mock_run.call_args[0][0]

    assert '-F' in cmd
    assert '-E' not in cmd
