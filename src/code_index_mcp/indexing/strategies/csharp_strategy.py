"""
C# parsing strategy using tree-sitter with single-pass traversal.
"""

import logging
import re
import threading
from typing import Dict, List, Tuple, Optional, Set

import tree_sitter
from tree_sitter_c_sharp import language

from .base_strategy import ParsingStrategy
from ..models import SymbolInfo, FileInfo


logger = logging.getLogger(__name__)


class TraversalContext:
    """Lightweight traversal context to keep state in a single pass."""

    def __init__(
        self,
        content: str,
        content_bytes: bytes,
        file_path: str,
        symbols: Dict[str, SymbolInfo],
        functions: List[str],
        classes: List[str],
        imports: List[str],
        symbol_lookup: Dict[str, str],
    ):
        self.content = content
        self.content_bytes = content_bytes
        self.file_path = file_path
        self.symbols = symbols
        self.functions = functions
        self.classes = classes
        self.imports = imports
        self.symbol_lookup = symbol_lookup
        self.pending_calls: List[Tuple[str, str]] = []
        self.pending_call_set: Set[Tuple[str, str]] = set()
        self.last_namespace: Optional[str] = None
        self.global_namespace_parts: List[str] = []


class CSharpParsingStrategy(ParsingStrategy):
    """C# parsing strategy using tree-sitter - single pass optimized."""

    _TYPE_KINDS = {
        "class_declaration": "class",
        "class": "class",
        "struct_declaration": "class",
        "struct": "class",
        "interface_declaration": "interface",
        "enum_declaration": "enum",
        "record_declaration": "class",
        "delegate_declaration": "delegate",
    }

    def __init__(self):
        self.csharp_language = tree_sitter.Language(language())
        self._parser_local = threading.local()

    def _get_parser(self) -> tree_sitter.Parser:
        parser = getattr(self._parser_local, "parser", None)
        if parser is None:
            parser = tree_sitter.Parser(self.csharp_language)
            self._parser_local.parser = parser
        return parser

    def get_language_name(self) -> str:
        return "csharp"

    def get_supported_extensions(self) -> List[str]:
        return [".cs"]

    def parse_file(self, file_path: str, content: str) -> Tuple[Dict[str, SymbolInfo], FileInfo]:
        """Parse C# file using tree-sitter with single-pass optimization."""
        symbols: Dict[str, SymbolInfo] = {}
        functions: List[str] = []
        classes: List[str] = []
        imports: List[str] = []

        sanitized_content = self._sanitize_content(content)
        content_bytes = sanitized_content.encode("utf8")
        parser = self._get_parser()

        try:
            tree = parser.parse(content_bytes)
        except Exception as exc:  # pragma: no cover - parser errors are rare
            logger.warning(f"Error parsing C# file {file_path}: {exc}")
            file_info = FileInfo(
                language=self.get_language_name(),
                line_count=content.count("\n") + 1,
                symbols={"functions": functions, "classes": classes},
                imports=imports,
            )
            return symbols, file_info

        symbol_lookup: Dict[str, str] = {}
        context = TraversalContext(
            content=sanitized_content,
            content_bytes=content_bytes,
            file_path=file_path,
            symbols=symbols,
            functions=functions,
            classes=classes,
            imports=imports,
            symbol_lookup=symbol_lookup,
        )

        base_namespace = self._extract_file_scoped_namespace(tree, context)
        context.global_namespace_parts = base_namespace

        self._traverse_node(
            tree.root_node,
            context=context,
            namespace_parts=base_namespace,
            type_stack=[],
            current_function=None,
        )

        namespace = None
        if context.symbol_lookup:
            # Best-effort: prefer first encountered namespace from imports parsing
            namespace = getattr(context, "last_namespace", None)

        file_info = FileInfo(
            language=self.get_language_name(),
            line_count=content.count("\n") + 1,
            symbols={"functions": functions, "classes": classes},
            imports=imports,
            package=namespace,
        )

        if context.pending_calls:
            file_info.pending_calls = context.pending_calls

        return symbols, file_info

    # Traversal helpers -------------------------------------------------
    def _traverse_node(
        self,
        node,
        context: TraversalContext,
        namespace_parts: List[str],
        type_stack: List[str],
        current_function: Optional[str],
    ) -> None:
        if not namespace_parts and context.global_namespace_parts:
            namespace_parts = context.global_namespace_parts

        node_type = node.type

        if node_type == "using_directive":
            import_name = self._extract_using(node, context)
            if import_name and import_name not in context.imports:
                context.imports.append(import_name)
            return

        if node_type in {"namespace_declaration", "namespace", "file_scoped_namespace_declaration"}:
            ns_name = self._extract_named_child(node, "name", context)
            new_namespace = namespace_parts
            if ns_name:
                ns_clean = self._strip_generics(ns_name)
                if node_type == "file_scoped_namespace_declaration":
                    new_namespace = [seg for seg in ns_clean.split(".") if seg]
                    context.global_namespace_parts = new_namespace
                else:
                    new_namespace = namespace_parts + [ns_clean]
                context.last_namespace = ".".join(new_namespace)

            for child in node.children:
                self._traverse_node(child, context, new_namespace, type_stack, current_function)
            return

        if node_type in self._TYPE_KINDS:
            type_name = self._extract_named_child(node, "name", context)
            if type_name:
                clean_name = self._strip_generics(type_name)
                full_type_name = self._qualify_name(namespace_parts, type_stack + [clean_name])
                symbol_id = self._create_symbol_id(context.file_path, full_type_name)
                context.symbols[symbol_id] = SymbolInfo(
                    type=self._TYPE_KINDS[node_type],
                    file=context.file_path,
                    line=node.start_point[0] + 1,
                )
                context.symbol_lookup[full_type_name] = symbol_id
                context.symbol_lookup[clean_name] = symbol_id
                context.classes.append(full_type_name)
                self._resolve_pending_calls(context)

                for child in node.children:
                    self._traverse_node(
                        child,
                        context,
                        namespace_parts,
                        type_stack + [clean_name],
                        current_function,
                    )
                return

        if node_type == "method_declaration":
            method_name = self._extract_named_child(node, "name", context)
            if method_name:
                clean_name = self._strip_generics(method_name)
                full_type = self._qualify_name(namespace_parts, type_stack)
                full_name = self._qualify_name(namespace_parts, type_stack + [clean_name])
                symbol_kind = "method" if type_stack else "function"
                symbol_id = self._create_symbol_id(context.file_path, full_name)
                signature = self._extract_signature(node, context)

                context.symbols[symbol_id] = SymbolInfo(
                    type=symbol_kind,
                    file=context.file_path,
                    line=node.start_point[0] + 1,
                    signature=signature,
                )

                context.symbol_lookup[full_name] = symbol_id
                context.symbol_lookup[clean_name] = symbol_id
                if type_stack:
                    context.symbol_lookup[f"{type_stack[-1]}.{clean_name}"] = symbol_id
                if full_type:
                    context.symbol_lookup[f"{full_type}.{clean_name}"] = symbol_id

                context.functions.append(full_name)
                self._resolve_pending_calls(context)

                for child in node.children:
                    self._traverse_node(
                        child,
                        context,
                        namespace_parts,
                        type_stack,
                        current_function=symbol_id,
                    )
                return

        if node_type == "constructor_declaration":
            ctor_name = type_stack[-1] if type_stack else self._extract_named_child(node, "name", context)
            if ctor_name:
                type_name = self._strip_generics(ctor_name)
                full_type = self._qualify_name(namespace_parts, type_stack)
                ctor_full_name = f"{full_type}.#ctor" if full_type else f"{type_name}.#ctor"
                symbol_id = self._create_symbol_id(context.file_path, ctor_full_name)
                signature = self._extract_signature(node, context)

                context.symbols[symbol_id] = SymbolInfo(
                    type="constructor",
                    file=context.file_path,
                    line=node.start_point[0] + 1,
                    signature=signature,
                )
                context.symbol_lookup[ctor_full_name] = symbol_id
                context.symbol_lookup[f"{type_name}.#ctor"] = symbol_id
                context.symbol_lookup[type_name] = context.symbol_lookup.get(type_name, symbol_id)
                context.functions.append(ctor_full_name)
                self._resolve_pending_calls(context)

                for child in node.children:
                    self._traverse_node(
                        child,
                        context,
                        namespace_parts,
                        type_stack,
                        current_function=symbol_id,
                    )
                return

        if node_type == "local_function_statement":
            func_name = self._extract_named_child(node, "name", context)
            if func_name:
                clean_name = self._strip_generics(func_name)
                full_name = self._qualify_name(namespace_parts, type_stack + [clean_name])
                symbol_id = self._create_symbol_id(context.file_path, full_name)
                signature = self._extract_signature(node, context)

                context.symbols[symbol_id] = SymbolInfo(
                    type="function",
                    file=context.file_path,
                    line=node.start_point[0] + 1,
                    signature=signature,
                )
                context.symbol_lookup[full_name] = symbol_id
                context.symbol_lookup[clean_name] = symbol_id
                context.functions.append(full_name)
                self._resolve_pending_calls(context)

                for child in node.children:
                    self._traverse_node(
                        child,
                        context,
                        namespace_parts,
                        type_stack,
                        current_function=symbol_id,
                    )
                return

        if current_function:
            if node_type == "invocation_expression":
                called, alt_called = self._resolve_invocation_name(node, context, namespace_parts, type_stack)
                self._register_call(context, current_function, called, alt_called)
            elif node_type == "object_creation_expression":
                called, alt_called = self._resolve_object_creation_name(node, context, namespace_parts, type_stack)
                self._register_call(context, current_function, called, alt_called)

        for child in node.children:
            self._traverse_node(child, context, namespace_parts, type_stack, current_function)

    # Extraction utilities ----------------------------------------------
    def _extract_using(self, node, context: TraversalContext) -> Optional[str]:
        text = self._slice_bytes(context.content_bytes, node.start_byte, node.end_byte).strip()
        if not text.startswith("using"):
            return None
        text = text[len("using") :].strip()
        text = re.sub(r"^static\s+", "", text)
        text = text.rstrip(";").strip()
        return text or None

    def _extract_named_child(self, node, field_name: str, context: TraversalContext) -> Optional[str]:
        try:
            name_node = node.child_by_field_name(field_name)
        except Exception:
            name_node = None
        if name_node:
            return self._slice_bytes(context.content_bytes, name_node.start_byte, name_node.end_byte).strip()

        # Fallback: first identifier/generic_name inside the node.
        for child in node.children:
            if child.type in {"identifier", "generic_name", "qualified_name"}:
                return self._slice_bytes(context.content_bytes, child.start_byte, child.end_byte).strip()
        return None

    def _extract_signature(self, node, context: TraversalContext) -> Optional[str]:
        header = self._slice_bytes(context.content_bytes, node.start_byte, node.end_byte)
        if not header:
            return None
        # Trim after first '{' or '=>'
        brace_pos = header.find("{")
        arrow_pos = header.find("=>")
        cut_pos = len(header)
        if brace_pos != -1:
            cut_pos = min(cut_pos, brace_pos)
        if arrow_pos != -1:
            cut_pos = min(cut_pos, arrow_pos)
        header = header[:cut_pos].strip()
        first_line = header.splitlines()[0].strip()
        return first_line or None

    def _resolve_invocation_name(
        self,
        node,
        context: TraversalContext,
        namespace_parts: List[str],
        type_stack: List[str],
    ) -> Tuple[Optional[str], Optional[str]]:
        func_node = node.child_by_field_name("function")
        if not func_node:
            return None, None

        raw = self._slice_bytes(context.content_bytes, func_node.start_byte, func_node.end_byte)
        raw = self._strip_generics(raw)
        raw = raw.strip()
        if not raw:
            return None, None

        # Extract the rightmost identifier as a fallback.
        segments = [seg for seg in raw.replace(" ", "").split(".") if seg]
        if not segments:
            return None, None

        if len(segments) == 1:
            return segments[0], None

        qualifier = ".".join(segments[:-1])
        member = segments[-1]

        # Heuristic: if qualifier looks like a type/namespace (PascalCase start), keep it.
        if qualifier and qualifier[0].isupper():
            return f"{qualifier}.{member}", member
        return member, None

    def _resolve_object_creation_name(
        self,
        node,
        context: TraversalContext,
        namespace_parts: List[str],
        type_stack: List[str],
    ) -> Tuple[Optional[str], Optional[str]]:
        type_node = node.child_by_field_name("type")
        if not type_node:
            return None, None
        raw = self._slice_bytes(context.content_bytes, type_node.start_byte, type_node.end_byte)
        raw = self._strip_generics(raw).strip()
        if not raw:
            return None, None

        segments = [seg for seg in raw.replace(" ", "").split(".") if seg]
        if not segments:
            return None, None

        primary = f"{'.'.join(segments)}.#ctor"
        alt = f"{segments[-1]}.#ctor" if len(segments) > 1 else None
        return primary, alt

    def _register_call(
        self,
        context: TraversalContext,
        caller: str,
        called: Optional[str],
        alt_called: Optional[str] = None,
    ) -> None:
        for candidate in (called, alt_called):
            if not candidate:
                continue
            if candidate in context.symbol_lookup:
                symbol_id = context.symbol_lookup[candidate]
                symbol_info = context.symbols.get(symbol_id)
                if symbol_info and caller not in symbol_info.called_by:
                    symbol_info.called_by.append(caller)
                return

            # Try suffix match: helpful for method names without namespace/type.
            suffix_matches = [
                sid for name, sid in context.symbol_lookup.items() if name.endswith(f".{candidate}")
            ]
            if len(suffix_matches) == 1:
                target_id = suffix_matches[0]
                symbol_info = context.symbols.get(target_id)
                if symbol_info and caller not in symbol_info.called_by:
                    symbol_info.called_by.append(caller)
                return

        if called:
            key = (caller, called)
            if key not in context.pending_call_set:
                context.pending_call_set.add(key)
                context.pending_calls.append(key)

    def _resolve_pending_calls(self, context: TraversalContext) -> None:
        """Resolve any queued calls now that new symbols are registered."""
        if not context.pending_calls:
            return

        remaining: List[Tuple[str, str]] = []
        for caller, called in context.pending_calls:
            resolved = False

            if called in context.symbol_lookup:
                symbol_id = context.symbol_lookup[called]
                symbol_info = context.symbols.get(symbol_id)
                if symbol_info and caller not in symbol_info.called_by:
                    symbol_info.called_by.append(caller)
                resolved = True
            else:
                suffix_matches = [
                    sid for name, sid in context.symbol_lookup.items() if name.endswith(f".{called}")
                ]
                if len(suffix_matches) == 1:
                    target_id = suffix_matches[0]
                    symbol_info = context.symbols.get(target_id)
                    if symbol_info and caller not in symbol_info.called_by:
                        symbol_info.called_by.append(caller)
                    resolved = True

            if not resolved:
                remaining.append((caller, called))

        context.pending_calls = remaining
        context.pending_call_set = set(remaining)

    # Small string utilities --------------------------------------------
    def _strip_generics(self, name: str) -> str:
        """Remove generic argument lists from identifiers."""
        if "<" not in name:
            return name
        result = []
        depth = 0
        for ch in name:
            if ch == "<":
                depth += 1
                continue
            if ch == ">":
                depth = max(0, depth - 1)
                continue
            if depth == 0:
                result.append(ch)
        return "".join(result).strip()

    def _slice_bytes(self, data: bytes, start: int, end: int) -> str:
        if start < 0 or end > len(data) or start >= end:
            return ""
        return data[start:end].decode("utf8", errors="ignore")

    def _qualify_name(self, namespace_parts: List[str], names: List[str]) -> str:
        segments = [seg for seg in namespace_parts if seg]
        segments.extend([seg for seg in names if seg])
        return ".".join(segments)

    def _sanitize_content(self, content: str) -> str:
        """Loosen preprocessor directives so tree-sitter can parse more code."""
        if not content:
            return content
        lines = content.splitlines()
        sanitized = []
        for line in lines:
            if line.lstrip().startswith("#"):
                sanitized.append("// " + line)
            else:
                sanitized.append(line)
        return "\n".join(sanitized)

    def _extract_file_scoped_namespace(self, tree, context: TraversalContext) -> List[str]:
        for child in tree.root_node.children:
            if child.type == "file_scoped_namespace_declaration":
                name = self._extract_named_child(child, "name", context)
                if name:
                    parts = [seg for seg in name.split(".") if seg]
                    context.last_namespace = ".".join(parts)
                    return parts
        return []
