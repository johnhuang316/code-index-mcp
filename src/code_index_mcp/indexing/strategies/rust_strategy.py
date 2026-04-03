"""Rust parsing strategy using tree-sitter with single-pass traversal."""

import logging
import re
from typing import Dict, List, Optional, Set, Tuple

import tree_sitter
from tree_sitter_rust import language

from .base_strategy import ParsingStrategy
from ..models import FileInfo, SymbolInfo

logger = logging.getLogger(__name__)


class TraversalContext:
    """Traversal state for Rust symbol extraction."""

    def __init__(
        self,
        content: str,
        content_bytes: bytes,
        file_path: str,
        symbols: Dict[str, SymbolInfo],
        functions: List[str],
        classes: List[str],
        imports: List[str],
    ):
        self.content = content
        self.content_bytes = content_bytes
        self.file_path = file_path
        self.symbols = symbols
        self.functions = functions
        self.classes = classes
        self.imports = imports
        self.symbol_lookup: Dict[str, str] = {}
        self.ambiguous_short_names: Set[str] = set()
        self.pending_calls: List[Tuple[str, str]] = []
        self.pending_call_set: Set[Tuple[str, str]] = set()


class RustParsingStrategy(ParsingStrategy):
    """Rust-specific parsing strategy using tree-sitter."""

    _TYPE_ITEMS = {"struct_item", "enum_item", "trait_item"}

    def __init__(self):
        self.rust_language = tree_sitter.Language(language())

    def get_language_name(self) -> str:
        return "rust"

    def get_supported_extensions(self) -> List[str]:
        return [".rs"]

    def parse_file(self, file_path: str, content: str) -> Tuple[Dict[str, SymbolInfo], FileInfo]:
        """Parse Rust file and extract symbols/imports/calls."""
        symbols: Dict[str, SymbolInfo] = {}
        functions: List[str] = []
        classes: List[str] = []
        imports: List[str] = []

        content_bytes = content.encode("utf8")
        parser = tree_sitter.Parser(self.rust_language)

        context = TraversalContext(
            content=content,
            content_bytes=content_bytes,
            file_path=file_path,
            symbols=symbols,
            functions=functions,
            classes=classes,
            imports=imports,
        )

        try:
            tree = parser.parse(content_bytes)
            self._traverse_node(
                tree.root_node,
                context,
                current_module=None,
                current_impl_type=None,
                current_function=None,
            )
        except Exception as exc:  # pragma: no cover - parser errors are uncommon
            logger.warning(f"Error parsing Rust file {file_path}: {exc}")

        file_info = FileInfo(
            language=self.get_language_name(),
            line_count=content.count("\n") + 1,
            symbols={"functions": functions, "classes": classes},
            imports=imports,
        )

        if context.pending_calls:
            file_info.pending_calls = context.pending_calls

        return symbols, file_info

    def _traverse_node(
        self,
        node,
        context: TraversalContext,
        current_module: Optional[str],
        current_impl_type: Optional[str],
        current_function: Optional[str],
    ) -> None:
        node_type = node.type

        if node_type == "mod_item":
            module_name = self._extract_name(node, context)
            next_module = self._join_namespace(current_module, module_name)
            body = node.child_by_field_name("body")
            if body is not None:
                for child in body.children:
                    self._traverse_node(
                        child,
                        context,
                        current_module=next_module,
                        current_impl_type=current_impl_type,
                        current_function=current_function,
                    )
                return

        if node_type == "use_declaration":
            import_path = self._extract_use_path(node, context)
            if import_path and import_path not in context.imports:
                context.imports.append(import_path)
            return

        if node_type in self._TYPE_ITEMS:
            type_name = self._qualify_name(current_module, self._extract_name(node, context))
            if type_name:
                symbol_id = self._create_symbol_id(context.file_path, type_name)
                context.symbols[symbol_id] = SymbolInfo(
                    type="class",
                    file=context.file_path,
                    line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                )
                self._register_lookup(context, type_name, symbol_id, allow_short_name_ambiguity=True)
                short_name = self._short_name(type_name)
                if short_name and short_name != type_name:
                    self._register_lookup(context, short_name, symbol_id, allow_short_name_ambiguity=True)
                context.classes.append(type_name)
                self._resolve_pending_calls_for_symbol(context, symbol_id)

            for child in node.children:
                self._traverse_node(
                    child,
                    context,
                    current_module=current_module,
                    current_impl_type=current_impl_type,
                    current_function=current_function,
                )
            return

        if node_type == "impl_item":
            impl_type = self._qualify_type_name(
                current_module,
                self._extract_impl_type_name(node, context),
            ) or current_impl_type
            for child in node.children:
                self._traverse_node(
                    child,
                    context,
                    current_module=current_module,
                    current_impl_type=impl_type,
                    current_function=current_function,
                )
            return

        if node_type == "function_item":
            name = self._extract_name(node, context)
            if name:
                if current_impl_type:
                    full_name = f"{current_impl_type}.{name}"
                    symbol_kind = "method"
                else:
                    full_name = self._qualify_name(current_module, name)
                    symbol_kind = "function"

                symbol_id = self._create_symbol_id(context.file_path, full_name)
                context.symbols[symbol_id] = SymbolInfo(
                    type=symbol_kind,
                    file=context.file_path,
                    line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    signature=self._extract_signature(node, context),
                )
                self._register_lookup(context, full_name, symbol_id, allow_short_name_ambiguity=False)
                short_name = self._short_name(full_name)
                if short_name:
                    self._register_lookup(context, short_name, symbol_id, allow_short_name_ambiguity=True)
                if current_impl_type:
                    owner_short = self._short_name(current_impl_type)
                    if owner_short and owner_short != current_impl_type:
                        self._register_lookup(
                            context,
                            f"{owner_short}.{name}",
                            symbol_id,
                            allow_short_name_ambiguity=True,
                        )
                context.functions.append(full_name)
                self._resolve_pending_calls_for_symbol(context, symbol_id)

                for child in node.children:
                    self._traverse_node(
                        child,
                        context,
                        current_module=current_module,
                        current_impl_type=current_impl_type,
                        current_function=symbol_id,
                    )
                return

        if node_type == "call_expression" and current_function:
            called_name = self._extract_called_name(node, context, current_module)
            if called_name:
                self._register_call(context, caller=current_function, called=called_name)

        for child in node.children:
            self._traverse_node(
                child,
                context,
                current_module=current_module,
                current_impl_type=current_impl_type,
                current_function=current_function,
            )

    def _extract_name(self, node, context: TraversalContext) -> Optional[str]:
        name_node = None
        try:
            name_node = node.child_by_field_name("name")
        except Exception:
            name_node = None

        if name_node is not None:
            name = self._slice_node(name_node, context)
            return self._sanitize_identifier(name)

        for child in node.children:
            if child.type in {"identifier", "type_identifier"}:
                name = self._slice_node(child, context)
                clean = self._sanitize_identifier(name)
                if clean:
                    return clean
        return None

    def _extract_impl_type_name(self, node, context: TraversalContext) -> Optional[str]:
        type_node = None
        try:
            type_node = node.child_by_field_name("type")
        except Exception:
            type_node = None

        if type_node is not None:
            return self._normalize_type_name(self._slice_node(type_node, context))

        for child in node.named_children:
            if child.type in {"type_identifier", "scoped_type_identifier", "generic_type", "identifier"}:
                normalized = self._normalize_type_name(self._slice_node(child, context))
                if normalized:
                    return normalized
        return None

    def _extract_signature(self, node, context: TraversalContext) -> Optional[str]:
        snippet = self._slice_node(node, context)
        if not snippet:
            return None
        first_line = snippet.splitlines()[0].strip()
        return first_line or None

    def _extract_use_path(self, node, context: TraversalContext) -> Optional[str]:
        text = self._slice_node(node, context)
        if not text:
            return None
        compact = " ".join(text.split())
        compact = re.sub(r"^(?:pub(?:\([^)]*\))?\s+)?use\s+", "", compact)
        compact = re.sub(r";\s*$", "", compact)
        return compact.strip() or None

    def _extract_called_name(
        self,
        node,
        context: TraversalContext,
        current_module: Optional[str],
    ) -> Optional[str]:
        function_node = None
        try:
            function_node = node.child_by_field_name("function")
        except Exception:
            function_node = None

        if function_node is None:
            for child in node.named_children:
                if child.type != "arguments":
                    function_node = child
                    break

        if function_node is None:
            return None

        identifiers = self._collect_identifier_tokens(function_node, context)
        if not identifiers:
            return None

        identifiers = self._normalize_call_segments(identifiers, current_module)
        if not identifiers:
            return None

        if len(identifiers) >= 2 and identifiers[-2][:1].isupper():
            owner = "::".join(identifiers[:-1])
            return f"{owner}.{identifiers[-1]}"
        if len(identifiers) >= 2:
            return "::".join(identifiers)
        return identifiers[-1]

    def _collect_identifier_tokens(self, node, context: TraversalContext) -> List[str]:
        tokens: List[str] = []
        stack = [node]

        while stack:
            current = stack.pop()
            if current.type in {"identifier", "type_identifier", "field_identifier", "self", "super", "crate"}:
                token = self._sanitize_identifier(self._slice_node(current, context))
                if token:
                    tokens.append(token)
                continue

            children = list(current.named_children or [])
            for child in reversed(children):
                stack.append(child)

        return tokens

    def _register_call(self, context: TraversalContext, caller: str, called: str) -> None:
        target_id = self._resolve_symbol_reference(context, called)
        if not target_id:
            caller_module = self._module_from_symbol_name(caller.split("::", 1)[-1])
            if caller_module and "." not in called and "::" not in called:
                target_id = self._resolve_symbol_reference(context, f"{caller_module}::{called}")
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
        if called in context.ambiguous_short_names:
            return None

        if called in context.symbol_lookup:
            return context.symbol_lookup[called]

        matches = set()
        for name, symbol_id in context.symbol_lookup.items():
            if name == called or name.endswith(f".{called}"):
                matches.add(symbol_id)
                continue
            if "::" in name and "." not in called and name.endswith(f"::{called}"):
                matches.add(symbol_id)
        if len(matches) == 1:
            return next(iter(matches))

        return None

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
        remaining: List[Tuple[str, str]] = []
        remaining_set: Set[Tuple[str, str]] = set()

        for caller, called in context.pending_calls:
            if self._call_matches_symbol(caller, called, short_name):
                if caller not in symbol.called_by:
                    symbol.called_by.append(caller)
            else:
                remaining.append((caller, called))
                remaining_set.add((caller, called))

        context.pending_calls = remaining
        context.pending_call_set = remaining_set

    def _call_matches_symbol(self, caller: str, called: str, short_name: str) -> bool:
        if called == short_name:
            return True
        # Only allow suffix matching when caller includes explicit qualification
        # (for example, module::Type::method captured as "Type.method").
        if "." in called and short_name.endswith(f".{called}"):
            return True
        caller_module = self._module_from_symbol_name(caller.split("::", 1)[-1])
        if "::" in called:
            normalized_called = self._normalize_relative_call_name(called, caller_module)
            return normalized_called == short_name
        if (
            caller_module
            and "." not in called
            and "::" in short_name
            and short_name == f"{caller_module}::{called}"
        ):
            return True
        return False

    def _slice_node(self, node, context: TraversalContext) -> str:
        return context.content_bytes[node.start_byte:node.end_byte].decode("utf8", errors="ignore")

    def _sanitize_identifier(self, value: str) -> Optional[str]:
        if not value:
            return None
        candidate = value.strip()
        match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", candidate)
        return match.group(0) if match else None

    def _normalize_type_name(self, value: str) -> Optional[str]:
        if not value:
            return None

        clean = value.strip()
        clean = clean.replace("&", " ")
        clean = clean.replace("mut", " ")
        clean = clean.replace("dyn", " ")
        clean = re.sub(r"'\w+", " ", clean)
        clean = re.sub(r"<[^>]*>", "", clean)
        clean = " ".join(clean.split())

        if not clean:
            return None

        segments = [self._sanitize_identifier(seg) for seg in re.split(r"::", clean) if seg]
        segments = [seg for seg in segments if seg]
        if not segments:
            return None

        return "::".join(segments)

    def _join_namespace(self, current_module: Optional[str], name: Optional[str]) -> Optional[str]:
        if not name:
            return current_module
        if not current_module:
            return name
        return f"{current_module}::{name}"

    def _qualify_name(self, current_module: Optional[str], name: Optional[str]) -> Optional[str]:
        if not name:
            return None
        return self._join_namespace(current_module, name)

    def _qualify_type_name(self, current_module: Optional[str], type_name: Optional[str]) -> Optional[str]:
        if not type_name:
            return None
        if "::" in type_name:
            return self._normalize_relative_call_name(type_name, current_module)
        return self._join_namespace(current_module, type_name)

    def _normalize_call_segments(
        self,
        identifiers: List[str],
        current_module: Optional[str],
    ) -> List[str]:
        if not identifiers:
            return []
        module_parts = current_module.split("::") if current_module else []
        if identifiers[0] == "crate":
            return identifiers[1:]
        if identifiers[0] == "self":
            return module_parts + identifiers[1:]
        if identifiers[0] == "super":
            return module_parts[:-1] + identifiers[1:]
        return identifiers

    def _normalize_relative_call_name(self, called: str, current_module: Optional[str]) -> str:
        normalized = self._normalize_call_segments(
            [segment for segment in called.split("::") if segment],
            current_module,
        )
        return "::".join(normalized)

    def _short_name(self, name: Optional[str]) -> Optional[str]:
        if not name:
            return None
        if "." in name:
            return name.rsplit(".", 1)[-1]
        if "::" in name:
            return name.rsplit("::", 1)[-1]
        return name

    def _module_from_symbol_name(self, name: str) -> Optional[str]:
        if not name:
            return None
        owner = name
        if "." in owner:
            owner = owner.rsplit(".", 1)[0]
        if "::" not in owner:
            return None
        return owner.rsplit("::", 1)[0]
