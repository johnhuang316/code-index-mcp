"""
Project management service for the Code Index MCP server.

This service handles project initialization, configuration management,
and project structure operations.
"""

import asyncio
import os
import json
from mcp.server.fastmcp import Context

from .base_service import BaseService
from ..utils import ValidationHelper, ResponseFormatter
from ..project_settings import ProjectSettings
from ..constants import SUPPORTED_EXTENSIONS


class ProjectService(BaseService):
    """
    Service for managing project initialization and configuration.

    This service handles:
    - Project path initialization and validation
    - Project configuration management
    - Project structure retrieval
    - Project metadata operations
    """

    def __init__(self, ctx: Context):
        """
        Initialize the project service.

        Args:
            ctx: The MCP Context object
        """
        super().__init__(ctx)
        # Service-specific initialization can be added here if needed
        self._project_switch_lock = asyncio.Lock()

    async def _stop_existing_file_watcher(self) -> None:
        """
        Stop and cleanup existing file watcher service if it exists.
        """
        try:
            # Get existing file watcher from context
            if (hasattr(self.ctx.request_context.lifespan_context, 'file_watcher_service') and
                self.ctx.request_context.lifespan_context.file_watcher_service):
                
                old_watcher = self.ctx.request_context.lifespan_context.file_watcher_service
                print("Stopping existing file watcher...")
                
                # Stop monitoring
                old_watcher.stop_monitoring()
                
                # Clear reference
                self.ctx.request_context.lifespan_context.file_watcher_service = None
                print("Existing file watcher stopped successfully")
                
        except Exception as e:
            print(f"Warning: Error stopping existing file watcher: {e}")
            # Continue anyway - we'll create a new one

    async def _start_new_file_watcher_with_retry(self, max_retries: int = 3) -> bool:
        """
        Start a new file watcher with retry logic.
        
        Args:
            max_retries: Maximum number of retry attempts
            
        Returns:
            True if file watcher started successfully, False otherwise
        """
        from .file_watcher_service import FileWatcherService
        from .index_service import IndexService
        
        for attempt in range(max_retries):
            try:
                print(f"Starting file watcher (attempt {attempt + 1}/{max_retries})...")
                
                # Create services
                file_watcher = FileWatcherService(self.ctx)
                index_service = IndexService(self.ctx)
                success = file_watcher.start_monitoring(
                    rebuild_callback=index_service.start_background_rebuild
                )
                
                if success:
                    # Store in context
                    self.ctx.request_context.lifespan_context.file_watcher_service = file_watcher
                    print("File watcher started successfully")
                    return True
                else:
                    print(f"File watcher failed to start (attempt {attempt + 1})")
                    
            except Exception as e:
                print(f"Error starting file watcher (attempt {attempt + 1}): {e}")
                
                # Wait before retry (except for last attempt)
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)
        
        # All attempts failed
        print(f"File watcher failed to start after {max_retries} attempts")
        return False

    def _record_file_watcher_error(self, message: str) -> None:
        """
        Record file watcher error for LLM notification.
        
        Args:
            message: Error message to record
        """
        import time
        
        error_info = {
            'status': 'failed',
            'message': f'{message}. Auto-refresh disabled. Please use manual refresh.',
            'timestamp': time.time(),
            'manual_refresh_required': True
        }
        
        # Store error in context for status reporting
        if hasattr(self.ctx.request_context.lifespan_context, '__dict__'):
            self.ctx.request_context.lifespan_context.file_watcher_error = error_info
        
        print(f"WARNING: File watcher error: {message}")
        print("   Auto-refresh is disabled. Use refresh_index for manual updates.")

    def initialize_project(self, path: str, generate_log_file: bool = False) -> str:
        """
        Initialize a project with the given path.

        Handles the logic for set_project_path MCP tool.

        Args:
            path: The project directory path to initialize

        Returns:
            Success message with project information

        Raises:
            ValueError: If path is invalid or initialization fails
        """
        # Run async logic synchronously
        import asyncio
        
        try:
            # Check if we're in an async context
            loop = asyncio.get_running_loop()
            # If we're in an async context, we need to run in a separate thread
            import concurrent.futures
            
            def run_async():
                return asyncio.run(self._initialize_project_with_lock(path, generate_log_file))
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_async)
                return future.result(timeout=60)  # 60 second timeout
                
        except RuntimeError:
            # No event loop running, we can use asyncio.run directly
            return asyncio.run(self._initialize_project_with_lock(path, generate_log_file))

    async def _initialize_project_with_lock(self, path: str, generate_log_file: bool = False) -> str:
        """
        Initialize project with async lock protection.
        """
        # Use atomic operation to prevent concurrent project switching
        async with self._project_switch_lock:
            return await self._initialize_project_atomic(path, generate_log_file)

    async def _initialize_project_atomic(self, path: str, generate_log_file: bool = False) -> str:
        """
        Atomic implementation of project initialization.
        """
        # Validate and normalize path
        norm_path = os.path.normpath(path)
        abs_path = os.path.abspath(norm_path)

        # Validate directory path
        error = ValidationHelper.validate_directory_path(abs_path)
        if error:
            raise ValueError(error)

        # Step 1: Stop existing file watcher first
        await self._stop_existing_file_watcher()

        # Step 2: Clear existing in-memory index and cache
        self.helper.clear_index_cache()

        # Step 3: Update the base path in context
        self.helper.update_base_path(abs_path)

        # Create settings manager for the project path
        project_settings = ProjectSettings(abs_path, skip_load=False)
        self.helper.update_settings(project_settings)

        print(f"Project settings path: {project_settings.settings_path}")

        # Check for version migration
        print("Checking for index version and migration...")
        migration_result = project_settings.migrate_legacy_index()
        if not migration_result:
            print("Legacy index detected, will rebuild with new system")

        # Try to load existing index
        print(f"Project path set to: {abs_path}")
        print("Attempting to load existing index...")

        loaded_index_data = None
        try:
            loaded_index_data = project_settings.load_index()
        except Exception as e:
            print(f"Could not load existing index: {e}")

        if loaded_index_data and isinstance(loaded_index_data, dict):
            # Check if it's the new format
            if ('index_metadata' in loaded_index_data and
                loaded_index_data.get('index_metadata', {}).get('version', '') >= '3.0'):
                print("Existing new-format index found and loaded successfully")

                # Update context with loaded index
                if hasattr(self.ctx.request_context.lifespan_context, 'index_cache'):
                    self.ctx.request_context.lifespan_context.index_cache.update(loaded_index_data)
                if hasattr(self.ctx.request_context.lifespan_context, 'file_index'):
                    self.ctx.request_context.lifespan_context.file_index.update(loaded_index_data)

                file_count = loaded_index_data.get('project_metadata', {}).get('total_files', 0)
                self.helper.update_file_count(file_count)

                # Get search capabilities info
                search_tool = project_settings.get_preferred_search_tool()
                search_info = (" Basic search available." if search_tool is None
                             else f" Advanced search enabled ({search_tool.name}).")

                # Step 4: Start new file watcher with retry
                watcher_success = await self._start_new_file_watcher_with_retry()
                
                # Step 5: Record file watcher status
                if not watcher_success:
                    self._record_file_watcher_error("Failed to start file watcher after loading existing index")

                return (f"Project path set to: {abs_path}. "
                        f"Loaded existing index with {file_count} files.{search_info}")
            else:
                print("Old format index detected, will rebuild with new system")

        # Build new index
        try:
            file_count = self._index_project(abs_path, generate_log_file)
        except Exception as e:
            print(f"Error building index: {e}")
            raise ValueError(f"Error building index: {e}") from e

        # Save project config
        config = {
            "base_path": abs_path,
            "supported_extensions": SUPPORTED_EXTENSIONS,
            "last_indexed": project_settings.load_config().get('last_indexed', None),
            "file_watcher": project_settings.get_file_watcher_config()
        }
        project_settings.save_config(config)

        # Get search capabilities info
        search_tool = project_settings.get_preferred_search_tool()
        search_info = (" Basic search available." if search_tool is None
                     else f" Advanced search enabled ({search_tool.name}).")

        # Step 4: Start new file watcher with retry
        watcher_success = await self._start_new_file_watcher_with_retry()
        
        # Step 5: Record file watcher status
        if not watcher_success:
            self._record_file_watcher_error("Failed to start file watcher after building new index")

        return f"Project path set to: {abs_path}. Indexed {file_count} files.{search_info}"

    def get_project_config(self) -> str:
        """
        Get the current project configuration.

        Handles the logic for config://code-indexer MCP resource.

        Returns:
            JSON formatted configuration string

        Raises:
            ValueError: If project is not configured
        """
        # Check if base_path is set
        if not self.base_path:
            config_data = {
                "status": "not_configured",
                "message": ("Project path not set. Please use set_project_path "
                           "to set a project directory first."),
                "supported_extensions": SUPPORTED_EXTENSIONS
            }
            return ResponseFormatter.config_response(config_data)

        # Get settings stats
        settings_stats = self.settings.get_stats() if self.settings else {}

        config_data = {
            "base_path": self.base_path,
            "supported_extensions": SUPPORTED_EXTENSIONS,
            "file_count": self.file_count,
            "settings_directory": self.settings.settings_path if self.settings else "",
            "settings_stats": settings_stats
        }

        return ResponseFormatter.config_response(config_data)

    def get_project_structure(self) -> str:
        """
        Get the project directory structure.

        Handles the logic for structure://project MCP resource.

        Returns:
            JSON formatted project structure

        Raises:
            ValueError: If project is not configured or structure unavailable
        """
        # Check if base_path is set
        if not self.base_path:
            structure_data = {
                "status": "not_configured",
                "message": ("Project path not set. Please use set_project_path "
                           "to set a project directory first.")
            }
            return json.dumps(structure_data, indent=2)

        # Check if we need to refresh the index
        if not self.index_cache:
            self._index_project(self.base_path)

        # Return the directory tree from the index
        if self.index_cache and 'directory_tree' in self.index_cache:
            return json.dumps(self.index_cache['directory_tree'], indent=2)
        else:
            error_data = {"error": "No directory tree available in index"}
            return json.dumps(error_data, indent=2)

    def _index_project(self, base_path: str, generate_log_file: bool = False) -> int:
        """
        Build the project index using the IndexBuilder system.

        Args:
            base_path: The project base path

        Returns:
            Number of files indexed
        """
        print(f"Building index for project: {base_path}")

        # Import here to avoid circular imports
        from ..indexing import IndexBuilder

        builder = IndexBuilder()
        code_index = builder.build_index(base_path, generate_log_file)

        # Convert to dictionary for storage
        index_json = code_index.to_json()
        index_data = json.loads(index_json)

        # Store in cache
        if hasattr(self.ctx.request_context.lifespan_context, 'index_cache'):
            self.ctx.request_context.lifespan_context.index_cache.update(index_data)
        if hasattr(self.ctx.request_context.lifespan_context, 'file_index'):
            self.ctx.request_context.lifespan_context.file_index.update(index_data)

        file_count = code_index.project_metadata.get('total_files', 0)
        self.helper.update_file_count(file_count)

        # Save the index
        if self.settings:
            self.settings.save_index(code_index)

        print(f"Index built successfully with {file_count} files")
        return file_count
