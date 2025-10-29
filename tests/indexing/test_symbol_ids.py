"""Tests for symbol identifier generation."""

from code_index_mcp.indexing.json_index_builder import JSONIndexBuilder


def test_symbol_ids_use_relative_paths(tmp_path):
    project_dir = tmp_path / "project"
    scripts_dir = project_dir / "scripts"
    examples_dir = project_dir / "examples"
    scripts_dir.mkdir(parents=True)
    examples_dir.mkdir(parents=True)

    (scripts_dir / "foo.py").write_text(
        "def foo():\n"
        "    return 1\n",
        encoding="utf-8",
    )
    (examples_dir / "foo.py").write_text(
        "def foo():\n"
        "    return 2\n",
        encoding="utf-8",
    )

    builder = JSONIndexBuilder(str(project_dir))
    index = builder.build_index(parallel=False)
    symbols = index["symbols"]

    assert "scripts/foo.py::foo" in symbols
    assert "examples/foo.py::foo" in symbols
    assert len({sid for sid in symbols if sid.endswith("::foo")}) == 2
