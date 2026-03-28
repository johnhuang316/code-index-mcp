"""
Request Context - Per-request project context using contextvars.

This module provides request-scoped project path management to support
multiple Claude Code sessions using different projects simultaneously.

The context is set from the `Mcp-Project-Path` HTTP header by the proxy,
allowing each request to operate on its own project without interference.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Context variable for request-scoped project path
_project_path_var: ContextVar[Optional[str]] = ContextVar(
    'project_path', default=None
)


@dataclass
class RequestContext:
    """Immutable snapshot of request context."""
    project_path: Optional[str] = None


def get_request_project_path() -> Optional[str]:
    """Get the current request's project path.

    Returns:
        Project path from HTTP header, or None if not set
    """
    return _project_path_var.get()


def set_request_project_path(path: Optional[str]) -> Token[Optional[str]]:
    """Set the current request's project path.

    Args:
        path: Project path from Mcp-Project-Path header
    """
    if path:
        logger.debug(f"[RequestContext] Setting project path: {path}")
    return _project_path_var.set(path)


def reset_request_project_path(token: Token[Optional[str]]) -> None:
    """Restore the current request's project path using a ContextVar token."""
    _project_path_var.reset(token)


class RequestContextManager:
    """Context manager for request-scoped project path.

    Usage:
        with RequestContextManager(project_path):
            # All operations in this block use project_path
            pass
    """

    def __init__(self, project_path: Optional[str]):
        self.project_path = project_path
        self._token: Optional[Token[Optional[str]]] = None

    def __enter__(self) -> 'RequestContextManager':
        self._token = set_request_project_path(self.project_path)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._token is not None:
            reset_request_project_path(self._token)
        return None
