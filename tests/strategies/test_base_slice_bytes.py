#!/usr/bin/env python3
"""Unit tests for ParsingStrategy._slice_bytes / _line_at_byte (issue #88)."""

from typing import Dict, List, Tuple

from code_index_mcp.indexing.strategies.base_strategy import ParsingStrategy
from code_index_mcp.indexing.models import SymbolInfo, FileInfo


class _DummyStrategy(ParsingStrategy):
    """Minimal concrete subclass so the ABC can be instantiated."""

    def get_language_name(self) -> str:
        return "dummy"

    def get_supported_extensions(self) -> List[str]:
        return [".dummy"]

    def parse_file(self, file_path: str, content: str) -> Tuple[Dict[str, SymbolInfo], FileInfo]:
        return {}, FileInfo(language="dummy", line_count=0, symbols={}, imports=[])


UNICODE_CONTENT = "/** Cafés — açúcar */\nfunction greet() {}\n"
UNICODE_BYTES = UNICODE_CONTENT.encode("utf8")


def test_slice_bytes_extracts_correct_text_after_multibyte_chars() -> None:
    strategy = _DummyStrategy()
    start = UNICODE_BYTES.index(b"greet")
    end = start + len(b"greet")
    assert strategy._slice_bytes(UNICODE_BYTES, start, end) == "greet"


def test_slice_bytes_clamps_out_of_range() -> None:
    strategy = _DummyStrategy()
    data = b"hello"
    assert strategy._slice_bytes(data, -3, 2) == "he"
    assert strategy._slice_bytes(data, 3, 999) == "lo"


def test_slice_bytes_inverted_and_empty_ranges_return_empty() -> None:
    strategy = _DummyStrategy()
    data = b"hello"
    assert strategy._slice_bytes(data, 4, 2) == ""
    assert strategy._slice_bytes(data, 2, 2) == ""
    assert strategy._slice_bytes(b"", 0, 5) == ""


def test_line_at_byte_counts_newlines_in_bytes() -> None:
    strategy = _DummyStrategy()
    offset = UNICODE_BYTES.index(b"function")
    assert strategy._line_at_byte(UNICODE_BYTES, offset) == 2
    assert strategy._line_at_byte(UNICODE_BYTES, 0) == 1
    assert strategy._line_at_byte(UNICODE_BYTES, 10 ** 6) == 3
