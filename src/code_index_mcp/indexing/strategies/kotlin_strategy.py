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

        parser = tree_sitter.Parser(self.kotlin_language)

        try:
            tree = parser.parse(content.encode("utf8"))

            package = self._extract_kotlin_package_fallback(content)
            imports.extend(self._extract_kotlin_imports_fallback(content))

            context = TraversalContext(
                content=content,
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
            called = self._get_called_function_name(node, context.content)
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
                return self._clean_identifier(content[child.start_byte : child.end_byte])
        return None

    def _get_kotlin_function_name(self, node, context: "TraversalContext") -> Optional[str]:
        # Prefer line-based parsing to avoid malformed spans in error nodes.
        if 0 <= node.start_point[0] < len(context.lines):
            line_text = context.lines[node.start_point[0]]
            match = re.search(r"fun\s+([A-Za-z_][\w]*)", line_text)
            if match:
                return match.group(1)

        # Fallback to AST child extraction.
        for child in node.children:
            if child.type in {"simple_identifier", "identifier"}:
                return self._clean_identifier(context.content[child.start_byte : child.end_byte])

        # Fallback: regex from the declaration header
        header = context.content[node.start_byte : node.end_byte].split("\n", 1)[0]
        match = re.search(r"fun\s+([A-Za-z_][\w]*)", header)
        if match:
            return match.group(1)
        return None

    def _get_kotlin_function_signature(self, node, context: "TraversalContext") -> str:
        if 0 <= node.start_point[0] < len(context.lines):
            return context.lines[node.start_point[0]].strip()
        snippet = context.content[node.start_byte : node.end_byte]
        return snippet.split("\n", 1)[0].strip()

    def _extract_kotlin_import_from_node(self, node, content: str) -> Optional[str]:
        text = content[node.start_byte : node.end_byte].strip()
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
        start = max(0, node.start_byte - 16)  # include small prefix to avoid truncated names
        snippet = content[start : node.end_byte]
        snippet = " ".join(snippet.split())
        matches = re.findall(r"([A-Za-z_][\w\\.]*)(?:<[^>]*>)?\s*\(", snippet)
        if matches:
            candidate = max(matches, key=len)
            if candidate in {"if", "for", "while", "when"}:
                return None
            return candidate
        return None

    def _clean_identifier(self, raw: str) -> Optional[str]:
        if not raw:
            return None
        cleaned = raw.strip()
        # Remove trailing punctuation/braces that can appear in malformed nodes
        cleaned = re.split(r"[^A-Za-z0-9_\\.]+", cleaned, maxsplit=1)[0]
        return cleaned or None


class TraversalContext:
    """Context object to pass state during single-pass traversal."""

    def __init__(
        self,
        content: str,
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
        self.lines = lines
        self.file_path = file_path
        self.symbols = symbols
        self.functions = functions
        self.classes = classes
        self.imports = imports
        self.symbol_lookup = symbol_lookup
        self.pending_calls = pending_calls
        self.pending_call_set = pending_call_set
