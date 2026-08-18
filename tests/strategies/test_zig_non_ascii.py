#!/usr/bin/env python3
"""Issue #88 regression: non-ASCII content must not corrupt Zig symbols/lines."""

from code_index_mcp.indexing.strategies.zig_strategy import ZigParsingStrategy

# 第一行塞大量多位元組字元,讓 byte 偏移漂移跨過換行,舊行號演算法必錯。
ASCII_ZIG = """// this is a long ascii comment used to pad the first line for parity!!
fn a() void {}
fn togglePause() void {}
"""

UNICODE_ZIG = """// 這是一段很長的中文註解用來製造位元組偏移量以測試行號的正確性→π—
fn a() void {}
fn togglePause() void {}
"""


def _parse(source: str):
    strategy = ZigParsingStrategy()
    symbols, file_info = strategy.parse_file("sample.zig", source)
    names = {sid.split("::", 1)[1]: info for sid, info in symbols.items()}
    return names, file_info


def test_unicode_symbols_match_ascii_twin() -> None:
    ascii_names, ascii_info = _parse(ASCII_ZIG)
    uni_names, uni_info = _parse(UNICODE_ZIG)

    assert set(uni_names) == set(ascii_names)
    assert uni_info.symbols == ascii_info.symbols
    for name in ascii_names:
        assert uni_names[name].line == ascii_names[name].line
        assert uni_names[name].signature == ascii_names[name].signature


def test_unicode_names_and_lines_exact() -> None:
    uni_names, _ = _parse(UNICODE_ZIG)
    assert "togglePause" in uni_names
    assert uni_names["togglePause"].line == 3
    assert uni_names["a"].line == 2
    assert uni_names["togglePause"].signature == "fn togglePause() void {}"
