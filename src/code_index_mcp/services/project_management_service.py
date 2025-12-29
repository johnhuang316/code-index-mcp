"""
Project Management Service - Business logic for project lifecycle management.

This service handles the business logic for project initialization, configuration,
and lifecycle management using the new JSON-based indexing system.
"""
import logging
from typing import Dict, Any, List
from dataclasses import dataclass
from contextlib import contextmanager

from .base_service import BaseService
from ..utils.response_formatter import ResponseFormatter
from ..constants import SUPPORTED_EXTENSIONS
from ..indexing import get_index_manager, get_shallow_index_manager

logger = logging.getLogger(__name__)


@dataclass
class ProjectInitializationResult:
    """Business result for project initialization operations."""
    project_path: str
    file_count: int
    index_source: str  # 'loaded_existing' or 'built_new'
    search_capabilities: str
    monitoring_status: str
    message: str


class ProjectManagementService(BaseService):
    """
    Business service for project lifecycle management.

    This service orchestrates project initialization workflows by composing
    technical tools to achieve business goals like setting up projects,
    managing configurations, and coordinating system components.
    """

    def __init__(self, ctx):
        super().__init__(ctx)
        # Deep index manager (legacy full index)
        self._index_manager = get_index_manager()
        # Shallow index manager (default for initialization)
        self._shallow_manager = get_shallow_index_manager()
        from ..tools.config import ProjectConfigTool
        self._config_tool = ProjectConfigTool()
        # Import FileWatcherTool locally to avoid circular import
        from ..tools.monitoring import FileWatcherTool
        self._watcher_tool = FileWatcherTool(ctx)


    @contextmanager
    def _noop_operation(self, *_args, **_kwargs):
        yield

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

    def initialize_project(self, path: str) -> str:
        """
        Initialize a project with comprehensive business logic.

        This is the main business method that orchestrates the project
        initialization workflow, handling validation, cleanup, setup,
        and coordination of all project components.

        Args:
            path: Project directory path to initialize

        Returns:
            Success message with project information

        Raises:
            ValueError: If path is invalid or initialization fails
        """
        # Business validation
        self._validate_initialization_request(path)

        # Business workflow: Execute initialization
        result = self._execute_initialization_workflow(path)

        # Business result formatting
        return self._format_initialization_result(result)

    def _validate_initialization_request(self, path: str) -> None:
        """
        Validate the project initialization request according to business rules.

        Args:
            path: Project path to validate

        Raises:
            ValueError: If validation fails
        """
        # Business rule: Path must be valid
        error = self._config_tool.validate_project_path(path)
        if error:
            raise ValueError(error)

    def _execute_initialization_workflow(self, path: str) -> ProjectInitializationResult:
        """
        Execute the core project initialization business workflow.

        Args:
            path: Project path to initialize

        Returns:
            ProjectInitializationResult with initialization data
        """
        # Business step 1: Initialize config tool
        self._config_tool.initialize_settings(path)

        # Normalize path for consistent processing
        normalized_path = self._config_tool.normalize_project_path(path)

        # Business step 2: Cleanup existing project state
        self._cleanup_existing_project()

        # Business step 3: Initialize shallow index by default (fast path)
        index_result = self._initialize_shallow_index_manager(normalized_path)

        # Business step 3.1: Store index manager in context for other services
        self.helper.update_index_manager(self._index_manager)

        # Business step 4: Setup file monitoring
        monitoring_result = self._setup_file_monitoring(normalized_path)

        # Business step 4: Update system state
        self._update_project_state(normalized_path, index_result['file_count'])

        # Business step 6: Get search capabilities info
        search_info = self._get_search_capabilities_info()

        return ProjectInitializationResult(
            project_path=normalized_path,
            file_count=index_result['file_count'],
            index_source=index_result['source'],
            search_capabilities=search_info,
            monitoring_status=monitoring_result,
            message=f"Project initialized: {normalized_path}"
        )

    def _cleanup_existing_project(self) -> None:
        """Business logic to cleanup existing project state."""
        with self._noop_operation():
            # Stop existing file monitoring
            self._watcher_tool.stop_existing_watcher()

            # Clear existing index cache
            self.helper.clear_index_cache()

            # Clear any existing index state
            pass

    def _initialize_shallow_index_manager(self, project_path: str) -> Dict[str, Any]:
        """
        Business logic to initialize the shallow index manager by default.

        Args:
            project_path: Project path

        Returns:
            Dictionary with initialization results
        """
        # Get user-configured exclude patterns
        excludes = self._get_exclude_patterns()

        # Set project path in shallow manager with exclusions
        if not self._shallow_manager.set_project_path(project_path, excludes):
            raise RuntimeError(f"Failed to set project path (shallow): {project_path}")

        # Update context
        self.helper.update_base_path(project_path)

        # Try to load existing shallow index or build new one
        if self._shallow_manager.load_index():
            source = "loaded_existing"
        else:
            if not self._shallow_manager.build_index():
                raise RuntimeError("Failed to build shallow index")
            source = "built_new"

        # Determine file count from shallow list
        try:
            files = self._shallow_manager.get_file_list()
            file_count = len(files)
        except Exception:  # noqa: BLE001 - safe fallback
            file_count = 0

        return {
            'file_count': file_count,
            'source': source,
            'total_symbols': 0,
            'languages': []
        }


    def _is_valid_existing_index(self, index_data: Dict[str, Any]) -> bool:
        """
        Business rule to determine if existing index is valid and usable.

        Args:
            index_data: Index data to validate

        Returns:
            True if index is valid and usable, False otherwise
        """
        if not index_data or not isinstance(index_data, dict):
            return False

        # Business rule: Must have new format metadata
        if 'index_metadata' not in index_data:
            return False

        # Business rule: Must be compatible version
        version = index_data.get('index_metadata', {}).get('version', '')
        return version >= '3.0'

    def _load_existing_index(self, index_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Business logic to load and use existing index.

        Args:
            index_data: Existing index data

        Returns:
            Dictionary with loading results
        """


        # Note: Legacy index loading is now handled by UnifiedIndexManager
        # This method is kept for backward compatibility but functionality moved

        # Extract file count from metadata
        file_count = index_data.get('project_metadata', {}).get('total_files', 0)



        return {
            'file_count': file_count,
            'source': 'loaded_existing'
        }


    def _setup_file_monitoring(self, project_path: str) -> str:
        """
        Business logic to setup file monitoring for the project.

        Args:
            project_path: Project path to monitor

        Returns:
            String describing monitoring setup result
        """


        try:
            # Create rebuild callback that uses the JSON index manager
            def rebuild_callback():
                logger.info("File watcher triggered rebuild callback")
                try:
                    logger.debug(f"Starting shallow index rebuild for: {project_path}")
                    # Business logic: File changed, rebuild using SHALLOW index manager
                    try:
                        if not self._shallow_manager.set_project_path(project_path):
                            logger.warning("Shallow manager set_project_path failed")
                            return False
                        if self._shallow_manager.build_index():
                            files = self._shallow_manager.get_file_list()
                            logger.info(f"File watcher shallow rebuild completed successfully - files {len(files)}")
                            return True
                        else:
                            logger.warning("File watcher shallow rebuild failed")
                            return False
                    except Exception as e:
                        import traceback
                        logger.error(f"File watcher shallow rebuild failed: {e}")
                        logger.error(f"Traceback: {traceback.format_exc()}")
                        return False
                except Exception as e:
                    import traceback
                    logger.error(f"File watcher rebuild failed: {e}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    return False

            # Start monitoring using watcher tool
            success = self._watcher_tool.start_monitoring(project_path, rebuild_callback)

            if success:
                # Store watcher in context for later access
                self._watcher_tool.store_in_context()
                # No logging
                return "monitoring_active"
            else:
                self._watcher_tool.record_error("Failed to start file monitoring")
                return "monitoring_failed"

        except Exception as e:
            error_msg = f"File monitoring setup failed: {e}"
            self._watcher_tool.record_error(error_msg)
            return "monitoring_error"

    def _update_project_state(self, project_path: str, file_count: int) -> None:
        """Business logic to update system state after project initialization."""


        # Update context with file count
        self.helper.update_file_count(file_count)

        # No logging

    def _get_search_capabilities_info(self) -> str:
        """Business logic to get search capabilities information."""
        search_info = self._config_tool.get_search_tool_info()

        if search_info['available']:
            return f"Advanced search enabled ({search_info['name']})"
        else:
            return "Basic search available"

    def _format_initialization_result(self, result: ProjectInitializationResult) -> str:
        """
        Format the initialization result according to business requirements.

        Args:
            result: Initialization result data

        Returns:
            Formatted result string for MCP response
        """
        if result.index_source == 'unified_manager':
            message = (f"Project path set to: {result.project_path}. "
                      f"Initialized unified index with {result.file_count} files. "
                      f"{result.search_capabilities}.")
        elif result.index_source == 'failed':
            message = (f"Project path set to: {result.project_path}. "
                      f"Index initialization failed. Some features may be limited. "
                      f"{result.search_capabilities}.")
        else:
            message = (f"Project path set to: {result.project_path}. "
                      f"Indexed {result.file_count} files. "
                      f"{result.search_capabilities}.")

        if result.monitoring_status != "monitoring_active":
            message += " (File monitoring unavailable - use manual refresh)"

        return message

    def get_project_config(self) -> str:
        """
        Get the current project configuration for MCP resource.

        Returns:
            JSON formatted configuration string
        """

        # Check if project is configured
        if not self.helper.base_path:
            config_data = {
                "status": "not_configured",
                "message": ("Project path not set. Please use set_project_path "
                           "to set a project directory first."),
                "supported_extensions": SUPPORTED_EXTENSIONS
            }
            return ResponseFormatter.config_response(config_data)

        # Get settings stats
        settings_stats = self.helper.settings.get_stats() if self.helper.settings else {}

        config_data = {
            "base_path": self.helper.base_path,
            "supported_extensions": SUPPORTED_EXTENSIONS,
            "file_count": self.helper.file_count,
            "settings_directory": self.helper.settings.settings_path if self.helper.settings else "",
            "settings_stats": settings_stats
        }

        return ResponseFormatter.config_response(config_data)

    # Removed: get_project_structure; the project structure resource is deprecated
