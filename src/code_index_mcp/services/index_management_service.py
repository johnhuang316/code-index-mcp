"""
Index Management Service - Business logic for index lifecycle management.

This service handles the business logic for index rebuilding, status monitoring,
and index-related operations using the new JSON-based indexing system.
"""
import time
import logging
import os
import json

from typing import Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

from .base_service import BaseService
from ..indexing import get_index_manager, get_shallow_index_manager, DeepIndexManager


@dataclass
class IndexRebuildResult:
    """Business result for index rebuild operations."""
    file_count: int
    rebuild_time: float
    status: str
    message: str


class IndexManagementService(BaseService):
    """
    Business service for index lifecycle management.

    This service orchestrates index management workflows using the new
    JSON-based indexing system for optimal LLM performance.
    """

    def __init__(self, ctx):
        super().__init__(ctx)
        # Deep manager (symbols/files, legacy JSON index manager)
        self._index_manager = get_index_manager()
        # Shallow manager (file-list only) for default workflows
        self._shallow_manager = get_shallow_index_manager()
        # Optional wrapper for explicit deep builds
        self._deep_wrapper = DeepIndexManager()

    def rebuild_index(self) -> str:
        """
        Rebuild the project index (DEFAULT: shallow file list).

        For deep/symbol rebuilds, use build_deep_index() tool instead.

        Returns:
            Success message with rebuild information

        Raises:
            ValueError: If project not set up or rebuild fails
        """
        # Business validation
        self._validate_rebuild_request()

        # Get user-configured exclude patterns
        excludes = self._get_exclude_patterns()

        # Shallow rebuild only (fast path)
        if not self._shallow_manager.set_project_path(self.base_path, excludes):
            raise RuntimeError("Failed to set project path (shallow) in index manager")
        if not self._shallow_manager.build_index():
            raise RuntimeError("Failed to rebuild shallow index")

        try:
            count = len(self._shallow_manager.get_file_list())
        except Exception:
            count = 0
        return f"Shallow index re-built with {count} files."

    def get_rebuild_status(self) -> Dict[str, Any]:
        """
        Get current index rebuild status information.

        Returns:
            Dictionary with rebuild status and metadata
        """
        # Check if project is set up
        if not self.base_path:
            return {
                'status': 'not_initialized',
                'message': 'Project not initialized',
                'is_rebuilding': False
            }

        # Get index stats from the new JSON system
        stats = self._index_manager.get_index_stats()
        
        return {
            'status': 'ready' if stats.get('status') == 'loaded' else 'needs_rebuild',
            'index_available': stats.get('status') == 'loaded',
            'is_rebuilding': False,
            'project_path': self.base_path,
            'file_count': stats.get('indexed_files', 0),
            'total_symbols': stats.get('total_symbols', 0),
            'symbol_types': stats.get('symbol_types', {}),
            'languages': stats.get('languages', [])
        }

    def _validate_rebuild_request(self) -> None:
        """
        Validate the index rebuild request according to business rules.

        Raises:
            ValueError: If validation fails
        """
        # Business rule: Project must be set up
        self._require_project_setup()

    def _get_exclude_patterns(self) -> List[str]:
        """Read exclude patterns from project settings for indexing.

        Returns:
            List of directory/file patterns to exclude from indexing
        """
        patterns: List[str] = []
        if not self.settings:
            return patterns
        try:
            config = self.settings.get_file_watcher_config()
            for key in ('exclude_patterns', 'additional_exclude_patterns'):
                for pattern in config.get(key) or []:
                    if isinstance(pattern, str) and pattern.strip():
                        patterns.append(pattern.strip())
        except Exception:  # noqa: BLE001 - fallback if config fails
            pass
        return patterns

    def _execute_rebuild_workflow(self) -> IndexRebuildResult:
        """
        Execute the core index rebuild business workflow.

        Returns:
            IndexRebuildResult with rebuild data
        """
        start_time = time.time()

        # Get user-configured exclude patterns
        excludes = self._get_exclude_patterns()

        # Set project path in index manager with exclusions
        if not self._index_manager.set_project_path(self.base_path, excludes):
            raise RuntimeError("Failed to set project path in index manager")

        # Rebuild the index
        if not self._index_manager.refresh_index():
            raise RuntimeError("Failed to rebuild index")

        # Get stats for result
        stats = self._index_manager.get_index_stats()
        file_count = stats.get('indexed_files', 0)

        rebuild_time = time.time() - start_time

        return IndexRebuildResult(
            file_count=file_count,
            rebuild_time=rebuild_time,
            status='success',
            message=f"Index rebuilt successfully with {file_count} files"
        )


    def _format_rebuild_result(self, result: IndexRebuildResult) -> str:
        """
        Format the rebuild result according to business requirements.

        Args:
            result: Rebuild result data

        Returns:
            Formatted result string for MCP response
        """
        return f"Project re-indexed. Found {result.file_count} files."

    def build_shallow_index(self) -> str:
        """
        Build and persist the shallow index (file list only).

        Returns:
            Success message including file count if available.

        Raises:
            ValueError/RuntimeError on validation or build failure
        """
        # Ensure project is set up
        self._require_project_setup()

        # Get user-configured exclude patterns
        excludes = self._get_exclude_patterns()

        # Initialize manager with current base path and exclusions
        if not self._shallow_manager.set_project_path(self.base_path, excludes):
            raise RuntimeError("Failed to set project path in index manager")

        # Build shallow index
        if not self._shallow_manager.build_index():
            raise RuntimeError("Failed to build shallow index")

        # Try to report count
        count = 0
        try:
            shallow_path = getattr(self._shallow_manager, 'index_path', None)
            if shallow_path and os.path.exists(shallow_path):
                with open(shallow_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        count = len(data)
        except Exception as e:  # noqa: BLE001 - safe fallback to zero
            logger.debug(f"Unable to read shallow index count: {e}")

        return f"Shallow index built{f' with {count} files' if count else ''}."

    def rebuild_deep_index(self) -> str:
        """Rebuild the deep index using the original workflow."""
        # Business validation
        self._validate_rebuild_request()

        # Deep rebuild via existing workflow
        result = self._execute_rebuild_workflow()
        return self._format_rebuild_result(result)
