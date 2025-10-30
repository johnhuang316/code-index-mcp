"""
Search Strategies for Code Indexer

This module defines the abstract base class for search strategies and will contain
concrete implementations for different search tools like ugrep, ripgrep, etc.
"""
import os
import re
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from ..indexing.qualified_names import normalize_file_path

if TYPE_CHECKING:  # pragma: no cover
    from ..utils.file_filter import FileFilter

def parse_search_output(
    output: str,
    base_path: str
) -> Dict[str, List[Tuple[int, str]]]:
    """
    Parse the output of command-line search tools (grep, ag, rg).

    Args:
        output: The raw output from the command-line tool.
        base_path: The base path of the project to make file paths relative.

    Returns:
        A dictionary where keys are file paths and values are lists of (line_number, line_content) tuples.
    """
    results = {}
    # Normalize base_path to ensure consistent path separation
    normalized_base_path = os.path.normpath(base_path)

    for line in output.strip().split('\n'):
        if not line.strip():
            continue
        try:
            # Try to parse as a matched line first (format: path:linenum:content)
            parts = line.split(':', 2)
            
            # Check if this might be a context line (format: path-linenum-content)
            # Context lines use '-' as separator in grep/ag output
            if len(parts) < 3 and '-' in line:
                # Try to parse as context line
                # Match pattern: path-linenum-content or path-linenum-\tcontent
                match = re.match(r'^(.*?)-(\d+)[-\t](.*)$', line)
                if match:
                    file_path_abs = match.group(1)
                    line_number_str = match.group(2)
                    content = match.group(3)
                else:
                    # If regex doesn't match, skip this line
                    continue
            elif sys.platform == "win32" and len(parts) >= 3 and len(parts[0]) == 1 and parts[1].startswith('\\'):
                # Handle Windows paths with drive letter (e.g., C:\path\file.txt)
                file_path_abs = f"{parts[0]}:{parts[1]}"
                line_number_str = parts[2].split(':', 1)[0]
                content = parts[2].split(':', 1)[1] if ':' in parts[2] else parts[2]
            elif len(parts) >= 3:
                # Standard format: path:linenum:content
                file_path_abs = parts[0]
                line_number_str = parts[1]
                content = parts[2]
            else:
                # Line doesn't match any expected format
                continue
            
            line_number = int(line_number_str)

            # If the path is already relative (doesn't start with /), keep it as is
            # Otherwise, make it relative to the base_path
            if os.path.isabs(file_path_abs):
                relative_path = os.path.relpath(file_path_abs, normalized_base_path)
            else:
                # Path is already relative, use it as is
                relative_path = file_path_abs
            
            # Normalize path separators for consistency
            relative_path = normalize_file_path(relative_path)

            if relative_path not in results:
                results[relative_path] = []
            results[relative_path].append((line_number, content))
        except (ValueError, IndexError):
            # Silently ignore lines that don't match the expected format
            # This can happen with summary lines or other tool-specific output
            pass

    return results


def create_word_boundary_pattern(pattern: str) -> str:
    """
    Create word boundary patterns for partial matching.
    This is NOT true fuzzy search, but allows matching words at boundaries.
    
    Args:
        pattern: Original search pattern
        
    Returns:
        Word boundary pattern for regex matching
    """
    # Escape any regex special characters to make them literal
    escaped = re.escape(pattern)
    
    # Create word boundary pattern that matches:
    # 1. Word at start of word boundary (e.g., "test" in "testing")
    # 2. Word at end of word boundary (e.g., "test" in "mytest") 
    # 3. Whole word (e.g., "test" as standalone word)
    if len(pattern) >= 3:  # Only for patterns of reasonable length
        # This pattern allows partial matches at word boundaries
        boundary_pattern = f"\\b{escaped}|{escaped}\\b"
    else:
        # For short patterns, require full word boundaries to avoid too many matches
        boundary_pattern = f"\\b{escaped}\\b"
    
    return boundary_pattern


def is_safe_regex_pattern(pattern: str) -> bool:
    """
    Check if a pattern appears to be a safe regex pattern.
    
    Args:
        pattern: The search pattern to check
        
    Returns:
        True if the pattern looks like a safe regex, False otherwise
    """
    # Strong indicators of regex intent
    strong_regex_indicators = ['|', '(', ')', '[', ']', '^', '$']
    
    # Weaker indicators that need context
    weak_regex_indicators = ['.', '*', '+', '?']
    
    # Check for strong regex indicators
    has_strong_regex = any(char in pattern for char in strong_regex_indicators)
    
    # Check for weak indicators with context
    has_weak_regex = any(char in pattern for char in weak_regex_indicators)
    
    # If has strong indicators, likely regex
    if has_strong_regex:
        # Still check for dangerous patterns
        dangerous_patterns = [
            r'(.+)+',  # Nested quantifiers
            r'(.*)*',  # Nested stars
            r'(.{0,})+',  # Potential ReDoS patterns
        ]
        
        has_dangerous_patterns = any(dangerous in pattern for dangerous in dangerous_patterns)
        return not has_dangerous_patterns
    
    # If only weak indicators, need more context
    if has_weak_regex:
        # Patterns like ".*", ".+", "file.*py" look like regex
        # But "file.txt", "test.py" look like literal filenames
        regex_like_patterns = [
            r'\.\*',  # .*
            r'\.\+',  # .+
            r'\.\w*\*',  # .something*
            r'\*\.',  # *.
            r'\w+\.\*\w*',  # word.*word
        ]
        
        return any(re.search(regex_pattern, pattern) for regex_pattern in regex_like_patterns)
    
    return False


class SearchStrategy(ABC):
    """
    Abstract base class for a search strategy.
    
    Each strategy is responsible for searching code using a specific tool or method.
    """

    def configure_excludes(self, file_filter: Optional['FileFilter']) -> None:
        """Configure shared exclusion settings for the strategy."""
        self.file_filter = file_filter
        if file_filter:
            self.exclude_dirs = sorted(set(file_filter.exclude_dirs))
            self.exclude_file_patterns = sorted(set(file_filter.exclude_files))
        else:
            self.exclude_dirs = []
            self.exclude_file_patterns = []

    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the search tool (e.g., 'ugrep', 'ripgrep')."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the search tool for this strategy is available on the system.
        
        Returns:
            True if the tool is available, False otherwise.
        """
        pass

    @abstractmethod
    def search(
        self,
        pattern: str,
        base_path: str,
        case_sensitive: bool = True,
        context_lines: int = 0,
        file_pattern: Optional[str] = None,
        fuzzy: bool = False,
        regex: bool = False
    ) -> Dict[str, List[Tuple[int, str]]]:
        """
        Execute a search using the specific strategy.

        Args:
            pattern: The search pattern.
            base_path: The root directory to search in.
            case_sensitive: Whether the search is case-sensitive.
            context_lines: Number of context lines to show around each match.
            file_pattern: Glob pattern to filter files (e.g., "*.py").
            fuzzy: Whether to enable fuzzy/partial matching.
            regex: Whether to enable regex pattern matching.

        Returns:
            A dictionary mapping filenames to lists of (line_number, line_content) tuples.
        """
        pass
