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


PHP_HELPER = """<?php
namespace Acme\\Core\\Helper;

use Acme\\Core\\Renderer\\Renderer;

class Data
{
    private Renderer $renderer;

    public function __construct(Renderer $renderer)
    {
        $this->renderer = $renderer;
    }

    /**
     * Creates an entity from a class name.
     *
     * @param string $class
     * @return mixed
     */
    public function createEntity(string $class): mixed
    {
        return new $class();
    }

    public function buildEntity(string $filename, string $class): mixed
    {
        $this->renderer->render($filename);
        return $this->createEntity($class);
    }

    public static function make(): self
    {
        return new self(new Renderer());
    }
}

function helper_fn(string $value): string
{
    return trim($value);
}
"""


def _build_project(tmp_path) -> Path:
    project = tmp_path / "php-project"
    helper_dir = project / "app" / "code" / "Helper"
    helper_dir.mkdir(parents=True)
    (helper_dir / "Data.php").write_text(PHP_HELPER, encoding="utf-8")
    return project


def test_php_deep_index_summary_and_symbol_body(tmp_path, monkeypatch):
    project = _build_project(tmp_path)

    manager = SQLiteIndexManager()
    assert manager.set_project_path(str(project))
    assert manager.build_index()
    assert manager.load_index()

    summary = manager.get_file_summary("app/code/Helper/Data.php")
    assert summary is not None
    assert summary["language"] == "php"

    # Regression guard: PHP previously routed to FallbackParsingStrategy and
    # reported zero symbols for every file.
    assert summary["symbol_count"] > 0

    function_names = {item["name"] for item in summary["functions"]}
    method_names = {item["name"] for item in summary["methods"]}
    class_names = {item["name"] for item in summary["classes"]}

    assert "Data" in class_names
    assert "Data.createEntity" in method_names
    assert "Data.buildEntity" in method_names
    assert "Data.make" in method_names
    assert "helper_fn" in function_names
    assert "Acme\\Core\\Renderer\\Renderer" in summary["imports"]

    monkeypatch.setattr(code_intelligence_service, "get_index_manager", lambda: manager)
    service = code_intelligence_service.CodeIntelligenceService(
        ctx=_DummyCtx(str(project))
    )

    short_body = service.get_symbol_body("app/code/Helper/Data.php", "createEntity")
    assert short_body["status"] == "success"
    assert short_body["type"] == "method"
    assert "public function createEntity" in short_body["code"]

    qualified_body = service.get_symbol_body(
        "app/code/Helper/Data.php", "Data.createEntity"
    )
    assert qualified_body["status"] == "success"
    assert "Creates an entity from a class name." in (qualified_body.get("docstring") or "")


def test_php_deep_index_records_called_by(tmp_path):
    project = _build_project(tmp_path)

    manager = SQLiteIndexManager()
    assert manager.set_project_path(str(project))
    assert manager.build_index()
    assert manager.load_index()

    summary = manager.get_file_summary("app/code/Helper/Data.php")
    assert summary is not None

    create_entity = next(
        item for item in summary["methods"] if item["name"] == "Data.createEntity"
    )

    assert any(
        caller.endswith("Data.buildEntity") for caller in create_entity["called_by"]
    )


def test_php_is_indexed_as_a_language(tmp_path):
    project = _build_project(tmp_path)

    manager = SQLiteIndexManager()
    assert manager.set_project_path(str(project))
    assert manager.build_index()
    assert manager.load_index()

    stats = manager.get_index_stats()
    assert "php" in stats.get("languages", [])
