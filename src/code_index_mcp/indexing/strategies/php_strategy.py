"""PHP parsing strategy using tree-sitter with single-pass traversal."""

import logging
import re
from typing import Dict, List, Optional, Set, Tuple

import tree_sitter
from tree_sitter_php import language_php

from .base_strategy import ParsingStrategy
from ..models import FileInfo, SymbolInfo

logger = logging.getLogger(__name__)

_ATTRIBUTE_PREFIX = re.compile(r"^(?:#\[[^\]]*\]\s*)+")
_DOCBLOCK = re.compile(r"^/\*\*(.*?)\*/$", re.DOTALL)


class TraversalContext:
    """Traversal state for PHP symbol extraction."""

    def __init__(
        self,
        content_bytes: bytes,
        file_path: str,
        symbols: Dict[str, SymbolInfo],
        functions: List[str],
        classes: List[str],
        imports: List[str],
    ):
        self.content_bytes = content_bytes
        self.file_path = file_path
        self.symbols = symbols
        self.functions = functions
        self.classes = classes
        self.imports = imports
        self.namespace: Optional[str] = None
        self.symbol_lookup: Dict[str, str] = {}
        self.ambiguous_short_names: Set[str] = set()
        self.pending_calls: List[Tuple[str, str]] = []
        self.pending_call_set: Set[Tuple[str, str]] = set()


