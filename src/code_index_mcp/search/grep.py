"""
Search Strategy for standard grep
"""
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple

from .base import SearchStrategy, parse_search_output, create_word_boundary_pattern, is_safe_regex_pattern

class GrepStrategy(SearchStrategy):
    """
    Search strategy using the standard 'grep' command-line tool.
    
    This is intended as a fallback for when more advanced tools like
    ugrep, ripgrep, or ag are not available.
    """

    @property
    def name(self) -> str:
        """The name of the search tool."""
        return 'grep'

    def is_available(self) -> bool:
        """Check if 'grep' command is available on the system."""
        return shutil.which('grep') is not None

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
        Execute a search using standard grep.

        Args:
            pattern: The search pattern
            base_path: Directory to search in
            case_sensitive: Whether search is case sensitive
            context_lines: Number of context lines to show
            file_pattern: File pattern to filter
            fuzzy: Enable word boundary matching
            regex: Enable regex pattern matching
        """
        # -r: recursive, -n: line number
        cmd = ['grep', '-r', '-n']

        # Prepare search pattern
        search_pattern = pattern
        
        if regex:
            # Use regex mode - check for safety first
            if not is_safe_regex_pattern(pattern):
                raise ValueError(f"Potentially unsafe regex pattern: {pattern}")
            cmd.append('-E')  # Extended Regular Expressions
        elif fuzzy:
            # Use word boundary pattern for partial matching
            search_pattern = create_word_boundary_pattern(pattern)
            cmd.append('-E')  # Extended Regular Expressions
        else:
            # Auto-detect if pattern looks like a safe regex
            if is_safe_regex_pattern(pattern):
                # Pattern contains regex chars, use extended regex mode
                cmd.append('-E')
            else:
                # Use literal string search
                cmd.append('-F')

        if not case_sensitive:
            cmd.append('-i')

        if context_lines > 0:
            cmd.extend(['-A', str(context_lines)])
            cmd.extend(['-B', str(context_lines)])
            
        if file_pattern:
            # Note: grep's --include uses glob patterns, not regex
            cmd.append(f'--include={file_pattern}')

        exclude_dirs = getattr(self, 'exclude_dirs', [])
        exclude_file_patterns = getattr(self, 'exclude_file_patterns', [])

        processed_dirs = set()
        for directory in exclude_dirs:
            normalized = directory.strip()
            if not normalized or normalized in processed_dirs:
                continue
            cmd.append(f'--exclude-dir={normalized}')
            processed_dirs.add(normalized)

        processed_files = set()
        for pattern in exclude_file_patterns:
            normalized = pattern.strip()
            if not normalized or normalized in processed_files:
                continue
            if normalized.startswith('!'):
                normalized = normalized[1:]
            cmd.append(f'--exclude={normalized}')
            processed_files.add(normalized)

        # Add -- to treat pattern as a literal argument, preventing injection
        cmd.append('--')
        cmd.append(search_pattern)
        cmd.append('.')  # Use current directory since we set cwd=base_path
        
        try:
            # grep exits with 1 if no matches are found, which is not an error.
            # It exits with 0 on success (match found). >1 for errors.
            process = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8',
                errors='replace',
                check=False,
                cwd=base_path  # Set working directory to project base path for proper pattern resolution
            )
            
            if process.returncode > 1:
                 raise RuntimeError(f"grep failed with exit code {process.returncode}: {process.stderr}")

            return parse_search_output(process.stdout, base_path)
        
        except FileNotFoundError:
            raise RuntimeError("'grep' not found. Please install it and ensure it's in your PATH.")
        except Exception as e:
            raise RuntimeError(f"An error occurred while running grep: {e}")
