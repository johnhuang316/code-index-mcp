from code_index_mcp.indexing.sqlite_index_manager import SQLiteIndexManager


def test_c_cross_file_called_by(tmp_path):
    project = tmp_path / "c-project"
    src = project / "src"
    src.mkdir(parents=True)

    (src / "lib.h").write_text("void helper(void);\n", encoding="utf-8")
    (src / "lib.c").write_text(
        "#include \"lib.h\"\nstruct State { int value; };\nvoid helper(void) {}\n",
        encoding="utf-8",
    )
    (src / "main.c").write_text(
        "#include \"lib.h\"\nvoid run(void) { helper(); }\n",
        encoding="utf-8",
    )

    manager = SQLiteIndexManager()
    assert manager.set_project_path(str(project))
    assert manager.build_index()
    assert manager.load_index()

    summary = manager.get_file_summary("src/lib.c")
    assert summary is not None
    assert summary["language"] == "c"

    functions = {item["name"]: item["called_by"] for item in summary["functions"]}
    assert functions["helper"] == ["src/main.c:2"]
    classes = {item["name"] for item in summary["classes"]}
    assert "State" in classes


def test_cpp_cross_file_method_called_by(tmp_path):
    project = tmp_path / "cpp-project"
    src = project / "src"
    src.mkdir(parents=True)

    (src / "greeter.hpp").write_text(
        "class Greeter { public: void greet(); };\n",
        encoding="utf-8",
    )
    (src / "greeter.cpp").write_text(
        "#include \"greeter.hpp\"\nvoid Greeter::greet() {}\n",
        encoding="utf-8",
    )
    (src / "main.cpp").write_text(
        "#include \"greeter.hpp\"\nvoid boot() { Greeter g; g.greet(); }\n",
        encoding="utf-8",
    )

    manager = SQLiteIndexManager()
    assert manager.set_project_path(str(project))
    assert manager.build_index()
    assert manager.load_index()

    summary = manager.get_file_summary("src/greeter.cpp")
    assert summary is not None
    assert summary["language"] == "cpp"

    methods = {item["name"]: item["called_by"] for item in summary["methods"]}
    assert methods["Greeter.greet"] == ["src/main.cpp:2"]
