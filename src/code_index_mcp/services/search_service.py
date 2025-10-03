"""
Search service for the Code Index MCP server.

This service handles code search operations, search tool management,
and search strategy selection.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_service import BaseService
from ..utils import FileFilter, ResponseFormatter, ValidationHelper
from ..search.base import is_safe_regex_pattern


class SearchService(BaseService):
    """Service for managing code search operations."""

    def __init__(self, ctx):
        super().__init__(ctx)
        self.file_filter = self._create_file_filter()

    def search_code(  # pylint: disable=too-many-arguments
        self,
        pattern: str,
        case_sensitive: bool = True,
        context_lines: int = 0,
        file_pattern: Optional[str] = None,
        fuzzy: bool = False,
        regex: Optional[bool] = None,
        max_line_length: Optional[int] = None
    ) -> Dict[str, Any]:
        """Search for code patterns in the project."""
        self._require_project_setup()

        if regex is None:
            regex = is_safe_regex_pattern(pattern)

        error = ValidationHelper.validate_search_pattern(pattern, regex)
        if error:
            raise ValueError(error)

        if file_pattern:
            error = ValidationHelper.validate_glob_pattern(file_pattern)
            if error:
                raise ValueError(f"Invalid file pattern: {error}")

        if not self.settings:
            raise ValueError("Settings not available")

        strategy = self.settings.get_preferred_search_tool()
        if not strategy:
            raise ValueError("No search strategies available")

        self._configure_strategy(strategy)

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
            filtered = self._filter_results(results)
            return ResponseFormatter.search_results_response(filtered)
        except Exception as exc:
            raise ValueError(f"Search failed using '{strategy.name}': {exc}") from exc

    def refresh_search_tools(self) -> str:
        """Refresh the available search tools."""
        if not self.settings:
            raise ValueError("Settings not available")

        self.settings.refresh_available_strategies()
        config = self.settings.get_search_tools_config()

        available = config['available_tools']
        preferred = config['preferred_tool']
        return f"Search tools refreshed. Available: {available}. Preferred: {preferred}."

    def get_search_capabilities(self) -> Dict[str, Any]:
        """Get information about search capabilities and available tools."""
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

    def _configure_strategy(self, strategy) -> None:
        """Apply shared exclusion configuration to the strategy if supported."""
        configure = getattr(strategy, 'configure_excludes', None)
        if not configure:
            return

        try:
            configure(self.file_filter)
        except Exception:  # pragma: no cover - defensive fallback
            pass

    def _create_file_filter(self) -> FileFilter:
        """Build a shared file filter drawing from project settings."""
        additional_dirs: List[str] = []
        additional_file_patterns: List[str] = []

        settings = self.settings
        if settings:
            try:
                config = settings.get_file_watcher_config()
            except Exception:  # pragma: no cover - fallback if config fails
                config = {}

            for key in ('exclude_patterns', 'additional_exclude_patterns'):
                patterns = config.get(key) or []
                for pattern in patterns:
                    if not isinstance(pattern, str):
                        continue
                    normalized = pattern.strip()
                    if not normalized:
                        continue
                    additional_dirs.append(normalized)
                    additional_file_patterns.append(normalized)

        file_filter = FileFilter(additional_dirs or None)

        if additional_file_patterns:
            file_filter.exclude_files.update(additional_file_patterns)

        return file_filter

    def _filter_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Filter out matches that reside under excluded paths."""
        if not isinstance(results, dict) or not results:
            return results

        if 'error' in results or not self.file_filter or not self.base_path:
            return results

        base_path = Path(self.base_path)
        filtered: Dict[str, Any] = {}

        for rel_path, matches in results.items():
            if not isinstance(rel_path, str):
                continue

            normalized = Path(rel_path.replace('\\', '/'))
            try:
                absolute = (base_path / normalized).resolve()
            except Exception:  # pragma: no cover - invalid path safety
                continue

            try:
                if self.file_filter.should_process_path(absolute, base_path):
                    filtered[rel_path] = matches
            except Exception:  # pragma: no cover - defensive fallback
                continue

        return filtered
