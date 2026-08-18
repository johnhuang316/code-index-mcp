# Issue #88 Byte-Offset Slicing Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修復 tree-sitter byte offset 被當成 Python str 字元索引使用導致非 ASCII 檔案符號名稱、簽名、行號損毀的 bug（issue #88）。

**Architecture:** 在 `ParsingStrategy` base class 新增 bytes-only 的 `_slice_bytes()` / `_line_at_byte()` helper；每個 tree-sitter 策略把餵給 `parser.parse()` 的那份 `content.encode('utf8')` bytes 保留下來，所有 `start_byte`/`end_byte` 切片一律切這份 bytes。規則：**量與切用同一把尺**。

**Tech Stack:** Python 3.10+（開發環境用 Homebrew Python 3.12 建 venv）、tree-sitter、pytest。

**Spec:** `docs/superpowers/specs/2026-07-27-issue-88-byte-offset-design.md`

## Global Constraints

- 分支：`fix/issue-88-byte-offset-slicing`（已存在，spec 已 commit 於其上）。
- 只修 `src/code_index_mcp/indexing/strategies/` 下的檔案與新增測試；**不動** `json_index_builder.py` 讀檔路徑、**不動** `csharp_strategy.py` / `rust_strategy.py` / `go_strategy.py` / `objective_c_strategy.py` / `python_strategy.py` / `fallback_strategy.py`。
- base 的新 helper **只收 `bytes`**，不收 `str`（不做 union 簽名）。
- 每個 task 一個 commit，訊息格式 `fix: ...` / `test: ...`，結尾加 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`。
- git 身分已設 repo-local（johnhuang316），不需要再設定。
- 所有 pytest 指令用 `venv/bin/pytest`（Task 1 會建立）。

---

### Task 1: 測試環境 + base `_slice_bytes` / `_line_at_byte`

**Files:**
- Create: `venv/`（不 commit；`.gitignore` 已含）
- Create: `tests/strategies/test_base_slice_bytes.py`
- Modify: `src/code_index_mcp/indexing/strategies/base_strategy.py`（在 `_get_file_name` 之後、`_safe_extract_text` 之前插入新方法；**此 task 不刪舊方法**，zig 還在用，Task 6 才刪）

**Interfaces:**
- Produces: `ParsingStrategy._slice_bytes(content_bytes: bytes, start: int, end: int) -> str`（越界 clamp、`start >= end` 回 `""`、`decode('utf8', errors='ignore')`）
- Produces: `ParsingStrategy._line_at_byte(content_bytes: bytes, offset: int) -> int`（1-based 行號）
- Task 2–6 全部依賴這兩個方法。

- [ ] **Step 1: 建立 venv 並安裝**

```bash
cd /Users/cqi_clawbot/Project/code-index-mcp
/opt/homebrew/opt/python@3.12/bin/python3.12 -m venv venv
venv/bin/pip install -e . pytest
```

預期：安裝成功結尾顯示 `Successfully installed ... code-index-mcp-2.17.0 ... pytest-...`。
（系統 `/usr/bin/python3` 是 3.9.6，低於專案要求的 3.10，所以必須用 Homebrew 3.12。）

- [ ] **Step 2: 跑既有測試確認基線是綠的**

```bash
venv/bin/pytest tests/ -q
```

預期:全部 PASS(如有既有失敗,記下失敗清單,後續 task 不得新增失敗項)。

- [ ] **Step 3: 寫失敗測試**

建立 `tests/strategies/test_base_slice_bytes.py`,完整內容:

```python
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
```

- [ ] **Step 4: 確認測試失敗**

```bash
venv/bin/pytest tests/strategies/test_base_slice_bytes.py -v
```

預期:FAIL,錯誤為 `AttributeError: '_DummyStrategy' object has no attribute '_slice_bytes'`。

- [ ] **Step 5: 實作**

在 `src/code_index_mcp/indexing/strategies/base_strategy.py` 的 `_get_file_name` 方法(L82-84)之後插入:

```python
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
```

- [ ] **Step 6: 確認測試通過**

```bash
venv/bin/pytest tests/strategies/test_base_slice_bytes.py -v
```

預期:4 項全 PASS。

- [ ] **Step 7: Commit**

```bash
git add tests/strategies/test_base_slice_bytes.py src/code_index_mcp/indexing/strategies/base_strategy.py
git commit -m "fix: add byte-safe _slice_bytes/_line_at_byte to ParsingStrategy base (#88)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: TypeScript 策略(15 處)

