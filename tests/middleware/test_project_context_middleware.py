"""Tests for project context middleware and request context lifecycle."""

from pathlib import Path
import sys

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = ROOT / 'src'
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from code_index_mcp.middleware.project_context_middleware import ProjectContextMiddleware
from code_index_mcp.request_context import (
    RequestContextManager,
    get_request_project_path,
    reset_request_project_path,
    set_request_project_path,
)


def test_request_context_manager_restores_outer_value():
    with RequestContextManager("outer"):
        with RequestContextManager("inner"):
            assert get_request_project_path() == "inner"
        assert get_request_project_path() == "outer"


def test_set_request_project_path_reset_restores_outer_value():
    with RequestContextManager("outer"):
        token = set_request_project_path("inner")
        assert get_request_project_path() == "inner"

        reset_request_project_path(token)

        assert get_request_project_path() == "outer"


def _build_app(handler):
    app = Starlette(routes=[Route("/", handler)])
    app.add_middleware(ProjectContextMiddleware)
    return app


@pytest.mark.anyio
async def test_middleware_restores_prior_context_after_request(anyio_backend):
    async def homepage(_request):
        return JSONResponse({"project_path": get_request_project_path()})

    transport = ASGITransport(app=_build_app(homepage))

    with RequestContextManager("outer"):
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/", headers={"mcp-project-path": "inner"})

        assert response.status_code == 200
        assert response.json() == {"project_path": "inner"}
        assert get_request_project_path() == "outer"


@pytest.mark.anyio
async def test_middleware_restores_prior_context_when_downstream_raises(anyio_backend):
    async def boom(_request):
        assert get_request_project_path() == "inner"
        raise RuntimeError("boom")

    transport = ASGITransport(app=_build_app(boom))

    with RequestContextManager("outer"):
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            with pytest.raises(RuntimeError, match="boom"):
                await client.get("/", headers={"mcp-project-path": "inner"})

        assert get_request_project_path() == "outer"


@pytest.fixture
def anyio_backend():
    return "asyncio"
