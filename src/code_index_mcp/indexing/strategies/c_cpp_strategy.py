"""C and C++ parsing strategy using tree-sitter."""

from __future__ import annotations

import logging
import re
import threading
from typing import Dict, List, Optional, Set, Tuple

import tree_sitter

from .base_strategy import ParsingStrategy
from ..models import FileInfo, SymbolInfo


logger = logging.getLogger(__name__)


class TraversalContext:
    """Traversal state for C/C++ symbol and call extraction."""

    def __init__(
        self,
        content: str,
        content_bytes: bytes,
        file_path: str,
        language_name: str,
        symbols: Dict[str, SymbolInfo],
        functions: List[str],
        classes: List[str],
        imports: List[str],
    ):
        self.content = content
        self.content_bytes = content_bytes
        self.file_path = file_path
        self.language_name = language_name
        self.symbols = symbols
        self.functions = functions
        self.classes = classes
        self.imports = imports
        self.symbol_lookup: Dict[str, str] = {}
        self.ambiguous_short_names: Set[str] = set()
        self.pending_calls: List[Tuple[str, str]] = []
        self.pending_call_set: Set[Tuple[str, str]] = set()


class CAndCppParsingStrategy(ParsingStrategy):
    """C/C++ parser. .h files are intentionally parsed as C."""

    _C_EXTENSIONS = {".c", ".h"}
    _CPP_EXTENSIONS = {".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"}
    _TYPE_NODES = {
        "struct_specifier": "struct",
        "union_specifier": "union",
        "enum_specifier": "enum",
        "class_specifier": "class",
    }
    _DECLARATOR_NODES = {
        "function_declarator",
        "pointer_declarator",
        "reference_declarator",
        "parenthesized_declarator",
        "qualified_identifier",
        "template_function",
        "destructor_name",
        "field_identifier",
        "identifier",
    }

    def __init__(self):
        from tree_sitter_c import language as c_language
        from tree_sitter_cpp import language as cpp_language

        self.c_language = tree_sitter.Language(c_language())
        self.cpp_language = tree_sitter.Language(cpp_language())
        self._parser_local = threading.local()

    def get_language_name(self) -> str:
        return "c_cpp"

    def get_supported_extensions(self) -> List[str]:
        return sorted(self._C_EXTENSIONS | self._CPP_EXTENSIONS)

    def parse_file(self, file_path: str, content: str) -> Tuple[Dict[str, SymbolInfo], FileInfo]:
        """Parse C/C++ file content and extract symbols/imports/calls."""
        symbols: Dict[str, SymbolInfo] = {}
        functions: List[str] = []
        classes: List[str] = []
        imports: List[str] = []
        language_name = self._language_for_path(file_path)

        content_bytes = content.encode("utf8")
        context = TraversalContext(
            content=content,
            content_bytes=content_bytes,
            file_path=file_path,
            language_name=language_name,
            symbols=symbols,
            functions=functions,
            classes=classes,
            imports=imports,
        )

        try:
            tree = self._get_parser(language_name).parse(content_bytes)
            self._traverse_node(
                tree.root_node,
                context=context,
                namespace_parts=[],
                type_stack=[],
                current_function=None,
            )
        except Exception as exc:  # pragma: no cover - parser errors are uncommon
            logger.warning("Error parsing %s file %s: %s", language_name, file_path, exc)

        file_info = FileInfo(
            language=language_name,
            line_count=content.count("\n") + 1,
            symbols={"functions": functions, "classes": classes},
            imports=imports,
        )
        if context.pending_calls:
            file_info.pending_calls = context.pending_calls

        return symbols, file_info

    def _get_parser(self, language_name: str) -> tree_sitter.Parser:
        attr = "c_parser" if language_name == "c" else "cpp_parser"
        parser = getattr(self._parser_local, attr, None)
        if parser is None:
            language = self.c_language if language_name == "c" else self.cpp_language
            parser = tree_sitter.Parser(language)
            setattr(self._parser_local, attr, parser)
        return parser

    def _traverse_node(
        self,
        node,
        context: TraversalContext,
        namespace_parts: List[str],
        type_stack: List[str],
        current_function: Optional[str],
    ) -> None:
        node_type = node.type

        if node_type == "preproc_include":
            include = self._extract_include(node, context)
            if include and include not in context.imports:
                context.imports.append(include)
            return

        if context.language_name == "cpp" and node_type == "namespace_definition":
            name = self._extract_name(node, context)
            next_namespace = namespace_parts + ([name] if name else [])
            body = node.child_by_field_name("body")
            children = body.children if body is not None else node.children
            for child in children:
                self._traverse_node(child, context, next_namespace, type_stack, current_function)
            return

        if node_type == "type_definition":
            if self._register_typedef_type(node, context, namespace_parts):
                return

        if node_type in self._TYPE_NODES and self._is_type_definition(node):
            type_name = self._extract_name(node, context)
            if type_name:
                qualified = self._qualify_name(namespace_parts, type_stack + [type_name])
                symbol_id = self._create_symbol_id(context.file_path, qualified)
                context.symbols[symbol_id] = SymbolInfo(
                    type=self._TYPE_NODES[node_type],
                    file=context.file_path,
                    line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                )
                self._register_lookup(context, qualified, symbol_id, allow_short_name_ambiguity=False)
                self._register_lookup(context, type_name, symbol_id, allow_short_name_ambiguity=True)
                context.classes.append(qualified)
                self._resolve_pending_calls_for_symbol(context, symbol_id)

                body = node.child_by_field_name("body")
                if body is not None:
                    for child in body.children:
                        self._traverse_node(
                            child,
                            context,
                            namespace_parts,
                            type_stack + [type_name],
                            current_function,
                        )
                    return

        if node_type == "function_definition":
            self._register_function_definition(node, context, namespace_parts, type_stack)
            symbol_id = self._symbol_id_for_function(node, context, namespace_parts, type_stack)
            if symbol_id:
                for child in node.children:
                    self._traverse_node(child, context, namespace_parts, type_stack, symbol_id)
                return

        if node_type == "declaration" and context.language_name == "cpp" and type_stack:
            # C++ methods declared inline as `void run() { ... }` can appear as declarations.
            symbol_id = self._register_inline_method_declaration(node, context, namespace_parts, type_stack)
            if symbol_id:
                for child in node.children:
                    self._traverse_node(child, context, namespace_parts, type_stack, symbol_id)
                return

        if node_type == "call_expression" and current_function:
            called = self._extract_called_name(node, context)
            if called:
                self._register_call(
                    context,
                    caller=current_function,
                    called=called,
                    unresolved_caller=f"{context.file_path}:{node.start_point[0] + 1}",
                )

        for child in node.children:
            self._traverse_node(child, context, namespace_parts, type_stack, current_function)

    def _register_function_definition(
        self,
        node,
        context: TraversalContext,
        namespace_parts: List[str],
        type_stack: List[str],
    ) -> Optional[str]:
        name = self._extract_function_name(node, context)
        if not name:
            return None

        full_name = self._qualify_function_name(name, namespace_parts, type_stack)
        symbol_id = self._create_symbol_id(context.file_path, full_name)
        symbol_type = "method" if "." in full_name and context.language_name == "cpp" else "function"
        signature = self._extract_signature(node, context)

        context.symbols[symbol_id] = SymbolInfo(
            type=symbol_type,
            file=context.file_path,
            line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            signature=signature,
        )
        self._register_function_lookups(context, full_name, symbol_id)
        context.functions.append(full_name)
        self._resolve_pending_calls_for_symbol(context, symbol_id)
        return symbol_id

    def _register_inline_method_declaration(
        self,
        node,
        context: TraversalContext,
        namespace_parts: List[str],
        type_stack: List[str],
    ) -> Optional[str]:
        if not any(child.type == "compound_statement" for child in node.children):
            return None
        declarator = node.child_by_field_name("declarator")
        if declarator is None or "function_declarator" not in self._node_type_set(declarator):
            return None
        name = self._extract_declarator_name(declarator, context)
        if not name:
            return None
        full_name = self._qualify_function_name(name, namespace_parts, type_stack)
        symbol_id = self._create_symbol_id(context.file_path, full_name)
        context.symbols[symbol_id] = SymbolInfo(
            type="method",
            file=context.file_path,
            line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            signature=self._extract_signature(node, context),
        )
        self._register_function_lookups(context, full_name, symbol_id)
        context.functions.append(full_name)
        self._resolve_pending_calls_for_symbol(context, symbol_id)
        return symbol_id

    def _register_typedef_type(
        self,
        node,
        context: TraversalContext,
        namespace_parts: List[str],
    ) -> bool:
        type_node = None
        for child in node.children:
            if child.type in self._TYPE_NODES:
                type_node = child
                break
        if type_node is None:
            return False

        alias = self._extract_typedef_alias(node, type_node, context)
        name = alias or self._extract_name(type_node, context)
        if not name:
            return False

        qualified = self._qualify_name(namespace_parts, [name])
        symbol_id = self._create_symbol_id(context.file_path, qualified)
        context.symbols[symbol_id] = SymbolInfo(
            type=self._TYPE_NODES[type_node.type],
            file=context.file_path,
            line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            signature=self._extract_signature(node, context),
        )
        self._register_lookup(context, qualified, symbol_id, allow_short_name_ambiguity=False)
        self._register_lookup(context, name, symbol_id, allow_short_name_ambiguity=True)
        context.classes.append(qualified)
        self._resolve_pending_calls_for_symbol(context, symbol_id)
        return True

    def _symbol_id_for_function(
        self,
        node,
        context: TraversalContext,
        namespace_parts: List[str],
        type_stack: List[str],
    ) -> Optional[str]:
        name = self._extract_function_name(node, context)
        if not name:
            return None
        return self._create_symbol_id(
            context.file_path,
            self._qualify_function_name(name, namespace_parts, type_stack),
        )

    def _extract_include(self, node, context: TraversalContext) -> Optional[str]:
        text = self._slice_node(node, context).strip()
        match = re.search(r"#\s*include\s*[<\"]([^>\"]+)[>\"]", text)
        return match.group(1) if match else None

    def _extract_name(self, node, context: TraversalContext) -> Optional[str]:
        try:
            name_node = node.child_by_field_name("name")
        except Exception:
            name_node = None
        if name_node is not None:
            return self._sanitize_identifier(self._slice_node(name_node, context))

        for child in node.children:
            if child.type in {"type_identifier", "identifier", "field_identifier"}:
                return self._sanitize_identifier(self._slice_node(child, context))
        return None

    def _extract_function_name(self, node, context: TraversalContext) -> Optional[str]:
        declarator = node.child_by_field_name("declarator")
        if declarator is not None:
            name = self._extract_declarator_name(declarator, context)
            if name:
                return name
        return self._extract_function_name_from_text(self._slice_node(node, context))

    def _extract_declarator_name(self, node, context: TraversalContext) -> Optional[str]:
        if node.type in {"identifier", "field_identifier"}:
            return self._sanitize_identifier(self._slice_node(node, context))
        if node.type in {"qualified_identifier", "template_function", "destructor_name"}:
            return self._normalize_cpp_name(self._slice_node(node, context))

        for field in ("declarator", "function", "name"):
            try:
                child = node.child_by_field_name(field)
            except Exception:
                child = None
            if child is not None:
                name = self._extract_declarator_name(child, context)
                if name:
                    return name

        for child in node.children:
            if child.type in self._DECLARATOR_NODES:
                name = self._extract_declarator_name(child, context)
                if name:
                    return name
        return None

    def _extract_function_name_from_text(self, text: str) -> Optional[str]:
        header = text.split("{", 1)[0]
        match = re.search(r"([~A-Za-z_][A-Za-z0-9_:~]*)\s*\([^;{}]*\)\s*$", header.strip())
        return self._normalize_cpp_name(match.group(1)) if match else None

    def _extract_typedef_alias(self, node, type_node, context: TraversalContext) -> Optional[str]:
        candidates = []
        for child in node.children:
            if child == type_node:
                continue
            if child.type in {"type_identifier", "identifier"}:
                candidate = self._sanitize_identifier(self._slice_node(child, context))
                if candidate:
                    candidates.append(candidate)
            elif child.type in {"init_declarator", "pointer_declarator", "array_declarator"}:
                candidate = self._last_identifier(child, context)
                if candidate:
                    candidates.append(candidate)
        return candidates[-1] if candidates else None

    def _last_identifier(self, node, context: TraversalContext) -> Optional[str]:
        found = None
        stack = [node]
        while stack:
            current = stack.pop()
            if current.type in {"type_identifier", "identifier", "field_identifier"}:
                found = self._sanitize_identifier(self._slice_node(current, context)) or found
            stack.extend(reversed(current.children))
        return found

    def _extract_called_name(self, node, context: TraversalContext) -> Optional[str]:
        try:
            function_node = node.child_by_field_name("function")
        except Exception:
            function_node = None
        if function_node is None:
            return None

        text = self._slice_node(function_node, context).strip()
        if not text:
            return None
        text = re.sub(r"<[^<>]*>", "", text)

        if "::" in text:
            return self._normalize_cpp_name(text)
        if "." in text or "->" in text:
            parts = re.split(r"(?:->|\.)", text)
            return self._sanitize_identifier(parts[-1])
        return self._sanitize_identifier(text)

    def _extract_signature(self, node, context: TraversalContext) -> Optional[str]:
        text = self._slice_node(node, context)
        if not text:
            return None
        header = text.split("{", 1)[0].strip()
        header = " ".join(header.split())
        return header or None

    def _register_call(
        self,
        context: TraversalContext,
        caller: str,
        called: str,
        unresolved_caller: Optional[str] = None,
    ) -> None:
        target_id = self._resolve_symbol_reference(context, called)
        if target_id:
            symbol = context.symbols.get(target_id)
            if symbol and caller not in symbol.called_by:
                symbol.called_by.append(caller)
            return

        key = (unresolved_caller or caller, called)
        if key not in context.pending_call_set:
            context.pending_call_set.add(key)
            context.pending_calls.append(key)

    def _resolve_symbol_reference(self, context: TraversalContext, called: str) -> Optional[str]:
        if called in context.ambiguous_short_names:
            return None
        if called in context.symbol_lookup:
            return context.symbol_lookup[called]

        matches = set()
        for name, symbol_id in context.symbol_lookup.items():
            if name == called or name.endswith(f".{called}"):
                matches.add(symbol_id)
        if len(matches) == 1:
            return next(iter(matches))
        return None

    def _register_function_lookups(self, context: TraversalContext, full_name: str, symbol_id: str) -> None:
        self._register_lookup(context, full_name, symbol_id, allow_short_name_ambiguity=False)
        short_name = full_name.rsplit(".", 1)[-1]
        self._register_lookup(context, short_name, symbol_id, allow_short_name_ambiguity=True)
        parts = full_name.split(".")
        if len(parts) >= 2:
            self._register_lookup(context, ".".join(parts[-2:]), symbol_id, allow_short_name_ambiguity=True)

    def _register_lookup(
        self,
        context: TraversalContext,
        name: str,
        symbol_id: str,
        allow_short_name_ambiguity: bool,
    ) -> None:
        if not name:
            return
        if allow_short_name_ambiguity and name in context.ambiguous_short_names:
            return
        existing = context.symbol_lookup.get(name)
        if existing and existing != symbol_id:
            if allow_short_name_ambiguity:
                context.ambiguous_short_names.add(name)
                context.symbol_lookup.pop(name, None)
            return
        context.symbol_lookup[name] = symbol_id

    def _resolve_pending_calls_for_symbol(self, context: TraversalContext, symbol_id: str) -> None:
        symbol = context.symbols.get(symbol_id)
        if not symbol:
            return
        short_name = symbol_id.split("::", 1)[-1]
        remaining = []
        remaining_set = set()
        for caller, called in context.pending_calls:
            if called == short_name or short_name.endswith(f".{called}"):
                if caller not in symbol.called_by:
                    symbol.called_by.append(caller)
            else:
                remaining.append((caller, called))
                remaining_set.add((caller, called))
        context.pending_calls = remaining
        context.pending_call_set = remaining_set

    def _is_type_definition(self, node) -> bool:
        if node.type == "enum_specifier":
            return any(child.type == "enumerator_list" for child in node.children)
        return node.child_by_field_name("body") is not None

    def _qualify_function_name(self, name: str, namespace_parts: List[str], type_stack: List[str]) -> str:
        clean = self._normalize_cpp_name(name) or name
        if "." in clean:
            clean_parts = clean.split(".")
            if namespace_parts and clean_parts[: len(namespace_parts)] == namespace_parts:
                return clean
            return self._qualify_name(namespace_parts, clean_parts)
        return self._qualify_name(namespace_parts, type_stack + [clean])

    def _qualify_name(self, namespace_parts: List[str], names: List[str]) -> str:
        return ".".join([part for part in namespace_parts + names if part])

    def _normalize_cpp_name(self, name: str) -> Optional[str]:
        if not name:
            return None
        clean = re.sub(r"<[^<>]*>", "", name.strip())
        clean = clean.replace("::", ".")
        clean = clean.replace("~", "#dtor")
        parts = []
        for part in clean.split("."):
            match = re.search(r"[#A-Za-z_][#A-Za-z0-9_]*", part)
            if match:
                parts.append(match.group(0))
        return ".".join(parts) if parts else None

    def _sanitize_identifier(self, value: str) -> Optional[str]:
        if not value:
            return None
        match = re.search(r"[A-Za-z_][A-Za-z0-9_]*", value.strip())
        return match.group(0) if match else None

    def _node_type_set(self, node) -> Set[str]:
        result = {node.type}
        stack = list(node.children)
        while stack:
            current = stack.pop()
            result.add(current.type)
            stack.extend(current.children)
        return result

    def _slice_node(self, node, context: TraversalContext) -> str:
        return context.content_bytes[node.start_byte:node.end_byte].decode("utf8", errors="ignore")

    def _language_for_path(self, file_path: str) -> str:
        lower = file_path.lower()
        for ext in self._CPP_EXTENSIONS:
            if lower.endswith(ext):
                return "cpp"
        return "c"
