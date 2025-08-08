"""
Search service for the Code Index MCP server.

This service handles code search operations, search tool management,
and search strategy selection.
"""

from typing import Dict, Any, Optional

from .base_service import BaseService
from ..utils import ValidationHelper, ResponseFormatter
from ..search.base import is_safe_regex_pattern


class SearchService(BaseService):
    """
    Service for managing code search operations.

    This service handles:
    - Code search with various parameters and options
    - Search tool management and detection
    - Search strategy selection and optimization
    - Search capabilities reporting
    """

    
    def search_code(  # pylint: disable=too-many-arguments
        self,
        pattern: str,
        case_sensitive: bool = True,
        context_lines: int = 0,
        file_pattern: Optional[str] = None,
        fuzzy: bool = False,
        regex: Optional[bool] = None,
        max_line_length: Optional[int] = 200
    ) -> Dict[str, Any]:
        """
        Search for code patterns in the project.

        Handles the logic for search_code_advanced MCP tool.

        Args:
            pattern: The search pattern
            case_sensitive: Whether search should be case-sensitive
            context_lines: Number of context lines to show
            file_pattern: Glob pattern to filter files
            fuzzy: Whether to enable fuzzy matching
            regex: Regex mode - True/False to force, None for auto-detection
            max_line_length: Optional. Default 200. Limits the length of lines when context_lines is used.

        Returns:
            Dictionary with search results or error information

        Raises:
            ValueError: If project is not set up or search parameters are invalid
        """
        self._require_project_setup()

        # Smart regex detection if regex parameter is None
        if regex is None:
            regex = is_safe_regex_pattern(pattern)
            if regex:
                print(f"Auto-detected regex pattern: {pattern}")

        # Validate search pattern
        error = ValidationHelper.validate_search_pattern(pattern, regex)
        if error:
            raise ValueError(error)

        # Validate file pattern if provided
        if file_pattern:
            error = ValidationHelper.validate_glob_pattern(file_pattern)
            if error:
                raise ValueError(f"Invalid file pattern: {error}")

        # Get search strategy from settings
        if not self.settings:
            raise ValueError("Settings not available")

        strategy = self.settings.get_preferred_search_tool()
        if not strategy:
            raise ValueError("No search strategies available")

        print(f"Using search strategy: {strategy.name}")

        try:
            results = strategy.search(
                pattern=pattern,
                base_path=self.base_path,
                case_sensitive=case_sensitive,
                context_lines=context_lines,
                file_pattern=file_pattern,
                fuzzy=fuzzy,
                regex=regex,
                max_line_length=max_line_length
            )
            return ResponseFormatter.search_results_response(results)
        except Exception as e:
            raise ValueError(f"Search failed using '{strategy.name}': {e}") from e

    
    def refresh_search_tools(self) -> str:
        """
        Refresh the available search tools.

        Handles the logic for refresh_search_tools MCP tool.

        Returns:
            Success message with available tools information

        Raises:
            ValueError: If refresh operation fails
        """
        if not self.settings:
            raise ValueError("Settings not available")

        self.settings.refresh_available_strategies()
        config = self.settings.get_search_tools_config()

        available = config['available_tools']
        preferred = config['preferred_tool']
        return f"Search tools refreshed. Available: {available}. Preferred: {preferred}."

    
    def get_search_capabilities(self) -> Dict[str, Any]:
        """
        Get information about search capabilities and available tools.

        Returns:
            Dictionary with search tool information and capabilities
        """
        if not self.settings:
            return {"error": "Settings not available"}

        config = self.settings.get_search_tools_config()

        capabilities = {
            "available_tools": config.get('available_tools', []),
            "preferred_tool": config.get('preferred_tool', 'basic'),
            "supports_regex": True,
            "supports_fuzzy": True,
            "supports_case_sensitivity": True,
            "supports_context_lines": True,
            "supports_file_patterns": True
        }

        return capabilities
