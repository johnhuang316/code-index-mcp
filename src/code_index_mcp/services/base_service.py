"""
Base service class providing common functionality for all services.

This module defines the base service pattern that all domain services inherit from,
ensuring consistent behavior and shared functionality across the service layer.
"""

from abc import ABC
from typing import Optional
from fastmcp import Context

from ..utils import ContextHelper, ValidationHelper


class BaseService(ABC):
    """
    Base class for all MCP services.

    This class provides common functionality that all services need:
    - Context management through ContextHelper
    - Common validation patterns
    - Shared error checking methods

    All domain services should inherit from this class to ensure
    consistent behavior and access to shared utilities.
    """

    def __init__(self, ctx: Context):
        """
        Initialize the base service.

        Args:
            ctx: The MCP Context object containing request and lifespan context
        """
        self.ctx = ctx
        self.helper = ContextHelper(ctx)

    def _validate_project_setup(self) -> Optional[str]:
        """
        Validate that the project is properly set up.

        This method checks if the base path is set and valid, which is
        required for most operations.

        Returns:
            Error message if project is not set up properly, None if valid
        """
        return self.helper.get_base_path_error()

    def _require_project_setup(self) -> None:
        """
        Ensure project is set up, raising an exception if not.

        This is a convenience method for operations that absolutely
        require a valid project setup.

        Raises:
            ValueError: If project is not properly set up
        """
        error = self._validate_project_setup()
        if error:
            raise ValueError(error)

    def _validate_file_path(self, file_path: str) -> Optional[str]:
        """
        Validate a file path for security and accessibility.

        Args:
            file_path: The file path to validate

        Returns:
            Error message if validation fails, None if valid
        """
        return ValidationHelper.validate_file_path(file_path, self.helper.base_path)

    def _require_valid_file_path(self, file_path: str) -> None:
        """
        Ensure file path is valid, raising an exception if not.

        Args:
            file_path: The file path to validate

        Raises:
            ValueError: If file path is invalid
        """
        error = self._validate_file_path(file_path)
        if error:
            raise ValueError(error)

    @property
    def base_path(self) -> str:
        """
        Convenient access to the base project path.

        Returns:
            The base project path
        """
        return self.helper.base_path

    @property
    def settings(self):
        """
        Convenient access to the project settings.

        Returns:
            The ProjectSettings instance
        """
        return self.helper.settings

    @property
    def file_count(self) -> int:
        """
        Convenient access to the current file count.

        Returns:
            The number of indexed files
        """
        return self.helper.file_count

    @property
    def index_provider(self):
        """
        Convenient access to the unified index provider.

        Returns:
            The current IIndexProvider instance, or None if not available
        """
        if self.helper.index_manager:
            return self.helper.index_manager.get_provider()
        return None
    
    @property
    def index_manager(self):
        """
        Convenient access to the index manager.

        Returns:
            The index manager instance, or None if not available
        """
        return self.helper.index_manager
