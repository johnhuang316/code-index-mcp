"""
Basic, pure-Python search strategy.
"""
import fnmatch
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pathspec

from .base import SearchStrategy, create_word_boundary_pattern
from ..utils.encoding import read_file_content

class BasicSearchStrategy(SearchStrategy):
    """
    A basic, pure-Python search strategy.

    This strategy iterates through files and lines manually. It's a fallback
    for when no advanced command-line search tools are available.
    It supports literal and fuzzy matching only.
    It does not support context lines or regex mode.
    """

    @property
    def name(self) -> str:
        """The name of the search tool."""
        return 'basic'

    def is_available(self) -> bool:
        """This basic strategy is always available."""
        return True

    def _matches_pattern(self, filename: str, pattern: str) -> bool:
        """Check if filename matches the glob pattern."""
        if not pattern:
            return True
        
        # Handle simple cases efficiently
        if pattern.startswith('*') and not any(c in pattern[1:] for c in '*?[]{}'):
            return filename.endswith(pattern[1:])
        
        # Use fnmatch for more complex patterns
        return fnmatch.fnmatch(filename, pattern)

    def _load_gitignore(self, base_path: str):
        """Load .gitignore from base_path and return a PathSpec, or None if absent."""
        gitignore_path = os.path.join(base_path, '.gitignore')
        if os.path.exists(gitignore_path):
            with open(gitignore_path, 'r') as f:
                return pathspec.PathSpec.from_lines("gitwildmatch", f)
        return None

    def search(
        self,
        pattern: str,
        base_path: str,
        case_sensitive: bool = True,
        context_lines: int = 0,
        file_pattern: Optional[str] = None,
        fuzzy: bool = False,
        regex: bool = False,
        exclude_patterns: Optional[List[str]] = None
    ) -> Dict[str, List[Tuple[int, str]]]:
        """
        Execute a basic, line-by-line search.

        Note: This implementation supports literal and fuzzy matching only.
        It does not support context_lines or regex mode.

        Args:
            pattern: The search pattern
            base_path: Directory to search in
            case_sensitive: Whether search is case sensitive
            context_lines: Number of context lines (not supported)
            file_pattern: File pattern to filter
            fuzzy: Enable word boundary matching
            regex: Request regex matching (rejected for the basic strategy)
        """
        results: Dict[str, List[Tuple[int, str]]] = {}

        if regex:
            raise ValueError(
                "Regex mode requires an external search tool; "
                "basic search only supports literal and fuzzy matching"
            )
        
        flags = 0 if case_sensitive else re.IGNORECASE
        
        try:
            if fuzzy:
                # Use word boundary pattern for partial matching
                search_pattern = create_word_boundary_pattern(pattern)
                search_regex = re.compile(search_pattern, flags)
            else:
                # Use literal string search
                search_regex = re.compile(re.escape(pattern), flags)
        except re.error as e:
            raise ValueError(f"Invalid search pattern: {pattern}, error: {e}")

        spec = self._load_gitignore(base_path)
        user_spec = None
        if exclude_patterns:
            user_spec = pathspec.PathSpec.from_lines("gitwildmatch", exclude_patterns)

        for root, dirs, files in os.walk(base_path):
            # Always skip .git directory
            dirs[:] = [d for d in dirs if d != '.git']

            for file in files:
                if file_pattern and not self._matches_pattern(file, file_pattern):
                    continue

                file_path = Path(root) / file
                rel_path = os.path.relpath(file_path, base_path)

                # Check .gitignore
                if spec and spec.match_file(rel_path):
                    continue

                # Check user excludes
                if user_spec and user_spec.match_file(rel_path):
                    continue

                try:
                    file_content = read_file_content(file_path)
                    for line_num, line in enumerate(file_content.splitlines(), 1):
                        if search_regex.search(line):
                            content = line.rstrip('\n')
                            if rel_path not in results:
                                results[rel_path] = []
                            results[rel_path].append((line_num, content))
                except (UnicodeDecodeError, ValueError, PermissionError, OSError):
                    continue
                except Exception:
                    continue
        
        return results
