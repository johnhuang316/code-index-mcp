"""
Code Intelligence Service - Business logic for code analysis and understanding.

This service handles the business logic for analyzing code files using the new
JSON-based indexing system optimized for LLM consumption.
"""

import logging
import os
from typing import Dict, Any

from .base_service import BaseService

# Configuration for get_symbol_body (conservative for stability)
# Philosophy: Return minimal data reliably, use line numbers to drill down
MAX_SYMBOL_LINES = 150  # max lines to return for a single symbol
from ..tools.filesystem import FileSystemTool
from ..indexing import get_index_manager

logger = logging.getLogger(__name__)


class CodeIntelligenceService(BaseService):
    """
    Business service for code analysis and intelligence using JSON indexing.

    This service provides comprehensive code analysis using the optimized
    JSON-based indexing system for fast LLM-friendly responses.
    """

    def __init__(self, ctx):
        super().__init__(ctx)
        self._filesystem_tool = FileSystemTool()

    def analyze_file(self, file_path: str) -> Dict[str, Any]:
        """
        Analyze a file and return comprehensive intelligence.

        This is the main business method that orchestrates the file analysis
        workflow, choosing the best analysis strategy and providing rich
        insights about the code.

        Args:
            file_path: Path to the file to analyze (relative to project root)

        Returns:
            Dictionary with comprehensive file analysis

        Raises:
            ValueError: If file path is invalid or analysis fails
        """
        # Business validation
        self._validate_analysis_request(file_path)

        # Use the global index manager
        index_manager = get_index_manager()
        
        # Debug logging
        logger.info(f"Getting file summary for: {file_path}")
        logger.info(f"Index manager state - Project path: {index_manager.project_path}")
        logger.info(f"Index manager state - Has builder: {index_manager.index_builder is not None}")
        if index_manager.index_builder:
            logger.info(f"Index manager state - Has index: {index_manager.index_builder.in_memory_index is not None}")
        
        # Get file summary from JSON index
        summary = index_manager.get_file_summary(file_path)
        logger.info(f"Summary result: {summary is not None}")

        # If deep index isn't available yet, return a helpful hint instead of error
        if not summary:
            return {
                "status": "needs_deep_index",
                "message": "Deep index not available. Please run build_deep_index before calling get_file_summary.",
                "file_path": file_path
            }

        return summary

    def _validate_analysis_request(self, file_path: str) -> None:
        """
        Validate the file analysis request according to business rules.

        Args:
            file_path: File path to validate

        Raises:
            ValueError: If validation fails
        """
        # Business rule: Project must be set up OR auto-initialization must be possible
        if self.base_path:
            # Standard validation if project is set up in context
            self._require_valid_file_path(file_path)
            full_path = os.path.join(self.base_path, file_path)
            if not os.path.exists(full_path):
                raise ValueError(f"File does not exist: {file_path}")
        else:
            # Allow proceeding if auto-initialization might work
            # The index manager will handle project discovery
            logger.info("Project not set in context, relying on index auto-initialization")
            
            # Basic file path validation only
            if not file_path or '..' in file_path:
                raise ValueError(f"Invalid file path: {file_path}")

    def get_symbol_body(self, file_path: str, symbol_name: str) -> Dict[str, Any]:
        """
        Get the code body of a specific symbol from a file.

        This method retrieves the actual source code of a function, method, or class
        by looking up its line range from the index and extracting that portion of the file.

        Args:
            file_path: Path to the file containing the symbol
            symbol_name: Name of the symbol (function, method, or class)

        Returns:
            Dictionary containing:
                - symbol_name: The name of the symbol
                - type: The type of symbol (function, method, class, etc.)
                - file_path: Path to the file
                - line: Start line number
                - end_line: End line number
                - code: The actual source code of the symbol
                - signature: The signature (if available)
                - docstring: The docstring (if available)
        """
        # Get file summary from index
        index_manager = get_index_manager()
        summary = index_manager.get_file_summary(file_path)

        if not summary:
            return {
                "status": "error",
                "message": "File not found in index or deep index not built",
                "file_path": file_path,
                "symbol_name": symbol_name
            }

        # Search for the symbol in functions, methods, and classes
        symbol_info = None
        symbol_type = None

        for func in summary.get("functions", []):
            if func.get("name") == symbol_name:
                symbol_info = func
                symbol_type = "function"
                break

        if not symbol_info:
            for method in summary.get("methods", []):
                if method.get("name") == symbol_name or method.get("name", "").endswith(f".{symbol_name}"):
                    symbol_info = method
                    symbol_type = "method"
                    break

        if not symbol_info:
            for cls in summary.get("classes", []):
                if cls.get("name") == symbol_name:
                    symbol_info = cls
                    symbol_type = "class"
                    break

        if not symbol_info:
            return {
                "status": "error",
                "message": f"Symbol '{symbol_name}' not found in file",
                "file_path": file_path,
                "symbol_name": symbol_name,
                "available_symbols": {
                    "functions": [f.get("name") for f in summary.get("functions", [])],
                    "methods": [m.get("name") for m in summary.get("methods", [])],
                    "classes": [c.get("name") for c in summary.get("classes", [])]
                }
            }

        line = symbol_info.get("line")
        end_line = symbol_info.get("end_line")

        if line is None:
            return {
                "status": "error",
                "message": "Symbol found but line information is missing",
                "file_path": file_path,
                "symbol_name": symbol_name
            }

        # Read the file content
        try:
            # Resolve full path
            if self.base_path:
                full_path = os.path.join(self.base_path, file_path)
            else:
                full_path = file_path

            with open(full_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Extract the symbol's code (1-indexed)
            start_idx = line - 1
            if end_line:
                end_idx = end_line  # end_line is inclusive
            else:
                # Fallback: read until next function/class or end of file
                end_idx = min(start_idx + 50, len(lines))  # Read up to 50 lines

            code_lines = lines[start_idx:end_idx]
            truncated = False
            if len(code_lines) > MAX_SYMBOL_LINES:
                code_lines = code_lines[:MAX_SYMBOL_LINES]
                truncated = True

            code = "".join(code_lines)
            if truncated:
                remaining = (end_idx - start_idx) - MAX_SYMBOL_LINES
                code += f"\n# ... truncated ({remaining} more lines, use line numbers to read specific sections)"

            return {
                "status": "success",
                "truncated": truncated,
                "symbol_name": symbol_name,
                "type": symbol_type,
                "file_path": file_path,
                "line": line,
                "end_line": end_line,
                "code": code,
                "signature": symbol_info.get("signature"),
                "docstring": symbol_info.get("docstring"),
                "called_by": symbol_info.get("called_by", [])
            }

        except FileNotFoundError:
            return {
                "status": "error",
                "message": f"File not found: {file_path}",
                "file_path": file_path,
                "symbol_name": symbol_name
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error reading file: {str(e)}",
                "file_path": file_path,
                "symbol_name": symbol_name
            }

