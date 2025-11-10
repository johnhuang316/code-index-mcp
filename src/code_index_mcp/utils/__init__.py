"""
Utility modules for the Code Index MCP server.

This package contains shared utilities used across services:
- error_handler: Decorator-based error handling for MCP entry points
- context_helper: Context access utilities and helpers
- validation: Common validation logic
- response_formatter: Response formatting utilities
"""

from .error_handler import (
    handle_mcp_errors,
    handle_mcp_resource_errors,
    handle_mcp_tool_errors,
    MCPToolError,
)
from .context_helper import ContextHelper
from .validation import ValidationHelper
from .response_formatter import ResponseFormatter
from .file_filter import FileFilter

__all__ = [
    'handle_mcp_errors',
    'handle_mcp_resource_errors',
    'handle_mcp_tool_errors',
    'MCPToolError',
    'ContextHelper', 
    'ValidationHelper',
    'ResponseFormatter',
    'FileFilter'
]
