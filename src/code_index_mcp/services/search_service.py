"""
Search service for the Code Index MCP server.

This service handles code search operations, search tool management,
and search strategy selection.
"""

from typing import Any, Dict, List, Optional, Tuple

from .base_service import BaseService
from ..utils import ResponseFormatter, ValidationHelper


class SearchService(BaseService):
    """Service for managing code search operations."""

    def __init__(self, ctx):
        super().__init__(ctx)
        self.additional_exclude_patterns = self._load_exclude_patterns()

    def search_code(  # pylint: disable=too-many-arguments, too-many-locals
        self,
        pattern: str,
        case_sensitive: bool = True,
        context_lines: int = 0,
        file_pattern: Optional[str] = None,
        fuzzy: bool = False,
        regex: Optional[bool] = None,
        start_index: int = 0,
        max_results: Optional[int] = 10
    ) -> Dict[str, Any]:
        """Search for code patterns in the project."""
        self._require_project_setup()

        if regex is None:
            regex = False

        error = ValidationHelper.validate_search_pattern(pattern, regex)
        if error:
            raise ValueError(error)

        if file_pattern:
            error = ValidationHelper.validate_glob_pattern(file_pattern)
            if error:
                raise ValueError(f"Invalid file pattern: {error}")

        pagination_error = ValidationHelper.validate_pagination(start_index, max_results)
        if pagination_error:
            raise ValueError(pagination_error)

        if not self.settings:
            raise ValueError("Settings not available")

        strategy = self.settings.get_preferred_search_tool()
        if not strategy:
            raise ValueError("No search strategies available")

        if regex and getattr(strategy, 'name', '').lower() == 'basic':
            raise ValueError(
                "Regex mode requires an external search tool; "
                "basic search only supports literal and fuzzy matching"
            )

        try:
            results = strategy.search(
                pattern=pattern,
                base_path=self.base_path,
                case_sensitive=case_sensitive,
                context_lines=context_lines,
                file_pattern=file_pattern,
                fuzzy=fuzzy,
                regex=regex,
                exclude_patterns=self.additional_exclude_patterns
            )
            formatted_results, pagination = self._paginate_results(
                results,
                start_index=start_index,
                max_results=max_results
            )
            return ResponseFormatter.search_results_response(
                formatted_results,
                pagination
            )
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
        available_tools = config.get('available_tools', [])
        supports_regex = any(tool.lower() != 'basic' for tool in available_tools)

        capabilities = {
            "available_tools": available_tools,
            "preferred_tool": config.get('preferred_tool', 'basic'),
            "supports_regex": supports_regex,
            "supports_fuzzy": True,
            "supports_case_sensitivity": True,
            "supports_context_lines": True,
            "supports_file_patterns": True
        }

        return capabilities

    def _load_exclude_patterns(self) -> list:
        """Load user-configured exclude patterns from project settings."""
        try:
            config = self.settings.load_config()
            # New location (project-level)
            patterns = config.get("additional_exclude_patterns", [])
            # Backward compat: check old location
            if not patterns:
                fw_config = config.get("file_watcher", {})
                patterns = fw_config.get("additional_exclude_patterns", [])
            return patterns if isinstance(patterns, list) else []
        except Exception:
            return []

    def _paginate_results(
        self,
        results: Dict[str, Any],
        start_index: int,
        max_results: Optional[int]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Apply pagination to search results and format them for responses."""
        total_matches = 0
        for matches in results.values():
            if isinstance(matches, (list, tuple)):
                total_matches += len(matches)

        effective_start = min(max(start_index, 0), total_matches)

        if total_matches == 0 or effective_start >= total_matches:
            pagination = self._build_pagination_metadata(
                total_matches=total_matches,
                returned=0,
                start_index=effective_start,
                max_results=max_results
            )
            return [], pagination

        collected: List[Dict[str, Any]] = []
        current_index = 0

        sorted_items = sorted(
            (
                (path, matches)
                for path, matches in results.items()
                if isinstance(path, str) and isinstance(matches, (list, tuple))
            ),
            key=lambda item: item[0]
        )

        for path, matches in sorted_items:
            sorted_matches = sorted(
                (match for match in matches if isinstance(match, (list, tuple)) and len(match) >= 2),
                key=lambda pair: pair[0]
            )

            for line_number, content, *_ in sorted_matches:
                if current_index >= effective_start:
                    if max_results is None or len(collected) < max_results:
                        collected.append({
                            "file": path,
                            "line": line_number,
                            "text": content
                        })
                    else:
                        break
                current_index += 1
            if max_results is not None and len(collected) >= max_results:
                break

        pagination = self._build_pagination_metadata(
            total_matches=total_matches,
            returned=len(collected),
            start_index=effective_start,
            max_results=max_results
        )
        return collected, pagination

    @staticmethod
    def _build_pagination_metadata(
        total_matches: int,
        returned: int,
        start_index: int,
        max_results: Optional[int]
    ) -> Dict[str, Any]:
        """Construct pagination metadata for search responses."""
        end_index = start_index + returned
        metadata: Dict[str, Any] = {
            "total_matches": total_matches,
            "returned": returned,
            "start_index": start_index,
            "has_more": end_index < total_matches
        }

        if max_results is not None:
            metadata["max_results"] = max_results

        metadata["end_index"] = end_index
        return metadata
