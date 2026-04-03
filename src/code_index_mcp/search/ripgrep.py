"""
Search Strategy for ripgrep
"""
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple

from .base import SearchStrategy, parse_search_output, create_word_boundary_pattern

class RipgrepStrategy(SearchStrategy):
    """Search strategy using the 'ripgrep' (rg) command-line tool."""

    @property
    def name(self) -> str:
        """The name of the search tool."""
        return 'ripgrep'

    def is_available(self) -> bool:
        """Check if 'rg' command is available on the system."""
        return shutil.which('rg') is not None

    def build_exclude_args(self, exclude_patterns: list[str]) -> list[str]:
        """Translate user-configured exclude patterns into ripgrep --glob arguments.

        Args:
            exclude_patterns: User-configured patterns to exclude.

        Returns:
            List of CLI arguments for ripgrep.
        """
        args = []
        for p in exclude_patterns:
            args.extend(['--glob', f'!{p}'])
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
        exclude_patterns: list[str] | None = None
    ) -> Dict[str, List[Tuple[int, str]]]:
        """
        Execute a search using ripgrep.

        Args:
            pattern: The search pattern
            base_path: Directory to search in
            case_sensitive: Whether search is case sensitive
            context_lines: Number of context lines to show
            file_pattern: File pattern to filter
            fuzzy: Enable word boundary matching (not true fuzzy search)
            regex: Enable regex pattern matching
            exclude_patterns: Additional glob patterns to exclude (e.g. ["logs/", "*.generated.ts"])
        """
        cmd = ['rg', '--line-number', '--no-heading', '--color=never']

        if not case_sensitive:
            cmd.append('--ignore-case')

        if fuzzy:
            # Use word boundary pattern for partial matching
            pattern = create_word_boundary_pattern(pattern)
        elif not regex:
            # Use literal string search
            cmd.append('--fixed-strings')

        if context_lines > 0:
            cmd.extend(['--context', str(context_lines)])

        if file_pattern:
            cmd.extend(['--glob', file_pattern])

        if exclude_patterns:
            cmd.extend(self.build_exclude_args(exclude_patterns))

        # Add -- to treat pattern as a literal argument, preventing injection
        cmd.append('--')
        cmd.append(pattern)
        cmd.append('.')  # Use current directory since we set cwd=base_path

        try:
            # ripgrep exits with 1 if no matches are found, which is not an error.
            # It exits with 2 for actual errors.
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=False,  # Do not raise CalledProcessError on non-zero exit
                cwd=base_path  # Set working directory to project base path for proper glob resolution
            )
            if process.returncode > 1:
                raise RuntimeError(f"ripgrep failed with exit code {process.returncode}: {process.stderr}")

            return parse_search_output(process.stdout, base_path)

        except FileNotFoundError:
            raise RuntimeError("ripgrep (rg) not found. Please install it and ensure it's in your PATH.")
        except Exception as e:
            # Re-raise other potential exceptions like permission errors
            raise RuntimeError(f"An error occurred while running ripgrep: {e}")
