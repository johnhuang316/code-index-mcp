"""
Common validation logic for the MCP server.

This module provides shared validation functions used across services
to ensure consistent validation behavior and reduce code duplication.
"""

import os
import re
import fnmatch
from typing import Optional, List

from ..indexing.qualified_names import normalize_file_path


class ValidationHelper:
    """
    Helper class containing common validation logic.

    This class provides static methods for common validation operations
    that are used across multiple services.
    """

    @staticmethod
    def validate_file_path(file_path: str, base_path: str) -> Optional[str]:
        """
        Validate a file path for security and accessibility.

        This method checks for:
        - Path traversal attempts
        - Absolute path usage (not allowed)
        - Path existence within base directory

        Args:
            file_path: The file path to validate (should be relative)
            base_path: The base project directory path

        Returns:
            Error message if validation fails, None if valid
        """
        if not file_path:
            return "File path cannot be empty"

        if not base_path:
            return "Base path not set"

        # Handle absolute paths (especially Windows paths starting with drive letters)
        if os.path.isabs(file_path) or (len(file_path) > 1 and file_path[1] == ':'):
            return (f"Absolute file paths like '{file_path}' are not allowed. "
                    "Please use paths relative to the project root.")

        # Normalize the file path
        norm_path = os.path.normpath(file_path)

        # Check for path traversal attempts
        if "..\\" in norm_path or "../" in norm_path or norm_path.startswith(".."):
            return f"Invalid file path: {file_path} (directory traversal not allowed)"

        # Construct the full path and verify it's within the project bounds
        full_path = os.path.join(base_path, norm_path)
        real_full_path = os.path.realpath(full_path)
        real_base_path = os.path.realpath(base_path)

        if not real_full_path.startswith(real_base_path):
            return "Access denied. File path must be within project directory."

        return None

    @staticmethod
    def validate_directory_path(dir_path: str) -> Optional[str]:
        """
        Validate a directory path for project initialization.

        Args:
            dir_path: The directory path to validate

        Returns:
            Error message if validation fails, None if valid
        """
        if not dir_path:
            return "Directory path cannot be empty"

        # Normalize and get absolute path
        try:
            norm_path = os.path.normpath(dir_path)
            abs_path = os.path.abspath(norm_path)
        except (OSError, ValueError) as e:
            return f"Invalid path format: {str(e)}"

        if not os.path.exists(abs_path):
            return f"Path does not exist: {abs_path}"

        if not os.path.isdir(abs_path):
            return f"Path is not a directory: {abs_path}"

        return None

    @staticmethod
    def validate_glob_pattern(pattern: str) -> Optional[str]:
        """
        Validate a glob pattern for file searching.

        Args:
            pattern: The glob pattern to validate

        Returns:
            Error message if validation fails, None if valid
        """
        if not pattern:
            return "Pattern cannot be empty"

        # Check for potentially dangerous patterns
        if pattern.startswith('/') or pattern.startswith('\\'):
            return "Pattern cannot start with path separator"

        # Test if the pattern is valid by trying to compile it
        try:
            # This will raise an exception if the pattern is malformed
            fnmatch.translate(pattern)
        except (ValueError, TypeError) as e:
            return f"Invalid glob pattern: {str(e)}"

        return None

    @staticmethod
    def validate_search_pattern(pattern: str, regex: bool = False) -> Optional[str]:
        """
        Validate a search pattern for code searching.

        Args:
            pattern: The search pattern to validate
            regex: Whether the pattern is a regex pattern

        Returns:
            Error message if validation fails, None if valid
        """
        if not pattern:
            return "Search pattern cannot be empty"

        if regex:
            # Basic regex validation - check for potentially dangerous patterns
            try:
                re.compile(pattern)
            except re.error as e:
                return (
                    f"Invalid regex pattern: {str(e)}. "
                    "If you intended a literal search, pass regex=False."
                )

            # Check for potentially expensive regex patterns (basic ReDoS protection)
            dangerous_patterns = [
                r'\(\?\=.*\)\+',  # Positive lookahead with quantifier
                r'\(\?\!.*\)\+',  # Negative lookahead with quantifier
                r'\(\?\<\=.*\)\+',  # Positive lookbehind with quantifier
                r'\(\?\<\!.*\)\+',  # Negative lookbehind with quantifier
            ]

            for dangerous in dangerous_patterns:
                if re.search(dangerous, pattern):
                    return "Potentially dangerous regex pattern detected"

        return None

    @staticmethod
    def validate_pagination(start_index: int, max_results: Optional[int]) -> Optional[str]:
        """
        Validate pagination parameters for search queries.

        Args:
            start_index: The index of the first result to include.
            max_results: The maximum number of results to return.

        Returns:
            Error message if validation fails, None if valid.
        """
        if not isinstance(start_index, int):
            return "start_index must be an integer"

        if start_index < 0:
            return "start_index cannot be negative"

        if max_results is None:
            return None

        if not isinstance(max_results, int):
            return "max_results must be an integer when provided"

        if max_results <= 0:
            return "max_results must be greater than zero when provided"

        return None

    @staticmethod
    def validate_file_extensions(extensions: List[str]) -> Optional[str]:
        """
        Validate a list of file extensions.

        Args:
            extensions: List of file extensions to validate

        Returns:
            Error message if validation fails, None if valid
        """
        if not extensions:
            return "Extensions list cannot be empty"

        for ext in extensions:
            if not isinstance(ext, str):
                return "All extensions must be strings"

            if not ext.startswith('.'):
                return f"Extension '{ext}' must start with a dot"

            if len(ext) < 2:
                return f"Extension '{ext}' is too short"

        return None

    @staticmethod
    def sanitize_file_path(file_path: str) -> str:
        """
        Sanitize a file path by normalizing separators and removing dangerous elements.

        Args:
            file_path: The file path to sanitize

        Returns:
            Sanitized file path
        """
        if not file_path:
            return ""

        # Normalize path separators and structure
        sanitized = normalize_file_path(file_path)

        # Remove any leading slashes to ensure relative path
        sanitized = sanitized.lstrip('/')

        return sanitized