**Files:**
- Create: `tests/strategies/test_typescript_non_ascii.py`
- Modify: `src/code_index_mcp/indexing/strategies/typescript_strategy.py`

**Interfaces:**
- Consumes: `self._slice_bytes(content_bytes, start, end)`(Task 1)
- Produces: `TraversalContext`(typescript_strategy 內部 class)的 `content: str` 欄位**換成** `content_bytes: bytes`;5 個私有 helper 的 `content: str` 參數換成 `content_bytes: bytes`。外部介面 `parse_file(file_path, content)` 不變。

- [ ] **Step 1: 寫失敗測試(雙胞胎檔案)**

建立 `tests/strategies/test_typescript_non_ascii.py`,完整內容:

```python
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
    assert "Greeter" in uni_names
    assert "Greeter.greet" in uni_names
    assert "greet" in uni_info.symbols["functions"]


def test_unicode_imports_and_exports_not_corrupted() -> None:
    source = "// Cafés — açúcar\nimport { x } from './x';\nexport const y = 1;\n"
    strategy = TypeScriptParsingStrategy()
    _, file_info = strategy.parse_file("sample.ts", source)
    assert file_info.imports == ["import { x } from './x';"]
    assert file_info.exports == ["export const y = 1;"]
```

- [ ] **Step 2: 確認測試失敗**

```bash
venv/bin/pytest tests/strategies/test_typescript_non_ascii.py -v
```

預期:FAIL——`test_unicode_symbols_match_ascii_twin` 的名稱集合不相等(unicode 版出現 `(): s` 之類的亂碼名),`test_unicode_function_extracted_exactly` 找不到 `greet`。

- [ ] **Step 3: 修改 `parse_file`(L42-58)**

原:

```python
        parser = tree_sitter.Parser(self.ts_language)
        tree = parser.parse(content.encode('utf8'))

        # Single-pass traversal that handles everything
        context = TraversalContext(
            content=content,
```

改為:

```python
        parser = tree_sitter.Parser(self.ts_language)
        content_bytes = content.encode('utf8')
        tree = parser.parse(content_bytes)

        # Single-pass traversal that handles everything
        context = TraversalContext(
            content_bytes=content_bytes,
```

- [ ] **Step 4: 修改 `TraversalContext`(L465-493)**

建構子參數 `content: str` 改為 `content_bytes: bytes`,`self.content = content` 改為 `self.content_bytes = content_bytes`。其餘欄位不動。

- [ ] **Step 5: 改寫 15 處切片與 5 個 helper**

(a) 5 個 helper 簽名與內文(L432-462),完整替換為:

```python
    def _get_function_name(self, node, content_bytes: bytes) -> Optional[str]:
        """Extract function name from tree-sitter node."""
        for child in node.children:
            if child.type == 'identifier':
                return self._slice_bytes(content_bytes, child.start_byte, child.end_byte)
        return None

    def _get_class_name(self, node, content_bytes: bytes) -> Optional[str]:
        """Extract class name from tree-sitter node."""
        for child in node.children:
            if child.type == 'identifier':
                return self._slice_bytes(content_bytes, child.start_byte, child.end_byte)
        return None

    def _get_interface_name(self, node, content_bytes: bytes) -> Optional[str]:
        """Extract interface name from tree-sitter node."""
        for child in node.children:
            if child.type == 'type_identifier':
                return self._slice_bytes(content_bytes, child.start_byte, child.end_byte)
        return None

    def _get_method_name(self, node, content_bytes: bytes) -> Optional[str]:
        """Extract method name from tree-sitter node."""
        for child in node.children:
            if child.type == 'property_identifier':
                return self._slice_bytes(content_bytes, child.start_byte, child.end_byte)
        return None

    def _get_ts_function_signature(self, node, content_bytes: bytes) -> str:
        """Extract TypeScript function signature."""
        return self._slice_bytes(content_bytes, node.start_byte, node.end_byte).split('\n')[0].strip()
```

(b) helper 的 5 個呼叫點,`context.content` 改 `context.content_bytes`:
- L84 `self._get_function_name(node, context.content_bytes)`
- L87 `self._get_ts_function_signature(node, context.content_bytes)`
- L108 `self._get_class_name(node, context.content_bytes)`
- L129 `self._get_interface_name(node, context.content_bytes)`
- L150 `self._get_method_name(node, context.content_bytes)`、L154 `self._get_ts_function_signature(node, context.content_bytes)`

