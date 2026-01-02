"""
Fallback parsing strategy for unsupported languages and file types.
"""

import os
from typing import Dict, List, Tuple
from .base_strategy import ParsingStrategy
from ..models import SymbolInfo, FileInfo


class FallbackParsingStrategy(ParsingStrategy):
    """Fallback parser for unsupported languages and file types."""

    def __init__(self, language_name: str = "unknown"):
        self.language_name = language_name

    def get_language_name(self) -> str:
        return self.language_name

    def get_supported_extensions(self) -> List[str]:
        return []  # Fallback supports any extension

    def parse_file(self, file_path: str, content: str) -> Tuple[Dict[str, SymbolInfo], FileInfo]:
        """Basic parsing: extract file information without symbol parsing."""
        symbols = {}

        # For document files, we can at least index their existence
        file_info = FileInfo(
            language=self.language_name,
            line_count=len(content.splitlines()),
            symbols={"functions": [], "classes": []},
            imports=[]
        )

        # For document files (e.g. .md, .txt, .json), we can add a symbol representing the file itself
        if self.language_name in ['markdown', 'text', 'json', 'yaml', 'xml', 'config', 'css', 'html']:
            filename = os.path.basename(file_path)
            symbol_id = self._create_symbol_id(file_path, f"file:{filename}")
            symbols[symbol_id] = SymbolInfo(
                type="file",
                file=file_path,
                line=1,
                end_line=len(content.splitlines()),
                signature=f"{self.language_name} file: {filename}"
            )

        return symbols, file_info
