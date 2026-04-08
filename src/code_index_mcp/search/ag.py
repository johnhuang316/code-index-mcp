"""
Search Strategy for The Silver Searcher (ag)
"""
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple

from .base import SearchStrategy, parse_search_output, create_word_boundary_pattern

class AgStrategy(SearchStrategy):
    """Search strategy using 'The Silver Searcher' (ag) command-line tool."""

    @property
    def name(self) -> str:
        """The name of the search tool."""
        return 'ag'

    def is_available(self) -> bool:
        """Check if 'ag' command is available on the system."""
        return shutil.which('ag') is not None

    def build_exclude_args(self, exclude_patterns: List[str]) -> List[str]:
        """Build ag --ignore args from a list of exclude patterns."""
        args = []
        for p in exclude_patterns:
            args.extend(['--ignore', p.rstrip('/')])
        return args

    def search(
        self,
        pattern: str,
        base_path: str,
        case_sensitive: bool = True,
        context_lines: int = 0,
        file_pattern: Optional[str] = None,
        fuzzy: bool = False,
        regex: bool = False,
        exclude_patterns: Optional[List[str]] = None,
        encoding: Optional[str] = None
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
        # Note: encoding parameter accepted for interface compatibility.
        # This tool does not support encoding flags; non-UTF-8 content
        # may not be matched correctly.
        # ag prints line numbers and groups by file by default, which is good.
        # --noheading is used to be consistent with other tools' output format.
        cmd = ['ag', '--noheading']

        if not case_sensitive:
            cmd.append('--ignore-case')

        # Prepare search pattern
        if fuzzy:
            # Use word boundary pattern for partial matching
            pattern = create_word_boundary_pattern(pattern)
        elif not regex:
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

        if exclude_patterns:
            cmd.extend(self.build_exclude_args(exclude_patterns))

        # Add -- to treat pattern as a literal argument, preventing injection
        cmd.append('--')
        cmd.append(pattern)
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