(c) 直接切片的 10 處,統一模式 `context.content[X.start_byte:X.end_byte]` → `self._slice_bytes(context.content_bytes, X.start_byte, X.end_byte)`:

| 行(原始) | 原式 | 新式 |
|---|---|---|
| L200 | `name = context.content[name_node.start_byte:name_node.end_byte]` | `name = self._slice_bytes(context.content_bytes, name_node.start_byte, name_node.end_byte)` |
| L202 | `signature = context.content[child.start_byte:child.end_byte].split('\n')[0].strip()` | `signature = self._slice_bytes(context.content_bytes, child.start_byte, child.end_byte).split('\n')[0].strip()` |
| L240 | `import_text = context.content[node.start_byte:node.end_byte]` | `import_text = self._slice_bytes(context.content_bytes, node.start_byte, node.end_byte)` |
| L245 | `export_text = context.content[node.start_byte:node.end_byte]` | `export_text = self._slice_bytes(context.content_bytes, node.start_byte, node.end_byte)` |
| L297 | `return context.content[node.start_byte:node.end_byte]` | `return self._slice_bytes(context.content_bytes, node.start_byte, node.end_byte)` |
| L309 | `property_name = context.content[property_node.start_byte:property_node.end_byte]` | `property_name = self._slice_bytes(context.content_bytes, property_node.start_byte, property_node.end_byte)` |
| L346 | `return context.content[function_node.start_byte:function_node.end_byte]` | `return self._slice_bytes(context.content_bytes, function_node.start_byte, function_node.end_byte)` |
| L358 | `property_name = context.content[property_node.start_byte:property_node.end_byte]` | `property_name = self._slice_bytes(context.content_bytes, property_node.start_byte, property_node.end_byte)` |
| L396 | `return context.content[node.start_byte:node.end_byte]` | `return self._slice_bytes(context.content_bytes, node.start_byte, node.end_byte)` |
| L425 | `property_name = context.content[property_node.start_byte:property_node.end_byte]` | `property_name = self._slice_bytes(context.content_bytes, property_node.start_byte, property_node.end_byte)` |

- [ ] **Step 6: 驗證檔內不再殘留 str 切片**

```bash
grep -n "context\.content\b" src/code_index_mcp/indexing/strategies/typescript_strategy.py
```

預期:0 筆輸出(只剩 `context.content_bytes`)。

- [ ] **Step 7: 確認測試通過(新測 + 全套)**

```bash
venv/bin/pytest tests/strategies/test_typescript_non_ascii.py -v && venv/bin/pytest tests/ -q
```

預期:新測 3 項 PASS;全套與 Task 1 Step 2 的基線一致。

- [ ] **Step 8: Commit**

```bash
git add tests/strategies/test_typescript_non_ascii.py src/code_index_mcp/indexing/strategies/typescript_strategy.py
git commit -m "fix: slice parsed bytes instead of str in TypeScript strategy (#88)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: JavaScript 策略(3 處 + 集中管道 `_get_node_text`)

**Files:**
- Create: `tests/strategies/test_javascript_non_ascii.py`
- Modify: `src/code_index_mcp/indexing/strategies/javascript_strategy.py`

**Interfaces:**
- Consumes: `self._slice_bytes`(Task 1)
- Produces: `_traverse_js_node` 與其下游所有私有 helper 的 `content: str` 參數改名改型為 `content_bytes: bytes`。外部介面 `parse_file` 不變。

JS 沒有 context class,`content` 是一路以參數傳遞;檔內對 `content` 的用途**只有** byte 切片(集中在 `_get_node_text`、`_get_js_function_signature`、L227)與轉傳,`splitlines()` 只在 `parse_file` 用原始 str。因此做法是把整條傳遞鏈的參數換成 bytes。

- [ ] **Step 1: 寫失敗測試**

建立 `tests/strategies/test_javascript_non_ascii.py`,完整內容:

```python
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
    assert uni_names["shout"].signature == "shout = () => greet();"
    assert "greet" in uni_info.symbols["functions"]
