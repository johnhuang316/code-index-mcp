"""
Search Strategy for ugrep
"""
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple

from .base import SearchStrategy, parse_search_output, create_word_boundary_pattern, is_safe_regex_pattern

class UgrepStrategy(SearchStrategy):
    """Search strategy using the 'ugrep' (ug) command-line tool."""

    @property
    def name(self) -> str:
        """The name of the search tool."""
        return 'ugrep'

    def is_available(self) -> bool:
        """Check if 'ug' command is available on the system."""
        return shutil.which('ug') is not None

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
        Execute a search using the 'ug' command-line tool.
        
        Args:
            pattern: The search pattern
            base_path: Directory to search in
            case_sensitive: Whether search is case sensitive
            context_lines: Number of context lines to show
            file_pattern: File pattern to filter
            fuzzy: Enable true fuzzy search (ugrep native support)
            regex: Enable regex pattern matching
        """
        if not self.is_available():
            return {"error": "ugrep (ug) command not found."}

        cmd = ['ug', '-r', '--line-number', '--no-heading']

        if fuzzy:
            # ugrep has native fuzzy search support
            cmd.append('--fuzzy')
        elif regex:
            # Use regex mode - check for safety first
            if not is_safe_regex_pattern(pattern):
                raise ValueError(f"Potentially unsafe regex pattern: {pattern}")
            # Don't add --fixed-strings, use regex mode
        else:
            # Use literal string search
            cmd.append('--fixed-strings')

        if not case_sensitive:
            cmd.append('--ignore-case')
        
        if context_lines > 0:
            cmd.extend(['-A', str(context_lines), '-B', str(context_lines)])
            
        if file_pattern:
            cmd.extend(['--include', file_pattern])

        processed_patterns = set()
        exclude_dirs = getattr(self, 'exclude_dirs', [])
        exclude_file_patterns = getattr(self, 'exclude_file_patterns', [])

        for directory in exclude_dirs:
            normalized = directory.strip()
            if not normalized or normalized in processed_patterns:
                continue
            cmd.extend(['--ignore', f'**/{normalized}/**'])
            processed_patterns.add(normalized)

        for pattern in exclude_file_patterns:
            normalized = pattern.strip()
            if not normalized or normalized in processed_patterns:
                continue
            if normalized.startswith('!'):
                ignore_pattern = normalized[1:]
            elif any(ch in normalized for ch in '*?[') or '/' in normalized:
                ignore_pattern = normalized
            else:
                ignore_pattern = f'**/{normalized}'
            cmd.extend(['--ignore', ignore_pattern])
            processed_patterns.add(normalized)

        # Add '--' to treat pattern as a literal argument, preventing injection
        cmd.append('--')
        cmd.append(pattern)
        cmd.append('.')  # Use current directory since we set cwd=base_path

        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore', # Ignore decoding errors for binary-like content
                check=False,  # Do not raise exception on non-zero exit codes
                cwd=base_path  # Set working directory to project base path for proper pattern resolution
            )
            
            # ugrep exits with 1 if no matches are found, which is not an error for us.
            # It exits with 2 for actual errors.
            if process.returncode > 1:
                error_output = process.stderr.strip()
                return {"error": f"ugrep execution failed with code {process.returncode}", "details": error_output}

            return parse_search_output(process.stdout, base_path)

        except FileNotFoundError:
            return {"error": "ugrep (ug) command not found. Please ensure it's installed and in your PATH."}
        except Exception as e:
            return {"error": f"An unexpected error occurred during search: {str(e)}"}
