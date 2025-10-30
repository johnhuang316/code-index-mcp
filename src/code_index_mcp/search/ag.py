"""
Search Strategy for The Silver Searcher (ag)
"""
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple

from .base import SearchStrategy, parse_search_output, create_word_boundary_pattern, is_safe_regex_pattern

class AgStrategy(SearchStrategy):
    """Search strategy using 'The Silver Searcher' (ag) command-line tool."""

    @property
    def name(self) -> str:
        """The name of the search tool."""
        return 'ag'

    def is_available(self) -> bool:
        """Check if 'ag' command is available on the system."""
        return shutil.which('ag') is not None

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
        Execute a search using The Silver Searcher (ag).

        Args:
            pattern: The search pattern
            base_path: Directory to search in
            case_sensitive: Whether search is case sensitive
            context_lines: Number of context lines to show
            file_pattern: File pattern to filter
            fuzzy: Enable word boundary matching (not true fuzzy search)
            regex: Enable regex pattern matching
        """
        # ag prints line numbers and groups by file by default, which is good.
        # --noheading is used to be consistent with other tools' output format.
        cmd = ['ag', '--noheading']

        if not case_sensitive:
            cmd.append('--ignore-case')

        # Prepare search pattern
        search_pattern = pattern
        
        if regex:
            # Use regex mode - check for safety first
            if not is_safe_regex_pattern(pattern):
                raise ValueError(f"Potentially unsafe regex pattern: {pattern}")
            # Don't add --literal, use regex mode
        elif fuzzy:
            # Use word boundary pattern for partial matching
            search_pattern = create_word_boundary_pattern(pattern)
        else:
            # Use literal string search
            cmd.append('--literal')

        if context_lines > 0:
            cmd.extend(['--before', str(context_lines)])
            cmd.extend(['--after', str(context_lines)])
            
        if file_pattern:
            # Convert glob pattern to regex pattern for ag's -G parameter
            # ag's -G expects regex, not glob patterns
            regex_pattern = file_pattern
            if '*' in file_pattern and not file_pattern.startswith('^') and not file_pattern.endswith('$'):
                # Convert common glob patterns to regex
                if file_pattern.startswith('*.'):
                    # Pattern like "*.py" -> "\.py$"
                    extension = file_pattern[2:]  # Remove "*."
                    regex_pattern = f'\\.{extension}$'
                elif file_pattern.endswith('*'):
                    # Pattern like "test_*" -> "^test_.*"
                    prefix = file_pattern[:-1]  # Remove "*"
                    regex_pattern = f'^{prefix}.*'
                elif '*' in file_pattern:
                    # Pattern like "test_*.py" -> "^test_.*\.py$"
                    # First escape dots, then replace * with .*
                    regex_pattern = file_pattern.replace('.', '\\.')
                    regex_pattern = regex_pattern.replace('*', '.*')
                    if not regex_pattern.startswith('^'):
                        regex_pattern = '^' + regex_pattern
                    if not regex_pattern.endswith('$'):
                        regex_pattern = regex_pattern + '$'
            
            cmd.extend(['-G', regex_pattern])

        processed_patterns = set()
        exclude_dirs = getattr(self, 'exclude_dirs', [])
        exclude_file_patterns = getattr(self, 'exclude_file_patterns', [])

        for directory in exclude_dirs:
            normalized = directory.strip()
            if not normalized or normalized in processed_patterns:
                continue
            cmd.extend(['--ignore', normalized])
            processed_patterns.add(normalized)

        for pattern in exclude_file_patterns:
            normalized = pattern.strip()
            if not normalized or normalized in processed_patterns:
                continue
            if normalized.startswith('!'):
                normalized = normalized[1:]
            cmd.extend(['--ignore', normalized])
            processed_patterns.add(normalized)

        # Add -- to treat pattern as a literal argument, preventing injection
        cmd.append('--')
        cmd.append(search_pattern)
        cmd.append('.')  # Use current directory since we set cwd=base_path
        
        try:
            # ag exits with 1 if no matches are found, which is not an error.
            # It exits with 0 on success (match found). Other codes are errors.
            process = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8',
                errors='replace',
                check=False,  # Do not raise CalledProcessError on non-zero exit
                cwd=base_path  # Set working directory to project base path for proper pattern resolution
            )
            # We don't check returncode > 1 because ag's exit code behavior
            # is less standardized than rg/ug. 0 for match, 1 for no match.
            # Any actual error will likely raise an exception or be in stderr.
            if process.returncode > 1:
                 raise RuntimeError(f"ag failed with exit code {process.returncode}: {process.stderr}")

            return parse_search_output(process.stdout, base_path)
        
        except FileNotFoundError:
            raise RuntimeError("'ag' (The Silver Searcher) not found. Please install it and ensure it's in your PATH.")
        except Exception as e:
            # Re-raise other potential exceptions like permission errors
            raise RuntimeError(f"An error occurred while running ag: {e}")
