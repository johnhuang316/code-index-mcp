#!/usr/bin/env python3
"""Issue #88 regression: non-ASCII content must not corrupt Kotlin symbols."""

import tree_sitter

from code_index_mcp.indexing.strategies.kotlin_strategy import (
    KotlinParsingStrategy,
    TraversalContext,
)

ASCII_KT = """// Cafes -- acucar
package com.example.app

import kotlin.collections.List

class Greeter {
    fun greet(): String = "hi"
}

fun topLevel(x: Int): Int = x + 1
"""

UNICODE_KT = """// Cafés — açúcar 中文註解
package com.example.app

import kotlin.collections.List

class Greeter {
    fun greet(): String = "hi"
}

fun topLevel(x: Int): Int = x + 1
"""


def _parse(source: str):
    strategy = KotlinParsingStrategy()
    symbols, file_info = strategy.parse_file("sample.kt", source)
    names = {sid.split("::", 1)[1]: info for sid, info in symbols.items()}
    return names, file_info


def test_unicode_symbols_match_ascii_twin() -> None:
    ascii_names, ascii_info = _parse(ASCII_KT)
    uni_names, uni_info = _parse(UNICODE_KT)

    assert set(uni_names) == set(ascii_names)
    assert uni_info.symbols == ascii_info.symbols
    assert uni_info.imports == ascii_info.imports
    for name in ascii_names:
        assert uni_names[name].line == ascii_names[name].line
        assert uni_names[name].signature == ascii_names[name].signature


def test_unicode_symbols_present() -> None:
    uni_names, _ = _parse(UNICODE_KT)
    assert "topLevel" in uni_names
    assert "Greeter.greet" in uni_names


# --- 以下兩個測試直攻 L218 / L227 的 fallback 分支(修改前必紅) ---

class _FakeNameNodeMissing:
    """Duck-typed node: name field 缺失,強制走 header fallback(L218)。

    _get_kotlin_function_name 只讀 child_by_field_name / start_point /
    start_byte / end_byte 四個屬性,假節點足以覆蓋。
    start_point 給極大列號讓 context.lines 快路徑失效。
    """

    def __init__(self, start_byte: int, end_byte: int):
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.start_point = (10 ** 6, 0)

    def child_by_field_name(self, _name):
        return None


def _make_context(source: str) -> TraversalContext:
    return TraversalContext(
        content=source,
        content_bytes=source.encode("utf8"),
        lines=[],  # 空 lines: 讓所有以行為準的快路徑失效,強制走 fallback
        file_path="sample.kt",
        symbols={},
        functions=[],
        classes=[],
        imports=[],
        symbol_lookup={},
        pending_calls=[],
        pending_call_set=set(),
    )


def test_function_name_header_fallback_survives_unicode() -> None:
    strategy = KotlinParsingStrategy()
    context = _make_context(UNICODE_KT)
    start = context.content_bytes.index(b"fun topLevel")
    end = context.content_bytes.index(b"= x + 1") + len(b"= x + 1")
    node = _FakeNameNodeMissing(start, end)
    assert strategy._get_kotlin_function_name(node, context) == "topLevel"


def test_function_signature_fallback_survives_unicode() -> None:
    strategy = KotlinParsingStrategy()
    context = _make_context(UNICODE_KT)
    parser = tree_sitter.Parser(strategy.kotlin_language)
    tree = parser.parse(context.content_bytes)

    def find_function(node):
        if node.type == "function_declaration":
            return node
        for child in node.children:
            found = find_function(child)
            if found is not None:
                return found
        return None

    fn_node = find_function(tree.root_node)
    assert fn_node is not None
    signature = strategy._get_kotlin_function_signature(fn_node, context)
    assert signature == 'fun greet(): String = "hi"'
