"""
Search Strategy for ripgrep
"""
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple

from .base import SearchStrategy, parse_search_output, create_word_boundary_pattern, is_safe_regex_pattern

class RipgrepStrategy(SearchStrategy):
    """Search strategy using the 'ripgrep' (rg) command-line tool."""

    @property
    def name(self) -> str:
        """The name of the search tool."""
        return 'ripgrep'

    def is_available(self) -> bool:
        """Check if 'rg' command is available on the system."""
        return shutil.which('rg') is not None

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
        Execute a search using ripgrep.
        
        Args:
            pattern: The search pattern
            base_path: Directory to search in
            case_sensitive: Whether search is case sensitive
            context_lines: Number of context lines to show
            file_pattern: File pattern to filter
            fuzzy: Enable word boundary matching (not true fuzzy search)
            regex: Enable regex pattern matching
        """
        cmd = ['rg', '--line-number', '--no-heading', '--color=never', '--no-ignore']

        if not case_sensitive:
            cmd.append('--ignore-case')

        # Prepare search pattern
        search_pattern = pattern
        
        if regex:
            # Use regex mode - check for safety first
            if not is_safe_regex_pattern(pattern):
                raise ValueError(f"Potentially unsafe regex pattern: {pattern}")
            # Don't add --fixed-strings, use regex mode
        elif fuzzy:
            # Use word boundary pattern for partial matching
            search_pattern = create_word_boundary_pattern(pattern)
        else:
            # Use literal string search
            cmd.append('--fixed-strings')

        if context_lines > 0:
            cmd.extend(['--context', str(context_lines)])
            
        if file_pattern:
            cmd.extend(['--glob', file_pattern])

        exclude_dirs = getattr(self, 'exclude_dirs', [])
        exclude_file_patterns = getattr(self, 'exclude_file_patterns', [])

        processed_patterns = set()

        for directory in exclude_dirs:
            normalized = directory.strip()
            if not normalized or normalized in processed_patterns:
                continue
            cmd.extend(['--glob', f'!**/{normalized}/**'])
            processed_patterns.add(normalized)

        for pattern in exclude_file_patterns:
            normalized = pattern.strip()
            if not normalized or normalized in processed_patterns:
                continue
            if normalized.startswith('!'):
                glob_pattern = normalized
            elif any(ch in normalized for ch in '*?[') or '/' in normalized:
                glob_pattern = f'!{normalized}'
            else:
                glob_pattern = f'!**/{normalized}'
            cmd.extend(['--glob', glob_pattern])
            processed_patterns.add(normalized)

        # Add -- to treat pattern as a literal argument, preventing injection
        cmd.append('--')
        cmd.append(search_pattern)
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
