"""
File Service - Simple file reading service for MCP resources.

This service provides simple file content reading functionality for MCP resources.
Complex file analysis has been moved to CodeIntelligenceService.

Usage:
- get_file_content() - used by files://{file_path} resource
"""

import os
from .base_service import BaseService
from ..utils.encoding import read_file_content


class FileService(BaseService):
    """
    Simple service for file content reading.

    This service handles basic file reading operations for MCP resources.
    Complex analysis functionality has been moved to CodeIntelligenceService.
    """

    def get_file_content(self, file_path: str) -> str:
        """
        Get file content for MCP resource.

        Automatically detects file encoding (UTF-8, GBK, GB2312, Shift-JIS,
        etc.) using charset-normalizer.

        Args:
            file_path: Path to the file (relative to project root)

        Returns:
            File content as string

        Raises:
            ValueError: If project is not set up or path is invalid
            FileNotFoundError: If file is not found or readable
        """
        self._require_project_setup()
        self._require_valid_file_path(file_path)

        # Build full path
        full_path = os.path.join(self.base_path, file_path)

        try:
            return read_file_content(full_path)
        except ValueError as e:
            raise ValueError(
                f"Could not decode file {file_path}. {e}"
            ) from e
        except (FileNotFoundError, PermissionError, OSError) as e:
            raise FileNotFoundError(f"Error reading file: {e}") from e
