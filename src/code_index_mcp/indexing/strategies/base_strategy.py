"""
Abstract base class for language parsing strategies.
"""

import os
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Optional
from ..models import SymbolInfo, FileInfo


class ParsingStrategy(ABC):
    """Abstract base class for language parsing strategies."""

    @abstractmethod
    def get_language_name(self) -> str:
        """Return the language name this strategy handles."""

    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """Return list of file extensions this strategy supports."""

    @abstractmethod
    def parse_file(self, file_path: str, content: str) -> Tuple[Dict[str, SymbolInfo], FileInfo]:
        """
        Parse file content and extract symbols.

        Args:
            file_path: Path to the file being parsed
            content: File content as string

        Returns:
            Tuple of (symbols_dict, file_info)
            - symbols_dict: Maps symbol_id -> SymbolInfo
            - file_info: FileInfo with metadata about the file
        """

    def _create_symbol_id(self, file_path: str, symbol_name: str) -> str:
        """
        Create a unique symbol ID.

        Args:
            file_path: Path to the file containing the symbol
            symbol_name: Name of the symbol

        Returns:
            Unique symbol identifier in format "relative_path::symbol_name"
        """
        relative_path = self._get_relative_path(file_path)
        return f"{relative_path}::{symbol_name}"

    def _get_relative_path(self, file_path: str) -> str:
        """Normalize path for symbol identifiers relative to project root."""
        if not file_path:
            return ""

        normalized = os.path.normpath(file_path)
        if normalized == ".":
            return ""

        normalized = normalized.replace("\\", "/")
        if normalized.startswith("./"):
            normalized = normalized[2:]

        if not os.path.isabs(file_path):
            normalized = normalized.lstrip("/")

        return normalized or os.path.basename(file_path)

    def _get_file_name(self, file_path: str) -> str:
        """Get just the filename from a full path."""
        return os.path.basename(file_path)

    def _slice_bytes(self, content_bytes: bytes, start: int, end: int) -> str:
        """Slice the UTF-8 bytes fed to tree-sitter using its byte offsets.

        tree-sitter reports node positions as byte offsets into the encoded
        source. Always slice the same bytes object that was passed to
        parser.parse() — never a str (issue #88).
        """
        start = max(0, min(start, len(content_bytes)))
        end = max(0, min(end, len(content_bytes)))
        if start >= end:
            return ""
        return content_bytes[start:end].decode("utf8", errors="ignore")

    def _line_at_byte(self, content_bytes: bytes, offset: int) -> int:
        """Return the 1-based line number containing the given byte offset."""
        offset = max(0, min(offset, len(content_bytes)))
        return content_bytes[:offset].count(b"\n") + 1
