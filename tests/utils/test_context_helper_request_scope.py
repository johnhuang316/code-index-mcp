"""Tests for request-scoped project resolution in ContextHelper."""

from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = ROOT / 'src'
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from code_index_mcp.request_context import RequestContextManager
from code_index_mcp.utils.context_helper import ContextHelper


def _make_context(base_path="", settings=None, file_count=0):
    lifespan_context = SimpleNamespace(
        base_path=base_path,
        settings=settings,
        file_count=file_count,
    )
    return SimpleNamespace(request_context=SimpleNamespace(lifespan_context=lifespan_context))


def test_context_helper_prefers_request_project_path_over_lifespan_base_path():
    ctx = _make_context(base_path="/project-a")
    helper = ContextHelper(ctx)

    with RequestContextManager("/project-b"):
        assert helper.base_path == "/project-b"


def test_context_helper_uses_lifespan_base_path_without_request_scope():
    ctx = _make_context(base_path="/project-a")

    assert ContextHelper(ctx).base_path == "/project-a"


def test_context_helper_keeps_settings_and_file_count_from_lifespan_state():
    settings = object()
    ctx = _make_context(base_path="/project-a", settings=settings, file_count=7)
    helper = ContextHelper(ctx)

    with RequestContextManager("/project-b"):
        assert helper.base_path == "/project-b"
        assert helper.settings is settings
        assert helper.file_count == 7
