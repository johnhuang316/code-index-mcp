"""
Project Context Middleware - Extract project path from HTTP header.

This middleware reads the `Mcp-Project-Path` header from incoming requests
and sets the request context for per-project index manager isolation.
"""

from __future__ import annotations

import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ..request_context import set_request_project_path, clear_request_project_path

logger = logging.getLogger(__name__)


class ProjectContextMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and set project context from HTTP headers.

    The proxy sends the project path via the `Mcp-Project-Path` header,
    allowing this middleware to set the request-scoped context before
    the request is processed.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Extract project path from header (case-insensitive)
        project_path = request.headers.get("mcp-project-path")

        if project_path:
            logger.debug(f"[Middleware] Project path from header: {project_path}")

        try:
            # Set the context for this request
            set_request_project_path(project_path)

            # Process the request
            response = await call_next(request)

            return response
        finally:
            # Clear context after request completes
            clear_request_project_path()
