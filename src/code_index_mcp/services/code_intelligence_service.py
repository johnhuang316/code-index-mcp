"""
Code Intelligence Service - Business logic for code analysis and understanding.

This service handles the business logic for analyzing code files using the new
JSON-based indexing system optimized for LLM consumption.
"""

import logging
import os
from typing import Dict, Any

from .base_service import BaseService
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





