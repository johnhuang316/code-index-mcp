"""
File Discovery Service - Business logic for intelligent file discovery.

This service handles the business logic for finding files using the new
JSON-based indexing system optimized for LLM consumption.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .base_service import BaseService
from ..indexing import get_shallow_index_manager


@dataclass
class FileDiscoveryResult:
    """Business result for file discovery operations."""
    files: List[str]
    total_count: int
    pattern_used: str
    search_strategy: str
    metadata: Dict[str, Any]


class FileDiscoveryService(BaseService):
    """
    Business service for intelligent file discovery using JSON indexing.

    This service provides fast file discovery using the optimized JSON
    indexing system for efficient LLM-oriented responses.
    """

    def __init__(self, ctx):
        super().__init__(ctx)
        self._index_manager = get_shallow_index_manager()

    def find_files(self, pattern: str, max_results: Optional[int] = None) -> List[str]:
        """
        Find files matching the given pattern using JSON indexing.

        Args:
            pattern: Glob pattern to search for (e.g., "*.py", "test_*.js")
            max_results: Maximum number of results to return (None for no limit)

        Returns:
            List of file paths matching the pattern

        Raises:
            ValueError: If pattern is invalid or project not set up
        """
        # Business validation
        self._validate_discovery_request(pattern)

        # Get files from JSON index
        files = self._index_manager.find_files(pattern)
        
        # Apply max_results limit if specified
        if max_results and len(files) > max_results:
            files = files[:max_results]
        
        return files

    def _validate_discovery_request(self, pattern: str) -> None:
        """
        Validate the file discovery request according to business rules.

        Args:
            pattern: Pattern to validate

        Raises:
            ValueError: If validation fails
        """
        # Ensure project is set up
        self._require_project_setup()

        # Validate pattern
        if not pattern or not pattern.strip():
            raise ValueError("Search pattern cannot be empty")