```

注意:`shout` 的簽名斷言值先跑 ASCII 版確認實際輸出後若不同,以 ASCII 版實際輸出為準修改斷言(雙胞胎相等斷言才是核心;精確值斷言只是防止兩邊一起壞)。

- [ ] **Step 2: 確認測試失敗**

```bash
venv/bin/pytest tests/strategies/test_javascript_non_ascii.py -v
```

預期:FAIL,unicode 版符號名亂碼。

- [ ] **Step 3: 修改 `parse_file`(L41-56)**

```python
        parser = tree_sitter.Parser(self.js_language)
        content_bytes = content.encode('utf8')
        tree = parser.parse(content_bytes)
        self._traverse_js_node(
            tree.root_node,
            content_bytes,
            file_path,
            ...
```

(其餘引數照舊;`line_count=len(content.splitlines())` 不動,繼續用 str。)

- [ ] **Step 4: 全檔參數改名改型**

對 `javascript_strategy.py` 做機械式替換——所有函式簽名中的 `content: str` 改 `content_bytes: bytes`,函式體內對該參數的引用 `content` 改 `content_bytes`(**除了** `parse_file` 裡的原始 `content: str` 參數與 `splitlines()` 那行)。受影響的函式:`_traverse_js_node`、`_collect_callback_arguments`(L355,收 `content: str` 並轉傳)、`_get_function_name`、`_get_class_name`、`_get_method_name`、`_find_parent_class`、`_get_js_function_signature`、`_get_node_text`、`_infer_expression_type`、`_resolve_called_function`、`_resolve_argument_reference`、`_resolve_member_qualifier`(以 grep 實際簽名為準,凡收 `content` 的私有方法一律改)。

三個真正切片的位置改為:

```python
    # L227(變數宣告簽名)
    signature = self._slice_bytes(content_bytes, child.start_byte, child.end_byte).split('\n')[0].strip()

    # L476-478
    def _get_js_function_signature(self, node, content_bytes: bytes) -> str:
        """Extract JavaScript function signature."""
        return self._slice_bytes(content_bytes, node.start_byte, node.end_byte).split('\n')[0].strip()

    # L480-481
    def _get_node_text(self, node, content_bytes: bytes) -> str:
        return self._slice_bytes(content_bytes, node.start_byte, node.end_byte)
```

- [ ] **Step 5: 驗證無殘留**

```bash
grep -n "content\[" src/code_index_mcp/indexing/strategies/javascript_strategy.py; grep -cn "content: str" src/code_index_mcp/indexing/strategies/javascript_strategy.py
```

預期:第一個 grep 0 筆;第二個只剩 1 筆(`parse_file` 的簽名)。

- [ ] **Step 6: 確認測試通過**

```bash
venv/bin/pytest tests/strategies/test_javascript_non_ascii.py tests/ -q
```

預期:全 PASS(基線不變)。

- [ ] **Step 7: Commit**

```bash
git add tests/strategies/test_javascript_non_ascii.py src/code_index_mcp/indexing/strategies/javascript_strategy.py
git commit -m "fix: slice parsed bytes instead of str in JavaScript strategy (#88)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Java 策略(7 處)

**Files:**
- Create: `tests/strategies/test_java_non_ascii.py`
- Modify: `src/code_index_mcp/indexing/strategies/java_strategy.py`

**Interfaces:**
- Consumes: `self._slice_bytes`(Task 1)
- Produces: java 的 `TraversalContext.content` 換成 `content_bytes: bytes`;5 個私有 helper 參數同步換型。外部介面 `parse_file` 不變。

- [ ] **Step 1: 寫失敗測試**

建立 `tests/strategies/test_java_non_ascii.py`,完整內容:

```python
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
```

- [ ] **Step 2: 確認測試失敗**

```bash
venv/bin/pytest tests/strategies/test_java_non_ascii.py -v
```

預期:FAIL,unicode 版 package/import/符號名亂碼。

- [ ] **Step 3: 修改 `parse_file`(L39-59)**

```python
        parser = tree_sitter.Parser(self.java_language)

        try:
            content_bytes = content.encode('utf8')
            tree = parser.parse(content_bytes)

            # Extract package info first
            for node in tree.root_node.children:
                if node.type == 'package_declaration':
                    package = self._extract_java_package(node, content_bytes)
                    break

            # Single-pass traversal that handles everything
            context = TraversalContext(
                content_bytes=content_bytes,
                ...
```

- [ ] **Step 4: `TraversalContext`(L200-211)`content` → `content_bytes: bytes`**

- [ ] **Step 5: 改寫 7 處 + helper 簽名**

helper 全部改收 `content_bytes: bytes` 並用 `self._slice_bytes`:

```python
    def _get_java_class_name(self, node, content_bytes: bytes) -> Optional[str]:
        for child in node.children:
            if child.type == 'identifier':
                return self._slice_bytes(content_bytes, child.start_byte, child.end_byte)
        return None

    def _get_java_method_name(self, node, content_bytes: bytes) -> Optional[str]:
        for child in node.children:
            if child.type == 'identifier':
                return self._slice_bytes(content_bytes, child.start_byte, child.end_byte)
        return None

    def _get_java_method_signature(self, node, content_bytes: bytes) -> str:
        return self._slice_bytes(content_bytes, node.start_byte, node.end_byte).split('\n')[0].strip()

    def _extract_java_package(self, node, content_bytes: bytes) -> Optional[str]:
        for child in node.children:
            if child.type == 'scoped_identifier':
                return self._slice_bytes(content_bytes, child.start_byte, child.end_byte)
        return None

    def _get_called_method_name(self, node, content_bytes: bytes) -> Optional[str]:
        """Extract called method name from method invocation node."""
        for child in node.children:
            if child.type == 'field_access':
                for subchild in child.children:
                    if subchild.type == 'identifier' and subchild.start_byte > child.start_byte:
                        return self._slice_bytes(content_bytes, subchild.start_byte, subchild.end_byte)
            elif child.type == 'identifier':
                return self._slice_bytes(content_bytes, child.start_byte, child.end_byte)
        return None
```

呼叫點:L83、L103、L117、L133 的 `context.content` → `context.content_bytes`;L152 改:

```python
            import_text = self._slice_bytes(context.content_bytes, node.start_byte, node.end_byte)
```

- [ ] **Step 6: 驗證 + 測試**

```bash
grep -n "context\.content\b" src/code_index_mcp/indexing/strategies/java_strategy.py
venv/bin/pytest tests/strategies/test_java_non_ascii.py tests/ -q
```

預期:grep 0 筆;測試全 PASS。

- [ ] **Step 7: Commit**

```bash
git add tests/strategies/test_java_non_ascii.py src/code_index_mcp/indexing/strategies/java_strategy.py
git commit -m "fix: slice parsed bytes instead of str in Java strategy (#88)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Kotlin 策略(2 處漏網 + 慢速分支 + 去重)

**Files:**
- Create: `tests/strategies/test_kotlin_non_ascii.py`
- Modify: `src/code_index_mcp/indexing/strategies/kotlin_strategy.py`

**Interfaces:**
- Consumes: base 的 `self._slice_bytes`(Task 1)
- Produces: 刪除 kotlin 本地 `_slice_bytes`(L412-418),其呼叫全部落到 base 版(bytes-only)。`_get_kotlin_type_name` / `_extract_kotlin_import_from_node` 參數改 `content_bytes: bytes`。

行為差異說明:kotlin 舊版 `_slice_bytes` 遇 start>end 會交換再切,base 版回 `""`。tree-sitter 不會產生反向區間,且既有 `test_kotlin_discovery.py` 會守住回歸。

- [ ] **Step 1: 寫失敗測試**

建立 `tests/strategies/test_kotlin_non_ascii.py`,完整內容:

```python
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
```

(前四個雙胞胎測試可能修改前就綠——kotlin 主路徑多半已走 bytes;它們守回歸。後兩個 fallback 測試修改前**必須紅**:`_get_kotlin_function_name` 的 header fallback(L218)與 `_get_kotlin_function_signature` 的 snippet fallback(L227)都還在用 str 切片,unicode 註解造成的 +13 bytes 偏移會讓斷言失敗。若 `test_function_signature_fallback_survives_unicode` 因 grammar 差異找不到 `function_declaration` 節點,改用實際的節點型別名(以 `tree.root_node` 印出的 sexp 為準),不可刪測試。)

- [ ] **Step 2: 確認 fallback 測試失敗**

```bash
venv/bin/pytest tests/strategies/test_kotlin_non_ascii.py -v
```

預期:`test_function_name_header_fallback_survives_unicode` 與 `test_function_signature_fallback_survives_unicode` FAIL(名稱/簽名被 +13 bytes 偏移弄壞);前四個雙胞胎測試綠紅皆可,記下結果。

- [ ] **Step 3: 修改四個位置 + 刪本地 helper**

(a) L93:`self._get_kotlin_type_name(node, context.content)` → `self._get_kotlin_type_name(node, context.content_bytes)`
(b) L152:`self._extract_kotlin_import_from_node(node, context.content)` → `self._extract_kotlin_import_from_node(node, context.content_bytes)`
(c) 兩個 helper 簽名(L186、L230)`content: str` → `content_bytes: bytes`,內文 `self._slice_bytes(content, ...)` → `self._slice_bytes(content_bytes, ...)`
(d) L218:

```python
        header = self._slice_bytes(context.content_bytes, node.start_byte, node.end_byte).split("\n", 1)[0]
```

(e) L227:

```python
        snippet = self._slice_bytes(context.content_bytes, node.start_byte, node.end_byte)
```

(f) 刪除 L412-418 的本地 `def _slice_bytes(...)` 整個方法。

- [ ] **Step 4: 驗證 + 測試**

```bash
grep -n "def _slice_bytes" src/code_index_mcp/indexing/strategies/kotlin_strategy.py
grep -n "context\.content\[" src/code_index_mcp/indexing/strategies/kotlin_strategy.py
venv/bin/pytest tests/strategies/test_kotlin_non_ascii.py tests/strategies/test_kotlin_discovery.py tests/ -q
```

預期:兩個 grep 都 0 筆;測試全 PASS(尤其既有 `test_kotlin_discovery.py`)。

- [ ] **Step 5: Commit**

```bash
git add tests/strategies/test_kotlin_non_ascii.py src/code_index_mcp/indexing/strategies/kotlin_strategy.py
git commit -m "fix: route Kotlin fallback slices through byte-safe helper (#88)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Zig 策略(3 處文字 + 2 處行號)+ 刪除 base 舊 helper

**Files:**
- Create: `tests/strategies/test_zig_non_ascii.py`
- Modify: `src/code_index_mcp/indexing/strategies/zig_strategy.py`
- Modify: `src/code_index_mcp/indexing/strategies/base_strategy.py`(刪 `_safe_extract_text` L86-91、`_extract_line_number` L69-80)

**Interfaces:**
- Consumes: `self._slice_bytes`(Task 1)
- Produces: 全 repo 不再有 `_safe_extract_text` / `_extract_line_number`(成功標準第 4 條)。

- [ ] **Step 1: 寫失敗測試(含行號斷言)**

建立 `tests/strategies/test_zig_non_ascii.py`,完整內容:

```python
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
```

- [ ] **Step 2: 確認測試失敗**

```bash
venv/bin/pytest tests/strategies/test_zig_non_ascii.py -v
```

預期:FAIL——unicode 版名稱亂碼(`lePause(` 之類)且 `togglePause` 缺失或行號錯。

- [ ] **Step 3: 修改 `zig_strategy.py`**

(a) L40-44:

```python
        parser = tree_sitter.Parser(self.zig_language)
        content_bytes = content.encode('utf8')
        tree = parser.parse(content_bytes)

        # Phase 1: Extract symbols using tree-sitter
        self._traverse_zig_node(tree.root_node, content_bytes, file_path, symbols, functions, classes, imports)
```

(b) `_traverse_zig_node` 簽名:`content: str` → `content_bytes: bytes`;內文:

```python
    def _traverse_zig_node(self, node, content_bytes: bytes, file_path: str, symbols: Dict, functions: List, classes: List, imports: List):
        """Traverse Zig AST node and extract symbols."""
        if node.type == 'function_declaration':
            func_name = self._extract_zig_function_name_from_node(node, content_bytes)
            if func_name:
                line_number = node.start_point[0] + 1
                symbol_id = self._create_symbol_id(file_path, func_name)
                symbols[symbol_id] = SymbolInfo(
                    type="function",
                    file=file_path,
                    line=line_number,
                    end_line=node.end_point[0] + 1,
                    signature=self._slice_bytes(content_bytes, node.start_byte, node.end_byte)
                )
                functions.append(func_name)

        elif node.type in ['struct_declaration', 'union_declaration', 'enum_declaration']:
            type_name = self._extract_zig_type_name_from_node(node, content_bytes)
            if type_name:
                line_number = node.start_point[0] + 1
                symbol_id = self._create_symbol_id(file_path, type_name)
                symbols[symbol_id] = SymbolInfo(
                    type=node.type.replace('_declaration', ''),
                    file=file_path,
                    line=line_number,
                    end_line=node.end_point[0] + 1
                )
                classes.append(type_name)

        # Recurse through children
        for child in node.children:
            self._traverse_zig_node(child, content_bytes, file_path, symbols, functions, classes, imports)

    def _extract_zig_function_name_from_node(self, node, content_bytes: bytes) -> Optional[str]:
        """Extract function name from tree-sitter node."""
        for child in node.children:
            if child.type == 'identifier':
                return self._slice_bytes(content_bytes, child.start_byte, child.end_byte)
        return None

    def _extract_zig_type_name_from_node(self, node, content_bytes: bytes) -> Optional[str]:
        """Extract type name from tree-sitter node."""
        for child in node.children:
            if child.type == 'identifier':
                return self._slice_bytes(content_bytes, child.start_byte, child.end_byte)
        return None
```

(zig 的 `.strip()` 差異:舊 `_safe_extract_text` 會 strip,新 `_slice_bytes` 不會;identifier 與 signature 節點邊界本身不含空白,行為等價。)

- [ ] **Step 4: 刪除 base 舊 helper**

刪除 `base_strategy.py` 的 `_extract_line_number`(L69-80)與 `_safe_extract_text`(L86-91)兩個方法。

- [ ] **Step 5: 驗證全 repo 無殘留呼叫**

```bash
grep -rn "_safe_extract_text\|_extract_line_number" src/ tests/
```

預期:0 筆。

- [ ] **Step 6: 確認測試通過**

```bash
venv/bin/pytest tests/strategies/test_zig_non_ascii.py tests/ -q
```

預期:全 PASS。

- [ ] **Step 7: Commit**

```bash
git add tests/strategies/test_zig_non_ascii.py src/code_index_mcp/indexing/strategies/zig_strategy.py src/code_index_mcp/indexing/strategies/base_strategy.py
git commit -m "fix: byte-safe Zig extraction, native line numbers, drop unsafe base helpers (#88)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: 最終驗證掃描(spec 成功標準)

**Files:** 無新增修改(只驗證;若掃出殘留則回頭補修並歸入對應語言的 commit 風格)

- [ ] **Step 1: 成功標準 3——全 repo 無 str byte 切片殘留**

```bash
grep -rnE "content\[[a-z_]+\.(start|end)_byte" src/code_index_mcp/indexing/strategies/
```

預期:0 筆。(csharp/rust 的 `content_bytes[...]`、kotlin 的 `_extract_word_token_bytes` 為 bytes 切片,不會被此 pattern 命中;若命中任何 `\.content\[` 或裸 `content[`,即為漏網,回對應 task 補修。)

- [ ] **Step 2: 成功標準 4——舊 helper 歸零**

```bash
grep -rn "_safe_extract_text\|_extract_line_number" src/ tests/
```

預期:0 筆。

- [ ] **Step 3: 成功標準 1、2——全套測試**

```bash
venv/bin/pytest tests/ -q
```

預期:exit code 0、全 PASS,含 6 個新測試檔(base、ts、js、java、kotlin、zig)與全部既有測試;對照 Task 1 Step 2 基線無新增失敗。(不要把 pytest 接進管線——沒有 pipefail 時 exit code 會被管線尾端指令蓋掉。)

- [ ] **Step 4: 檢視 diff 總覽並確認範圍**

```bash
git log --oneline master..HEAD
git diff master --stat
```

預期:8 個 commit(spec 1 + 計畫 1 + 修復 6);變更檔案僅限 `docs/superpowers/`、`tests/strategies/`、`src/code_index_mcp/indexing/strategies/{base,typescript,javascript,java,kotlin,zig}_strategy.py`。

---

## 附註(給執行者)

- **不要動** `csharp_strategy.py` 的本地 `_slice_bytes`(L497):它的語意與 base 版不同(越界回 `""` 而非 clamp),是刻意保留的。
- 各 task 中的行號是 master @ `5e8d5fc` 的行號,改到後面行號會漂移——以 pattern 為準,行號只是導航。
- 若 `tree_sitter_zig` / `tree_sitter_kotlin` 等套件在 pip install 時失敗,先確認 wheel 支援 macOS arm64 + Python 3.12;必要時改用 `/opt/homebrew/opt/python@3.13/bin/python3.13` 重建 venv。
- 測試中的精確值斷言(簽名字串)若與 grammar 版本有出入,以 **ASCII 雙胞胎的實際輸出**為準調整;雙胞胎相等斷言不可放寬。
