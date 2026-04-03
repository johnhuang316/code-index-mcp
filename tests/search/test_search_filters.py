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
def test_ripgrep_uses_native_gitignore(mock_run, tmp_path):
    """ripgrep should NOT have --no-ignore flag (uses native .gitignore)."""
    mock_run.return_value = SimpleNamespace(returncode=0, stdout="", stderr="")
    strategy = RipgrepStrategy()
    strategy.search("mongo", str(tmp_path))
    cmd = mock_run.call_args[0][0]
    assert '--no-ignore' not in cmd


@patch("code_index_mcp.search.ripgrep.subprocess.run")
def test_ripgrep_build_exclude_args(mock_run, tmp_path):
    """ripgrep should translate exclude patterns to --glob '!pattern' args."""
    strategy = RipgrepStrategy()
    args = strategy.build_exclude_args(["logs/", "*.generated.ts"])
    assert args == ['--glob', '!logs/', '--glob', '!*.generated.ts']


@patch("code_index_mcp.search.grep.subprocess.run")
def test_grep_strategy_treats_regex_chars_as_literal_without_regex_mode(mock_run, tmp_path):
    mock_run.return_value = SimpleNamespace(returncode=0, stdout="", stderr="")

    strategy = GrepStrategy()
    strategy.search("hello.*world", str(tmp_path), regex=False)

    cmd = mock_run.call_args[0][0]

    assert '-F' in cmd
    assert '-E' not in cmd


def test_strategy_build_exclude_args_returns_list():
    """Each strategy must implement build_exclude_args returning a list of CLI args."""
    from code_index_mcp.search.ripgrep import RipgrepStrategy
    strategy = RipgrepStrategy()
    args = strategy.build_exclude_args(["logs/", "*.generated.ts"])
    assert isinstance(args, list)
    # Base class returns empty list, subclasses will override


@patch("code_index_mcp.search.ugrep.shutil.which", return_value="/usr/bin/ug")
@patch("code_index_mcp.search.ugrep.subprocess.run")
def test_ugrep_uses_ignore_files_flag(mock_run, mock_which, tmp_path):
    """ugrep should use --ignore-files for .gitignore support."""
    mock_run.return_value = SimpleNamespace(returncode=0, stdout="", stderr="")
    from code_index_mcp.search.ugrep import UgrepStrategy
    strategy = UgrepStrategy()
    strategy.search("mongo", str(tmp_path))
    cmd = mock_run.call_args[0][0]
    assert '--ignore-files' in cmd
    assert '--ignore' not in cmd


@patch("code_index_mcp.search.ugrep.shutil.which", return_value="/usr/bin/ug")
@patch("code_index_mcp.search.ugrep.subprocess.run")
def test_ugrep_search_pattern_not_shadowed(mock_run, mock_which, tmp_path):
    """ugrep must use the actual search pattern, not an exclude pattern."""
    mock_run.return_value = SimpleNamespace(returncode=0, stdout="", stderr="")
    from code_index_mcp.search.ugrep import UgrepStrategy
    strategy = UgrepStrategy()
    strategy.search("myFunction", str(tmp_path))
    cmd = mock_run.call_args[0][0]
    assert cmd[-2] == "myFunction"


@patch("code_index_mcp.search.ugrep.subprocess.run")
def test_ugrep_build_exclude_args(mock_run, tmp_path):
    """ugrep should translate exclude patterns to --exclude-dir and --exclude."""
    from code_index_mcp.search.ugrep import UgrepStrategy
    strategy = UgrepStrategy()
    args = strategy.build_exclude_args(["logs/", "*.tmp"])
    assert '--exclude-dir=logs' in args
    assert '--exclude=*.tmp' in args
