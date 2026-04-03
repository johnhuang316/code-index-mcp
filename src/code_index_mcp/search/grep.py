"""
Search Strategy for standard grep
"""
import os
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple

from .base import SearchStrategy, parse_search_output, create_word_boundary_pattern

FALLBACK_EXCLUDE_DIRS = ['.git', 'node_modules', '__pycache__', '.venv', 'venv']


class GrepStrategy(SearchStrategy):
    """
    Search strategy using the standard 'grep' command-line tool.

    When inside a git repository, uses 'git grep' which natively respects
    .gitignore rules. Otherwise falls back to 'grep -r' with hardcoded
    exclude directories.

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

    def _is_git_repo(self, path: str) -> bool:
        """Return True if path is the root of a git repository."""
        return os.path.isdir(os.path.join(path, '.git'))

    def build_exclude_args(self, exclude_patterns: list) -> list:
        """
        Translate a list of exclude patterns into grep CLI arguments.

        Patterns ending with '/' are treated as directories and become
        --exclude-dir flags; all others become --exclude flags.
        """
        args = []
        for p in exclude_patterns:
            if p.endswith('/'):
                args.append(f'--exclude-dir={p.rstrip("/")}')
            else:
                args.append(f'--exclude={p}')
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
    ) -> Dict[str, List[Tuple[int, str]]]:
        """
        Execute a search using git grep (in a git repo) or plain grep.

        Args:
            pattern: The search pattern
            base_path: Directory to search in
            case_sensitive: Whether search is case sensitive
            context_lines: Number of context lines to show
            file_pattern: File pattern to filter (e.g. '*.py')
            fuzzy: Enable word boundary matching
            regex: Enable regex pattern matching
            exclude_patterns: Additional patterns to exclude (dirs end with '/')
        """
        use_git = self._is_git_repo(base_path)

        if use_git:
            cmd = ['git', 'grep', '-n']
        else:
            cmd = ['grep', '-r', '-n']

        # Determine the effective search pattern and flags
        if regex:
            cmd.append('-E')
        elif fuzzy:
            pattern = create_word_boundary_pattern(pattern)
            cmd.append('-E')
        else:
            cmd.append('-F')

        if not case_sensitive:
            cmd.append('-i')

        if context_lines > 0:
            cmd.extend(['-A', str(context_lines)])
            cmd.extend(['-B', str(context_lines)])

        if not use_git and file_pattern:
            cmd.append(f'--include={file_pattern}')

        if not use_git:
            # Add hardcoded fallback excludes for non-git trees
            for d in FALLBACK_EXCLUDE_DIRS:
                cmd.append(f'--exclude-dir={d}')

        # Inject user-supplied exclude patterns (grep only; git grep ignores them)
        if not use_git and exclude_patterns:
            cmd.extend(self.build_exclude_args(exclude_patterns))

        # Separator: everything after '--' is treated as a non-option argument
        cmd.append('--')
        cmd.append(pattern)

        if use_git:
            # git grep uses pathspecs after the pattern for file filtering
            if file_pattern:
                cmd.append(file_pattern)
        else:
            # grep -r uses '.' as the starting directory (cwd=base_path)
            cmd.append('.')

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
                cwd=base_path,
            )

            if process.returncode > 1:
                raise RuntimeError(
                    f"grep failed with exit code {process.returncode}: {process.stderr}"
                )

            return parse_search_output(process.stdout, base_path)

        except FileNotFoundError:
            raise RuntimeError("'grep' not found. Please install it and ensure it's in your PATH.")
        except Exception as e:
            raise RuntimeError(f"An error occurred while running grep: {e}")
