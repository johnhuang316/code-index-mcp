"""
Kotlin parsing strategy using tree-sitter - single-pass optimized version.
"""

import logging
import re
from typing import Dict, List, Tuple, Optional, Set

import tree_sitter
from tree_sitter_kotlin import language

from .base_strategy import ParsingStrategy
from ..models import SymbolInfo, FileInfo

logger = logging.getLogger(__name__)


class KotlinParsingStrategy(ParsingStrategy):
    """Kotlin-specific parsing strategy - single pass optimized."""

    def __init__(self):
        self.kotlin_language = tree_sitter.Language(language())

    def get_language_name(self) -> str:
        return "kotlin"

    def get_supported_extensions(self) -> List[str]:
        return [".kt", ".kts"]

    def parse_file(self, file_path: str, content: str) -> Tuple[Dict[str, SymbolInfo], FileInfo]:
        """Parse Kotlin file using tree-sitter with single-pass optimization."""
        symbols: Dict[str, SymbolInfo] = {}
        functions: List[str] = []
        classes: List[str] = []
        imports: List[str] = []
        package: Optional[str] = None

        symbol_lookup: Dict[str, str] = {}
        pending_calls: List[Tuple[str, str]] = []
        pending_call_set: Set[Tuple[str, str]] = set()

        content_bytes = content.encode("utf8")
        parser = tree_sitter.Parser(self.kotlin_language)

        try:
            tree = parser.parse(content_bytes)

            package = self._extract_kotlin_package_fallback(content)
            imports.extend(self._extract_kotlin_imports_fallback(content))

            context = TraversalContext(
                content=content,
                content_bytes=content_bytes,
                lines=content.splitlines(),
                file_path=file_path,
                symbols=symbols,
                functions=functions,
                classes=classes,
                imports=imports,
                symbol_lookup=symbol_lookup,
                pending_calls=pending_calls,
                pending_call_set=pending_call_set,
            )

            self._traverse_node_single_pass(tree.root_node, context)

        except Exception as e:
            logger.warning(f"Error parsing Kotlin file {file_path}: {e}")

        file_info = FileInfo(
            language=self.get_language_name(),
            line_count=len(content.splitlines()),
            symbols={"functions": functions, "classes": classes},
            imports=imports,
            package=package,
        )

        if pending_calls:
            file_info.pending_calls = pending_calls

        return symbols, file_info

    def _traverse_node_single_pass(
        self,
        node,
        context: "TraversalContext",
        current_class: Optional[str] = None,
        current_function: Optional[str] = None,
    ) -> None:
        node_type = node.type

        if node_type in {"class_declaration", "object_declaration", "interface_declaration"}:
            name = self._get_kotlin_type_name(node, context.content)
            if name:
                symbol_id = self._create_symbol_id(context.file_path, name)
                symbol_kind = "interface" if node_type == "interface_declaration" else "class"
                context.symbols[symbol_id] = SymbolInfo(
                    type=symbol_kind,
                    file=context.file_path,
                    line=node.start_point[0] + 1,
                )
                context.symbol_lookup[name] = symbol_id
                context.classes.append(name)

                for child in node.children:
                    self._traverse_node_single_pass(
                        child,
                        context,
                        current_class=name,
                        current_function=current_function,
                    )
                return

        if node_type == "function_declaration":
            name = self._get_kotlin_function_name(node, context)
            if name:
                if current_class:
                    full_name = f"{current_class}.{name}"
                    symbol_kind = "method"
                else:
                    full_name = name
                    symbol_kind = "function"

                symbol_id = self._create_symbol_id(context.file_path, full_name)
                context.symbols[symbol_id] = SymbolInfo(
                    type=symbol_kind,
                    file=context.file_path,
                    line=node.start_point[0] + 1,
                    signature=self._get_kotlin_function_signature(node, context),
                )
                context.symbol_lookup[full_name] = symbol_id
                context.symbol_lookup[name] = symbol_id
                context.functions.append(full_name)

                for child in node.children:
                    self._traverse_node_single_pass(
                        child,
                        context,
                        current_class=current_class,
                        current_function=symbol_id,
                    )
                return

        if node_type == "call_expression" and current_function:
            called = self._get_called_function_name(node, context.content_bytes)
            if called:
                self._register_call(context, current_function, called)

        if node_type in {"import_header", "import_declaration"}:
            import_path = self._extract_kotlin_import_from_node(node, context.content)
            if import_path and import_path not in context.imports:
                context.imports.append(import_path)

        for child in node.children:
            self._traverse_node_single_pass(
                child,
                context,
                current_class=current_class,
                current_function=current_function,
            )

    def _register_call(self, context: "TraversalContext", caller: str, called: str) -> None:
        if called in context.symbol_lookup:
            symbol_id = context.symbol_lookup[called]
            symbol_info = context.symbols.get(symbol_id)
            if symbol_info and caller not in symbol_info.called_by:
                symbol_info.called_by.append(caller)
            return

        # Try matching declared methods like "Class.method"
        suffix = f".{called}"
        matches = [sid for name, sid in context.symbol_lookup.items() if name.endswith(suffix)]
        if len(matches) == 1:
            symbol_info = context.symbols.get(matches[0])
            if symbol_info and caller not in symbol_info.called_by:
                symbol_info.called_by.append(caller)
            return

        key = (caller, called)
        if key not in context.pending_call_set:
            context.pending_call_set.add(key)
            context.pending_calls.append(key)

    def _get_kotlin_type_name(self, node, content: str) -> Optional[str]:
        for child in node.children:
            if child.type in {"type_identifier", "simple_identifier", "identifier"}:
                return self._clean_identifier(self._slice_bytes(content, child.start_byte, child.end_byte))
        return None

    def _get_kotlin_function_name(self, node, context: "TraversalContext") -> Optional[str]:
        # Prefer AST field navigation (fast path).
        try:
            name_node = node.child_by_field_name("name")
        except Exception:
            name_node = None

        expected_from_line: Optional[str] = None
        if 0 <= node.start_point[0] < len(context.lines):
            expected_from_line = self._extract_fun_name_from_line(context.lines[node.start_point[0]])

        if name_node is not None:
            raw = self._slice_bytes(context.content_bytes, name_node.start_byte, name_node.end_byte)
            cleaned = self._clean_identifier(raw)
            if cleaned:
                if expected_from_line and expected_from_line != cleaned:
                    return expected_from_line
                if expected_from_line:
                    return cleaned
                if self._identifier_is_plausible_in_declaration_line(node, context, cleaned):
                    return cleaned

        # Fallback (rare): derive from the declaration line/header when the tree is malformed.
        if expected_from_line:
            return expected_from_line

        header = context.content[node.start_byte : node.end_byte].split("\n", 1)[0]
        expected_from_header = self._extract_fun_name_from_line(header)
        if expected_from_header:
            return expected_from_header
        return None

    def _get_kotlin_function_signature(self, node, context: "TraversalContext") -> str:
        if 0 <= node.start_point[0] < len(context.lines):
            return context.lines[node.start_point[0]].strip()
        snippet = context.content[node.start_byte : node.end_byte]
        return snippet.split("\n", 1)[0].strip()

    def _extract_kotlin_import_from_node(self, node, content: str) -> Optional[str]:
        text = self._slice_bytes(content, node.start_byte, node.end_byte).strip()
        if not text.startswith("import"):
            return None
        text = text[len("import") :].strip()
        # Drop alias: "import a.b.C as D"
        text = re.split(r"\s+as\s+", text, maxsplit=1)[0].strip()
        return text or None

    def _extract_kotlin_package_fallback(self, content: str) -> Optional[str]:
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("package "):
                match = re.match(r"package\s+([A-Za-z0-9_\\.]+)", stripped)
                return match.group(1) if match else None
            if stripped and not stripped.startswith(("//", "/*", "*")):
                # Stop scanning once code starts.
                break
        return None

    def _extract_kotlin_imports_fallback(self, content: str) -> List[str]:
        results: List[str] = []
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("import "):
                value = stripped[len("import") :].strip()
                value = re.split(r"\s+as\s+", value, maxsplit=1)[0].strip()
                if value:
                    results.append(value)
                continue
            if stripped.startswith("package "):
                continue
            if stripped and not stripped.startswith(("//", "/*", "*")):
                # Stop scanning once code starts.
                break
        # Preserve order, remove duplicates
        deduped: List[str] = []
        seen: Set[str] = set()
        for item in results:
            if item not in seen:
                seen.add(item)
                deduped.append(item)
        return deduped

    def _get_called_function_name(self, node, content: str) -> Optional[str]:
        callee_node = self._get_call_expression_callee(node)
        if callee_node is None:
            return None

        identifiers = self._collect_identifiers_from_callee(callee_node, content)
        if not identifiers:
            return None

        called = self._normalize_called_identifier(identifiers)
        if called in {"_", "as", "else", "for", "fun", "if", "in", "is", "override", "return", "val", "var", "when", "while"}:
            return None
        return called

    def _clean_identifier(self, raw: str) -> Optional[str]:
        if not raw:
            return None
        cleaned = raw.strip()
        # Remove trailing punctuation/braces that can appear in malformed nodes
        cleaned = re.split(r"[^A-Za-z0-9_]+", cleaned, maxsplit=1)[0]
        return cleaned or None

    def _identifier_is_plausible_in_declaration_line(
        self,
        node,
        context: "TraversalContext",
        identifier: str,
    ) -> bool:
        if not (0 <= node.start_point[0] < len(context.lines)):
            return True
        line_text = context.lines[node.start_point[0]]
        if "fun" not in line_text:
            return True
        fun_index = line_text.find("fun")
        name_index = line_text.find(identifier)
        return name_index != -1 and name_index > fun_index

    def _get_call_expression_callee(self, call_node):
        # Kotlin call_expression named children typically look like:
        # - identifier + value_arguments
        # - navigation_expression + value_arguments
        # Prefer the first named child that isn't the arguments/suffix.
        for child in getattr(call_node, "named_children", []) or []:
            if child.type in {"value_arguments", "lambda_literal", "type_arguments"}:
                continue
            return child
        return None

    def _collect_identifiers_from_callee(self, node, content: str) -> List[str]:
        # Walk the callee subtree left-to-right and collect only identifier-ish nodes.
        identifiers: List[str] = []
        stack: List = [(node, 0)]

        content_bytes = content if isinstance(content, (bytes, bytearray)) else content.encode("utf8")
        while stack:
            current, child_index = stack.pop()
            if child_index == 0 and current.type in {"identifier", "simple_identifier", "type_identifier"}:
                raw = self._extract_word_token_bytes(content_bytes, current.start_byte, current.end_byte)
                cleaned = self._clean_identifier(raw.decode("utf8", errors="ignore"))
                if cleaned:
                    identifiers.append(cleaned)
                continue

            children = getattr(current, "named_children", None)
            if children is None:
                children = []

            if child_index < len(children):
                stack.append((current, child_index + 1))
                stack.append((children[child_index], 0))

        return identifiers

    def _normalize_called_identifier(self, identifiers: List[str]) -> str:
        # Prefer either "Type.method" (static/companion-like) or "method".
        if len(identifiers) == 1:
            return identifiers[0]
        if identifiers[-2][:1].isupper():
            return f"{identifiers[-2]}.{identifiers[-1]}"
        return identifiers[-1]

    def _extract_fun_name_from_line(self, line_text: str) -> Optional[str]:
        text = line_text.strip()
        fun_index = text.find("fun")
        if fun_index == -1:
            return None

        i = fun_index + 3
        while i < len(text) and text[i].isspace():
            i += 1

        # Skip type parameters: fun <T> name(...)
        if i < len(text) and text[i] == "<":
            depth = 0
            while i < len(text):
                ch = text[i]
                if ch == "<":
                    depth += 1
                elif ch == ">":
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                i += 1
            while i < len(text) and text[i].isspace():
                i += 1

        # Backticked identifiers: fun `when`(...)
        if i < len(text) and text[i] == "`":
            i += 1
            end = text.find("`", i)
            if end != -1:
                return text[i:end]
            return None

        start = i
        while i < len(text) and (text[i].isalnum() or text[i] == "_"):
            i += 1
        name = text[start:i]
        return name or None

    def _extract_word_token_bytes(self, content_bytes: bytes, start: int, end: int) -> bytes:
        # Some malformed trees yield truncated identifier spans; extend to word boundaries.
        start = max(0, min(start, len(content_bytes)))
        end = max(0, min(end, len(content_bytes)))
        if end < start:
            start, end = end, start

        while start > 0 and (
            chr(content_bytes[start - 1]).isalnum() or content_bytes[start - 1] == ord("_")
        ):
            start -= 1
        while end < len(content_bytes) and (
            chr(content_bytes[end]).isalnum() or content_bytes[end] == ord("_")
        ):
            end += 1
        return content_bytes[start:end]

    def _slice_bytes(self, content_or_bytes, start: int, end: int) -> str:
        data = content_or_bytes if isinstance(content_or_bytes, (bytes, bytearray)) else content_or_bytes.encode("utf8")
        start = max(0, min(start, len(data)))
        end = max(0, min(end, len(data)))
        if end < start:
            start, end = end, start
        return data[start:end].decode("utf8", errors="ignore")


class TraversalContext:
    """Context object to pass state during single-pass traversal."""

    def __init__(
        self,
        content: str,
        content_bytes: bytes,
        lines: List[str],
        file_path: str,
        symbols: Dict[str, SymbolInfo],
        functions: List[str],
        classes: List[str],
        imports: List[str],
        symbol_lookup: Dict[str, str],
        pending_calls: List[Tuple[str, str]],
        pending_call_set: Set[Tuple[str, str]],
    ):
        self.content = content
        self.content_bytes = content_bytes
        self.lines = lines
        self.file_path = file_path
        self.symbols = symbols
        self.functions = functions
        self.classes = classes
        self.imports = imports
        self.symbol_lookup = symbol_lookup
        self.pending_calls = pending_calls
        self.pending_call_set = pending_call_set
