#!/usr/bin/env python3
"""Issue #88 regression: non-ASCII content must not corrupt TS symbols."""

from code_index_mcp.indexing.strategies.typescript_strategy import TypeScriptParsingStrategy

ASCII_TS = """/** Cafes -- acucar */
function greet(): string {
  return "hi";
}

class Greeter {
  greet(): string {
    return "yo";
  }
}

interface Repo {
  save(): void;
}
"""

UNICODE_TS = """/** Cafés — açúcar 中文註解 */
function greet(): string {
  return "hi";
}

class Greeter {
  greet(): string {
    return "yo";
  }
}

interface Repo {
  save(): void;
}
"""


def _parse(source: str):
    strategy = TypeScriptParsingStrategy()
    symbols, file_info = strategy.parse_file("sample.ts", source)
    names = {sid.split("::", 1)[1]: info for sid, info in symbols.items()}
    return names, file_info


def test_unicode_symbols_match_ascii_twin() -> None:
    ascii_names, ascii_info = _parse(ASCII_TS)
    uni_names, uni_info = _parse(UNICODE_TS)

    assert set(uni_names) == set(ascii_names)
    assert uni_info.symbols == ascii_info.symbols
    for name in ascii_names:
        assert uni_names[name].line == ascii_names[name].line
        assert uni_names[name].signature == ascii_names[name].signature


def test_unicode_function_extracted_exactly() -> None:
    uni_names, uni_info = _parse(UNICODE_TS)
    assert "greet" in uni_names
    assert uni_names["greet"].signature == "function greet(): string {"
    assert "Repo" in uni_names
    assert "Repo" in uni_info.symbols["classes"]
    assert "greet" in uni_info.symbols["functions"]


def test_unicode_imports_and_exports_not_corrupted() -> None:
    source = "// Cafés — açúcar\nimport { x } from './x';\nexport const y = 1;\n"
    strategy = TypeScriptParsingStrategy()
    _, file_info = strategy.parse_file("sample.ts", source)
    assert file_info.imports == ["import { x } from './x';"]
    assert file_info.exports == ["export const y = 1;"]
