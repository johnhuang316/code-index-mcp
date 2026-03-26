from pathlib import Path

from code_index_mcp.indexing.sqlite_index_manager import SQLiteIndexManager
from code_index_mcp.services import code_intelligence_service


class _DummyLifespanContext:
    def __init__(self, base_path: str):
        self.base_path = base_path


class _DummyRequestContext:
    def __init__(self, base_path: str):
        self.lifespan_context = _DummyLifespanContext(base_path)


class _DummyCtx:
    def __init__(self, base_path: str):
        self.request_context = _DummyRequestContext(base_path)


def test_rust_deep_index_summary_and_symbol_body(monkeypatch):
    sample_project = (
        Path(__file__).resolve().parents[2]
        / "test"
        / "sample-projects"
        / "rust"
        / "conversation"
    )
    assert sample_project.exists()

    manager = SQLiteIndexManager()
    assert manager.set_project_path(str(sample_project))
    assert manager.build_index()
    assert manager.load_index()

    summary = manager.get_file_summary("src/conversation.rs")
    assert summary is not None
    assert summary["language"] == "rust"
    assert summary["symbol_count"] > 0

    function_names = {item["name"] for item in summary["functions"]}
    method_names = {item["name"] for item in summary["methods"]}
    class_names = {item["name"] for item in summary["classes"]}

    assert "run" in function_names
    assert "helper" in function_names
    assert "Conversation.new" in method_names
    assert "Conversation.append" in method_names
    assert "Conversation" in class_names
    assert "Status" in class_names
    assert "Runnable" in class_names

    assert "std::collections::VecDeque" in summary["imports"]

    # Use the service path so we validate get_symbol_body with Rust symbols.
    monkeypatch.setattr(code_intelligence_service, "get_index_manager", lambda: manager)
    service = code_intelligence_service.CodeIntelligenceService(ctx=_DummyCtx(str(sample_project)))

    run_body = service.get_symbol_body("src/conversation.rs", "run")
    assert run_body["status"] == "success"
    assert run_body["type"] == "function"
    assert "pub fn run" in run_body["code"]

    append_body = service.get_symbol_body("src/conversation.rs", "append")
    assert append_body["status"] == "success"
    assert append_body["type"] == "method"
    assert append_body["symbol_name"] == "append"
    assert "pub fn append" in append_body["code"]


def test_rust_symbol_body_requires_qualified_name_when_ambiguous(tmp_path, monkeypatch):
    sample_project = tmp_path / "rust-ambiguous"
    src_dir = sample_project / "src"
    src_dir.mkdir(parents=True)

    (sample_project / "Cargo.toml").write_text(
        "[package]\nname = \"rust-ambiguous\"\nversion = \"0.1.0\"\nedition = \"2021\"\n",
        encoding="utf-8",
    )
    (src_dir / "lib.rs").write_text(
        "\n".join(
            [
                "mod alpha {",
                "    pub fn helper() {}",
                "}",
                "",
                "mod beta {",
                "    pub fn helper() {}",
                "}",
            ]
        ),
        encoding="utf-8",
    )

    manager = SQLiteIndexManager()
    assert manager.set_project_path(str(sample_project))
    assert manager.build_index()
    assert manager.load_index()

    monkeypatch.setattr(code_intelligence_service, "get_index_manager", lambda: manager)
    service = code_intelligence_service.CodeIntelligenceService(ctx=_DummyCtx(str(sample_project)))

    ambiguous = service.get_symbol_body("src/lib.rs", "helper")
    assert ambiguous["status"] == "error"
    assert "ambiguous" in ambiguous["message"]
    assert ambiguous["candidates"] == ["alpha::helper", "beta::helper"]

    qualified = service.get_symbol_body("src/lib.rs", "alpha::helper")
    assert qualified["status"] == "success"
    assert qualified["type"] == "function"
    assert "pub fn helper" in qualified["code"]
