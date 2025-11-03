"""Tests covering shared search filtering behaviour."""
import os
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path as _TestPath

    

from code_index_mcp.search.basic import BasicSearchStrategy
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


@patch("code_index_mcp.search.ripgrep.subprocess.run")
def test_ripgrep_strategy_adds_exclude_globs(mock_run, tmp_path):
    mock_run.return_value = SimpleNamespace(returncode=0, stdout="", stderr="")

    strategy = RipgrepStrategy()
    strategy.configure_excludes(FileFilter())

    strategy.search("mongo", str(tmp_path))

    cmd = mock_run.call_args[0][0]
    glob_args = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == '--glob' and i + 1 < len(cmd)]

    assert any(value.startswith('!**/node_modules/') for value in glob_args)
