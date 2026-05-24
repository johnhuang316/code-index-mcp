"""
Nim parsing strategy using regex-based symbol extraction.

There is no maintained PyPI tree-sitter grammar package for Nim, so this
strategy intentionally uses conservative line-oriented parsing. It extracts
stable top-level declarations without invoking the Nim compiler/nimsuggest.
"""

import logging
import re
from typing import Dict, List, Tuple

from .base_strategy import ParsingStrategy
from ..models import SymbolInfo, FileInfo

logger = logging.getLogger(__name__)


_IDENTIFIER = r"(?:`[^`]+`|[A-Za-z_][A-Za-z0-9_]*)"


class NimParsingStrategy(ParsingStrategy):
    """Nim parsing strategy using conservative regex-based extraction."""

    PROC_PATTERN = re.compile(
        rf"^([ \t]*)(proc|func|method|iterator|converter|macro|template)\s+({_IDENTIFIER})\*?\b"
    )
    INLINE_TYPE_PATTERN = re.compile(
        rf"^([ \t]*)type\s+({_IDENTIFIER})\*?\s*(?:=|:)"
    )
    TYPE_BLOCK_PATTERN = re.compile(r"^([ \t]*)type\s*(?:#.*)?$")
    TYPE_ITEM_PATTERN = re.compile(
        rf"^([ \t]+)({_IDENTIFIER})\*?\s*=\s*(object|enum|ref\s+object|tuple|distinct|proc|concept)\b"
    )
    TOP_VALUE_PATTERN = re.compile(
        rf"^([ \t]*)(const|let|var)\s+({_IDENTIFIER})\*?\s*[:=]"
    )
    VALUE_BLOCK_PATTERN = re.compile(r"^([ \t]*)(const|let|var)\s*(?:#.*)?$")
    VALUE_ITEM_PATTERN = re.compile(rf"^([ \t]+)({_IDENTIFIER})\*?\s*[:=]")
    IMPORT_PATTERN = re.compile(r"^\s*import\s+(.+)$")
    FROM_IMPORT_PATTERN = re.compile(r"^\s*from\s+(\S+)\s+import\s+(.+)$")
    EXPORT_PATTERN = re.compile(r"^\s*export\s+(.+)$")

    def get_language_name(self) -> str:
        return "nim"

    def get_supported_extensions(self) -> List[str]:
        return [".nim", ".nims"]

    def parse_file(self, file_path: str, content: str) -> Tuple[Dict[str, SymbolInfo], FileInfo]:
        """Parse a Nim file and extract top-level symbols/imports."""
        symbols: Dict[str, SymbolInfo] = {}
        functions: List[str] = []
        classes: List[str] = []
        imports: List[str] = []
        exports: List[str] = []

        lines = content.splitlines()
        active_block: str | None = None

        for index, line in enumerate(lines):
            line_number = index + 1
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            indent = self._indent_width(line)

            if indent == 0:
                active_block = None

                value_block = self.VALUE_BLOCK_PATTERN.match(line)
                if value_block:
                    active_block = value_block.group(2)
                    continue

                if self.TYPE_BLOCK_PATTERN.match(line):
                    active_block = "type"
                    continue

                proc_match = self.PROC_PATTERN.match(line)
                if proc_match:
                    kind = proc_match.group(2)
                    name = self._clean_name(proc_match.group(3))
                    self._add_symbol(symbols, file_path, name, kind, line_number, lines)
                    functions.append(name)
                    continue

                inline_type = self.INLINE_TYPE_PATTERN.match(line)
                if inline_type:
                    name = self._clean_name(inline_type.group(2))
                    self._add_symbol(symbols, file_path, name, "class", line_number, lines)
                    classes.append(name)
                    continue

                value_match = self.TOP_VALUE_PATTERN.match(line)
                if value_match:
                    kind = value_match.group(2)
                    name = self._clean_name(value_match.group(3))
                    self._add_symbol(symbols, file_path, name, kind, line_number, lines)
                    continue

            elif active_block == "type":
                type_item = self.TYPE_ITEM_PATTERN.match(line)
                if type_item:
                    name = self._clean_name(type_item.group(2))
                    self._add_symbol(symbols, file_path, name, "class", line_number, lines)
                    classes.append(name)
                    continue

            elif active_block in {"const", "let", "var"}:
                value_item = self.VALUE_ITEM_PATTERN.match(line)
                if value_item:
                    name = self._clean_name(value_item.group(2))
                    self._add_symbol(symbols, file_path, name, active_block, line_number, lines)
                    continue

            import_match = self.IMPORT_PATTERN.match(line)
            if import_match:
                imports.extend(self._split_import_list(import_match.group(1).strip()))
                continue

            from_import = self.FROM_IMPORT_PATTERN.match(line)
            if from_import:
                imports.append(f"{from_import.group(1).strip()}/{from_import.group(2).strip()}")
                continue

            export_match = self.EXPORT_PATTERN.match(line)
            if export_match:
                exports.extend(self._split_import_list(export_match.group(1).strip()))

        self._populate_end_lines(symbols, len(lines))

        file_info = FileInfo(
            language=self.get_language_name(),
            line_count=len(lines),
            symbols={"functions": functions, "classes": classes},
            imports=imports,
            exports=exports,
        )

        return symbols, file_info

    def _add_symbol(
        self,
        symbols: Dict[str, SymbolInfo],
        file_path: str,
        name: str,
        kind: str,
        line_number: int,
        lines: List[str],
    ) -> None:
        symbol_id = self._create_symbol_id(file_path, name)
        symbols[symbol_id] = SymbolInfo(
            type=kind,
            file=file_path,
            line=line_number,
            signature=self._extract_signature(lines, line_number - 1),
        )

    @staticmethod
    def _indent_width(line: str) -> int:
        width = 0
        for ch in line:
            if ch == " ":
                width += 1
            elif ch == "\t":
                width += 4
            else:
                break
        return width

    @staticmethod
    def _clean_name(raw: str) -> str:
        if raw.startswith("`") and raw.endswith("`"):
            return raw[1:-1]
        return raw

    @staticmethod
    def _split_import_list(raw: str) -> List[str]:
        parts: List[str] = []
        current: List[str] = []
        bracket_depth = 0
        for ch in raw:
            if ch == "[":
                bracket_depth += 1
            elif ch == "]" and bracket_depth > 0:
                bracket_depth -= 1
            if ch == "," and bracket_depth == 0:
                item = "".join(current).strip()
                if item:
                    parts.append(item)
                current = []
            else:
                current.append(ch)
        item = "".join(current).strip()
        if item:
            parts.append(item)
        return parts

    def _extract_signature(self, lines: List[str], start_idx: int) -> str:
        """Extract a declaration signature from one or more lines."""
        if start_idx >= len(lines):
            return ""

        signature_lines = [lines[start_idx].strip()]
        base_indent = self._indent_width(lines[start_idx])

        for i in range(start_idx + 1, min(start_idx + 12, len(lines))):
            line = lines[i]
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = self._indent_width(line)
            if indent > base_indent:
                signature_lines.append(stripped)
                if stripped.endswith("=") or stripped.endswith(":"):
                    break
            else:
                break

        return " ".join(signature_lines)

    @staticmethod
    def _populate_end_lines(symbols: Dict[str, SymbolInfo], total_lines: int) -> None:
        ordered = sorted(symbols.values(), key=lambda symbol: symbol.line)
        for index, symbol in enumerate(ordered):
            if index + 1 < len(ordered):
                symbol.end_line = max(symbol.line, ordered[index + 1].line - 1)
            else:
                symbol.end_line = total_lines