class PhpParsingStrategy(ParsingStrategy):
    """PHP-specific parsing strategy using tree-sitter."""

    _TYPE_DECLARATIONS = {
        "class_declaration",
        "interface_declaration",
        "trait_declaration",
        "enum_declaration",
    }
    _CALL_TYPES = {
        "function_call_expression",
        "member_call_expression",
        "scoped_call_expression",
    }

    def __init__(self):
        self.php_language = tree_sitter.Language(language_php())

    def get_language_name(self) -> str:
        return "php"

    def get_supported_extensions(self) -> List[str]:
        return [".php", ".phtml", ".php3", ".php4", ".php5", ".phps"]

    def parse_file(self, file_path: str, content: str) -> Tuple[Dict[str, SymbolInfo], FileInfo]:
        """Parse PHP file and extract symbols/imports/calls."""
        symbols: Dict[str, SymbolInfo] = {}
        functions: List[str] = []
        classes: List[str] = []
        imports: List[str] = []

        content_bytes = content.encode("utf8")
        parser = tree_sitter.Parser(self.php_language)

        context = TraversalContext(
            content_bytes=content_bytes,
            file_path=file_path,
            symbols=symbols,
            functions=functions,
            classes=classes,
            imports=imports,
        )

        try:
            tree = parser.parse(content_bytes)
            self._traverse_children(
                tree.root_node.children,
                context,
                current_namespace=None,
                current_type=None,
                current_function=None,
            )
        except Exception as exc:  # pragma: no cover - parser errors are uncommon
            logger.warning(f"Error parsing PHP file {file_path}: {exc}")

        file_info = FileInfo(
            language=self.get_language_name(),
            line_count=content.count("\n") + 1,
            symbols={"functions": functions, "classes": classes},
            imports=imports,
            package=context.namespace,
        )

        if context.pending_calls:
            file_info.pending_calls = context.pending_calls

        return symbols, file_info

    def _traverse_children(
        self,
        nodes,
        context: TraversalContext,
        current_namespace: Optional[str],
        current_type: Optional[str],
        current_function: Optional[str],
    ) -> None:
        """Traverse a sibling list, tracking semicolon-style namespaces forward."""
        active_namespace = current_namespace

        for node in nodes:
            if node.type == "namespace_definition":
                namespace = self._extract_namespace(node, context)
                if namespace:
                    context.namespace = namespace
                body = node.child_by_field_name("body")
                if body is not None:
                    self._traverse_children(
                        body.children,
                        context,
                        namespace,
                        None,
                        current_function,
                    )
                    continue
                active_namespace = namespace
                continue

            self._traverse_node(
                node,
                context,
                active_namespace,
                current_type,
                current_function,
            )

    def _traverse_node(
        self,
        node,
        context: TraversalContext,
        current_namespace: Optional[str],
        current_type: Optional[str],
        current_function: Optional[str],
    ) -> None:
        node_type = node.type

        if node_type == "namespace_use_declaration":
            self._collect_import(node, context)
            return

        if node_type in self._TYPE_DECLARATIONS:
            type_name = self._extract_name(node, context)
            if type_name:
                symbol_id = self._create_symbol_id(context.file_path, type_name)
                context.symbols[symbol_id] = SymbolInfo(
                    type="class",
                    file=context.file_path,
                    line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    docstring=self._extract_docblock(node, context),
                )
                self._register_lookup(context, type_name, symbol_id)
                qualified = self._qualify(current_namespace, type_name)
                if qualified and qualified != type_name:
                    self._register_lookup(context, qualified, symbol_id)
                context.classes.append(type_name)
                self._resolve_pending_calls_for_symbol(context, symbol_id)

            body = node.child_by_field_name("body")
            if body is not None:
                self._traverse_children(
                    body.children,
                    context,
                    current_namespace,
                    type_name,
                    current_function,
                )
            return

        if node_type == "method_declaration":
            self._record_callable(node, context, current_type, "method", current_namespace)
            body = node.child_by_field_name("body")
            if body is not None:
                name = self._extract_name(node, context)
                full_name = self._member_name(current_type, name)
                symbol_id = self._create_symbol_id(context.file_path, full_name)
                self._traverse_children(
                    body.children,
                    context,
                    current_namespace,
                    current_type,
                    symbol_id,
                )
            return

        if node_type == "function_definition":
            self._record_callable(node, context, None, "function", current_namespace)
            body = node.child_by_field_name("body")
            if body is not None:
                name = self._extract_name(node, context)
                symbol_id = self._create_symbol_id(context.file_path, name)
                self._traverse_children(
                    body.children,
                    context,
                    current_namespace,
                    current_type,
                    symbol_id,
                )
            return

        if node_type in self._CALL_TYPES and current_function:
            called_name = self._extract_called_name(node, context, current_type, current_namespace)
            if called_name:
                self._register_call(context, caller=current_function, called=called_name)

        if node_type == "object_creation_expression" and current_function:
            called_name = self._extract_constructor_name(node, context, current_type)
            if called_name:
                self._register_call(context, caller=current_function, called=called_name)

        self._traverse_children(
            node.children,
            context,
            current_namespace,
            current_type,
            current_function,
        )

    def _record_callable(
        self,
        node,
        context: TraversalContext,
        owner_type: Optional[str],
        symbol_kind: str,
        current_namespace: Optional[str],
    ) -> None:
        """Persist a method or function declaration as a symbol."""
        name = self._extract_name(node, context)
        if not name:
            return

        full_name = self._member_name(owner_type, name)
        symbol_id = self._create_symbol_id(context.file_path, full_name)
        context.symbols[symbol_id] = SymbolInfo(
            type=symbol_kind,
            file=context.file_path,
            line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            signature=self._extract_signature(node, context),
            docstring=self._extract_docblock(node, context),
        )

        self._register_lookup(context, full_name, symbol_id, allow_short_name_ambiguity=False)
        self._register_lookup(context, name, symbol_id, allow_short_name_ambiguity=True)
        if current_namespace:
            qualified = self._qualify(current_namespace, full_name)
            if qualified:
                self._register_lookup(
                    context,
                    qualified,
                    symbol_id,
                    allow_short_name_ambiguity=True,
                )

        context.functions.append(full_name)
        self._resolve_pending_calls_for_symbol(context, symbol_id)

    def _collect_import(self, node, context: TraversalContext) -> None:
        text = self._slice_node(node, context)
        if not text:
            return
        compact = " ".join(text.split())
        compact = re.sub(r"^use\s+", "", compact)
        compact = re.sub(r";\s*$", "", compact)
        for clause in re.split(r",(?![^{]*\})", compact):
            candidate = clause.strip()
            if candidate and candidate not in context.imports:
                context.imports.append(candidate)

    def _extract_namespace(self, node, context: TraversalContext) -> Optional[str]:
        # tree-sitter-php uses a single "namespace_name" node for the semicolon
        # form (namespace A\B;) and separate "name" children for the braced form
        # (namespace A\B { ... }), so collect from both node types.
        segments = [
            self._slice_node(child, context).strip()
            for child in node.named_children
            if child.type in {"name", "namespace_name"}
        ]
        cleaned = [segment for segment in segments if segment]
        if cleaned:
            return "\\".join(cleaned)

        name_node = node.child_by_field_name("name")
        if name_node is not None:
            text = self._slice_node(name_node, context).strip()
            return text or None
        return None

    def _extract_name(self, node, context: TraversalContext) -> Optional[str]:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            for child in node.children:
                if child.type == "name":
                    name_node = child
                    break
        if name_node is None:
            return None
        return self._slice_node(name_node, context).strip() or None

    def _extract_signature(self, node, context: TraversalContext) -> Optional[str]:
        body = node.child_by_field_name("body")
        end_byte = body.start_byte if body is not None else node.end_byte
        raw = self._slice_bytes(context.content_bytes, node.start_byte, end_byte)
        if not raw:
            return None

        collapsed = " ".join(raw.split())
        collapsed = _ATTRIBUTE_PREFIX.sub("", collapsed)
        collapsed = collapsed.rstrip(";").strip()
        return collapsed or None

    def _extract_docblock(self, node, context: TraversalContext) -> Optional[str]:
        previous = node.prev_named_sibling
        if previous is None or previous.type != "comment":
            return None
        text = self._slice_node(previous, context).strip()
        match = _DOCBLOCK.match(text)
        if not match:
            return None
        cleaned = []
        for line in match.group(1).splitlines():
            stripped = line.strip()
            if stripped.startswith("*"):
                stripped = stripped[1:].strip()
            if stripped:
                cleaned.append(stripped)
        return "\n".join(cleaned) or None

    def _extract_called_name(
        self,
        node,
        context: TraversalContext,
        current_type: Optional[str],
        current_namespace: Optional[str],
    ) -> Optional[str]:
        node_type = node.type

        if node_type == "function_call_expression":
            target = node.child_by_field_name("function")
            if target is None:
                return None
            text = self._slice_node(target, context).strip()
            if not text or text.startswith("$"):
                return None
            return text

        if node_type == "member_call_expression":
            method_node = node.child_by_field_name("name")
            object_node = node.child_by_field_name("object")
            if method_node is None or object_node is None:
                return None
            method_name = self._slice_node(method_node, context).strip()
            object_text = self._slice_node(object_node, context).strip()
            if not method_name:
                return None
            if object_text in {"$this", "self", "static"}:
                return self._member_name(current_type, method_name)
            return None

        if node_type == "scoped_call_expression":
            method_node = node.child_by_field_name("name")
            scope_node = node.child_by_field_name("scope")
            if method_node is None or scope_node is None:
                return None
            method_name = self._slice_node(method_node, context).strip()
            scope_text = self._slice_node(scope_node, context).strip()
            if not method_name or not scope_text:
                return None
            if scope_text in {"self", "static"}:
                return self._member_name(current_type, method_name)
            if scope_text == "parent":
                return None
            return f"{scope_text}.{method_name}"

        return None

    def _extract_constructor_name(
        self,
        node,
        context: TraversalContext,
        current_type: Optional[str],
    ) -> Optional[str]:
        class_node = None
        for child in node.children:
            if child.type in {"name", "qualified_name"}:
                class_node = child
                break
        if class_node is None:
            return None

        class_text = self._slice_node(class_node, context).strip()
        if not class_text or class_text.startswith("$"):
            return None
        if class_text in {"self", "static"}:
            return self._member_name(current_type, "__construct")
        if class_text == "parent":
            return None

        short_class = class_text.rsplit("\\", 1)[-1]
        return f"{short_class}.__construct"

    def _register_call(self, context: TraversalContext, caller: str, called: str) -> None:
        target_id = self._resolve_symbol_reference(context, called)
        if target_id:
            symbol = context.symbols.get(target_id)
            if symbol and caller not in symbol.called_by:
                symbol.called_by.append(caller)
            return

        key = (caller, called)
        if key not in context.pending_call_set:
            context.pending_call_set.add(key)
            context.pending_calls.append(key)

    def _resolve_symbol_reference(self, context: TraversalContext, called: str) -> Optional[str]:
        if not called or called in context.ambiguous_short_names:
            return None

        if called in context.symbol_lookup:
            return context.symbol_lookup[called]

        short_name = called.rsplit("\\", 1)[-1]
        if short_name != called and short_name not in context.ambiguous_short_names:
            resolved = context.symbol_lookup.get(short_name)
            if resolved:
                return resolved

        # Methods reached through $this may be declared on a trait or a parent
        # class, so fall back to the bare method name once the owner-qualified
        # form misses. Ambiguous bare names are excluded by the guard above.
        if "." in called:
            member_name = called.rsplit(".", 1)[-1]
            if member_name not in context.ambiguous_short_names:
                return context.symbol_lookup.get(member_name)

        return None

    def _register_lookup(
        self,
        context: TraversalContext,
        name: Optional[str],
        symbol_id: str,
        allow_short_name_ambiguity: bool = True,
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
        remaining: List[Tuple[str, str]] = []
        remaining_set: Set[Tuple[str, str]] = set()

        for caller, called in context.pending_calls:
            if called == short_name or short_name.endswith(f".{called}"):
                if caller not in symbol.called_by:
                    symbol.called_by.append(caller)
            else:
                remaining.append((caller, called))
                remaining_set.add((caller, called))

        context.pending_calls = remaining
        context.pending_call_set = remaining_set

    def _member_name(self, owner_type: Optional[str], name: Optional[str]) -> str:
        if not name:
            return ""
        if owner_type:
            return f"{owner_type}.{name}"
        return name

    def _qualify(self, namespace: Optional[str], name: Optional[str]) -> Optional[str]:
        if not name:
            return None
        if not namespace:
            return name
        return f"{namespace}\\{name}"

    def _slice_node(self, node, context: TraversalContext) -> str:
        return self._slice_bytes(context.content_bytes, node.start_byte, node.end_byte)
