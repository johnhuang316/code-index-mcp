"""
File Service - Simple file reading service for MCP resources.

This service provides simple file content reading functionality for MCP resources.
Complex file analysis has been moved to CodeIntelligenceService.

Usage:
- get_file_content() - used by files://{file_path} resource
"""

import os
from .base_service import BaseService
from ..utils.encoding import read_file_with_encoding


class FileService(BaseService):
    """
    Simple service for file content reading.

    This service handles basic file reading operations for MCP resources.
    Complex analysis functionality has been moved to CodeIntelligenceService.
    """

    def get_file_content(self, file_path: str, encoding: str | None = None) -> str:
        """
        Get file content for MCP resource.

        Args:
            file_path: Path to the file (relative to project root)
            encoding: Explicit encoding to use. When None, resolved from
                project settings or defaults to UTF-8.

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

        enc = encoding
        if enc is None and self.settings:
            try:
                enc = self.settings.get_encoding_config().get("default_encoding")
            except Exception:
                pass

        try:
            return read_file_with_encoding(full_path, encoding=enc)
        except ValueError as e:
            raise ValueError(f"Could not decode file {file_path}. {e}") from e
        except (FileNotFoundError, PermissionError, OSError) as e:
            raise FileNotFoundError(f"Error reading file: {e}") from e
