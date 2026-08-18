#!/usr/bin/env python3
"""Issue #88 regression: non-ASCII content must not corrupt Java symbols."""

from code_index_mcp.indexing.strategies.java_strategy import JavaParsingStrategy

ASCII_JAVA = """// Cafes -- acucar
package com.example;

import java.util.List;

public class Greeter {
    public String greet() {
        return "hi";
    }
}
"""

UNICODE_JAVA = """// Cafés — açúcar 中文註解
package com.example;

import java.util.List;

public class Greeter {
    public String greet() {
        return "hi";
    }
}
"""


def _parse(source: str):
    strategy = JavaParsingStrategy()
    symbols, file_info = strategy.parse_file("Sample.java", source)
    names = {sid.split("::", 1)[1]: info for sid, info in symbols.items()}
    return names, file_info


def test_unicode_symbols_match_ascii_twin() -> None:
    ascii_names, ascii_info = _parse(ASCII_JAVA)
    uni_names, uni_info = _parse(UNICODE_JAVA)

    assert set(uni_names) == set(ascii_names)
    assert uni_info.symbols == ascii_info.symbols
    assert uni_info.package == ascii_info.package == "com.example"
    assert uni_info.imports == ascii_info.imports == ["java.util.List"]
    for name in ascii_names:
        assert uni_names[name].line == ascii_names[name].line
        assert uni_names[name].signature == ascii_names[name].signature


def test_unicode_method_extracted_exactly() -> None:
    uni_names, _ = _parse(UNICODE_JAVA)
    assert "Greeter" in uni_names
    assert "Greeter.greet" in uni_names
    assert uni_names["Greeter.greet"].signature == "public String greet() {"
