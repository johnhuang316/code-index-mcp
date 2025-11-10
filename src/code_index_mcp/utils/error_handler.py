"""
Decorator-based error handling for MCP entry points.

This module provides consistent error handling across all MCP tools, resources, and prompts.
"""

import functools
import json
from typing import Any, Callable


class MCPToolError(RuntimeError):
    """Exception raised when an MCP entry point fails."""

    def __init__(self, message: str):
        super().__init__(message)


def handle_mcp_errors(return_type: str = 'str') -> Callable:
    """
    Decorator to handle exceptions in MCP entry points consistently.

    This decorator catches all exceptions and rethrows them as MCPToolError after
    formatting a consistent error message. FastMCP converts the raised exception
    into a structured error response for the client.

    Args:
        return_type: Label used to format the error message for logging/consistency.
            - 'str'/'list'/others: Prefixes message with "Error: ..."
            - 'dict'/'json': Prefixes message with "Operation failed: ..."

    Returns:
        Decorator function that wraps MCP entry points with error handling

    Example:
        @mcp.tool()
        @handle_mcp_errors(return_type='str')
        def set_project_path(path: str, ctx: Context) -> str:
            from ..services.project_management_service import ProjectManagementService
            return ProjectManagementService(ctx).initialize_project(path)

        @mcp.tool()
        @handle_mcp_errors(return_type='dict')
        def search_code_advanced(pattern: str, ctx: Context, **kwargs) -> Dict[str, Any]:
            return SearchService(ctx).search_code(pattern, **kwargs)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except MCPToolError:
                raise
            except Exception as exc:
                error_message = str(exc)
                formatted = _format_error_message(error_message, return_type)
                raise MCPToolError(formatted) from exc

        return wrapper
    return decorator


def handle_mcp_resource_errors(func: Callable) -> Callable:
    """
    Specialized error handler for MCP resources that always return strings.

    This is a convenience decorator specifically for @mcp.resource decorated functions
    which always return string responses.

    Args:
        func: The MCP resource function to wrap

    Returns:
        Wrapped function with error handling

    Example:
        @mcp.resource("config://code-indexer")
        @handle_mcp_resource_errors
        def get_config(ctx: Context) -> str:
            from ..services.project_management_service import ProjectManagementService
            return ProjectManagementService(ctx).get_project_config()
    """
    return handle_mcp_errors(return_type='str')(func)


def handle_mcp_tool_errors(return_type: str = 'str') -> Callable:
    """
    Specialized error handler for MCP tools with flexible return types.

    This is a convenience decorator specifically for @mcp.tool decorated functions
    which may return either strings or dictionaries.

    Args:
        return_type: Label describing the successful payload shape (e.g. 'str', 'dict', 'list').

    Returns:
        Decorator function for MCP tools

    Example:
        @mcp.tool()
        @handle_mcp_tool_errors(return_type='dict')
        def find_files(pattern: str, ctx: Context) -> Dict[str, Any]:
            from ..services.file_discovery_service import FileDiscoveryService
            return FileDiscoveryService(ctx).find_files(pattern)
    """
    return handle_mcp_errors(return_type=return_type)


def _format_error_message(error_message: str, return_type: str) -> str:
    """
    Convert an exception message into a consistent string for MCP errors.

    Args:
        error_message: The raw exception message.
        return_type: The declared return type for the decorated entry point.

    Returns:
        A string representation suitable for raising as MCPToolError.
    """
    if return_type in {'dict', 'json'}:
        return f"Operation failed: {error_message}"
    return f"Error: {error_message}"
