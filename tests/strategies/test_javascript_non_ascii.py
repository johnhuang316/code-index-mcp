#!/usr/bin/env python3
"""Issue #88 regression: non-ASCII content must not corrupt JS symbols."""

from code_index_mcp.indexing.strategies.javascript_strategy import JavaScriptParsingStrategy

ASCII_JS = """// Cafes -- acucar
function greet() { return "hi"; }

const shout = () => greet();

class Greeter {
  greet() { return "yo"; }
}
"""

UNICODE_JS = """// Cafés — açúcar 中文註解
function greet() { return "hi"; }

const shout = () => greet();

class Greeter {
  greet() { return "yo"; }
}
"""


def _parse(source: str):
    strategy = JavaScriptParsingStrategy()
    symbols, file_info = strategy.parse_file("sample.js", source)
    names = {sid.split("::", 1)[1]: info for sid, info in symbols.items()}
    return names, file_info


def test_unicode_symbols_match_ascii_twin() -> None:
    ascii_names, ascii_info = _parse(ASCII_JS)
    uni_names, uni_info = _parse(UNICODE_JS)

    assert set(uni_names) == set(ascii_names)
    assert uni_info.symbols == ascii_info.symbols
    for name in ascii_names:
        assert uni_names[name].line == ascii_names[name].line
        assert uni_names[name].signature == ascii_names[name].signature


def test_unicode_function_extracted_exactly() -> None:
    uni_names, uni_info = _parse(UNICODE_JS)
    assert "greet" in uni_names
    assert "shout" in uni_names
    assert uni_names["shout"].signature == "shout = () => greet()"
    assert "greet" in uni_info.symbols["functions"]
