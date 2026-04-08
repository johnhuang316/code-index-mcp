"""
File System Tool - Pure technical component for file system operations.

This tool handles low-level file system operations without any business logic.
"""

import os
from typing import Dict, Any, Optional
from pathlib import Path

from ...utils.encoding import read_file_with_encoding as _read_file


class FileSystemTool:
    """
    Pure technical component for file system operations.

    This tool provides low-level file system capabilities without
    any business logic or decision making.
    """

    def __init__(self):
        pass

    def get_file_stats(self, file_path: str) -> Dict[str, Any]:
        """
        Get basic file system statistics for a file.

        Args:
            file_path: Absolute path to the file

        Returns:
            Dictionary with file statistics

        Raises:
            FileNotFoundError: If file doesn't exist
            OSError: If file cannot be accessed
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            stat_info = os.stat(file_path)
            path_obj = Path(file_path)

            return {
                'size_bytes': stat_info.st_size,
                'modified_time': stat_info.st_mtime,
                'created_time': stat_info.st_ctime,
                'is_file': path_obj.is_file(),
                'is_directory': path_obj.is_dir(),
                'extension': path_obj.suffix,
                'name': path_obj.name,
                'parent': str(path_obj.parent)
            }

        except OSError as e:
            raise OSError(f"Cannot access file {file_path}: {e}") from e

    def read_file_content(self, file_path: str) -> str:
        """
        Read file content with encoding-aware reading.

        Args:
            file_path: Absolute path to the file

        Returns:
            File content as string

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file cannot be decoded
        """
        return _read_file(file_path)

    def count_lines(self, file_path: str) -> int:
        """
        Count the number of lines in a file.

        Args:
            file_path: Absolute path to the file

        Returns:
            Number of lines in the file

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        try:
            content = self.read_file_content(file_path)
            return len(content.splitlines())
        except Exception:
            # If we can't read the file, return 0
            return 0

    def detect_language_from_extension(self, file_path: str) -> str:
        """
        Detect programming language from file extension.

        Args:
            file_path: Path to the file

        Returns:
            Language name or 'unknown'
        """
        extension = Path(file_path).suffix.lower()

        lang_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.cxx': 'cpp',
            '.cc': 'cpp',
            '.c': 'c',
            '.h': 'c',
            '.hpp': 'cpp',
            '.hxx': 'cpp',
            '.cs': 'csharp',
            '.go': 'go',
            '.rs': 'rust',
            '.php': 'php',
            '.rb': 'ruby',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.m': 'objc',
            '.mm': 'objc',
            '.html': 'html',
            '.htm': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.sass': 'sass',
            '.less': 'less',
            '.json': 'json',
            '.xml': 'xml',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.md': 'markdown',
            '.txt': 'text',
            '.sh': 'shell',
            '.bash': 'shell',
            '.zsh': 'shell',
            '.fish': 'shell',
            '.ps1': 'powershell',
            '.bat': 'batch',
            '.cmd': 'batch'
        }

        return lang_map.get(extension, 'unknown')

    def is_text_file(self, file_path: str) -> bool:
        """
        Check if a file is likely a text file.

        Args:
            file_path: Path to the file

        Returns:
            True if file appears to be text, False otherwise
        """
        try:
            # Try to read a small portion of the file
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)

            # Check for null bytes (common in binary files)
            if b'\x00' in chunk:
                return False

            # Try to decode as UTF-8
            try:
                chunk.decode('utf-8')
                return True
            except UnicodeDecodeError:
                # Try other encodings
                for encoding in ['latin-1', 'cp1252']:
                    try:
                        chunk.decode(encoding)
                        return True
                    except UnicodeDecodeError:
                        continue

                return False

        except Exception:
            return False

    def get_file_size_category(self, file_path: str) -> str:
        """
        Categorize file size for analysis purposes.

        Args:
            file_path: Path to the file

        Returns:
            Size category: 'small', 'medium', 'large', or 'very_large'
        """
        try:
            size = os.path.getsize(file_path)

            if size < 1024:  # < 1KB
                return 'tiny'
            elif size < 10 * 1024:  # < 10KB
                return 'small'
            elif size < 100 * 1024:  # < 100KB
                return 'medium'
            elif size < 1024 * 1024:  # < 1MB
                return 'large'
            else:
                return 'very_large'

        except Exception:
            return 'unknown'
