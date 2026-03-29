"""
PHP parsing strategy using tree-sitter.
"""

import logging
from typing import Dict, List, Tuple, Optional
from .base_strategy import ParsingStrategy
from ..models import SymbolInfo, FileInfo

logger = logging.getLogger(__name__)

import tree_sitter
from tree_sitter_php import language_php


class PhpParsingStrategy(ParsingStrategy):
    """PHP-specific parsing strategy using tree-sitter."""

    def __init__(self):
        self.php_language = tree_sitter.Language(language_php())

    def get_language_name(self) -> str:
        return "php"

    def get_supported_extensions(self) -> List[str]:
        return ['.php', '.phtml', '.php3', '.php4', '.php5', '.phps']

    def parse_file(self, file_path: str, content: str) -> Tuple[Dict[str, SymbolInfo], FileInfo]:
        """Parse PHP file using tree-sitter."""
        symbols = {}
        functions = []
        classes = []
        imports = []
        namespace = None

        # Symbol lookup index for O(1) access
        symbol_lookup: Dict[str, str] = {}

        parser = tree_sitter.Parser(self.php_language)

        try:
            # tree-sitter uses byte offsets — always parse bytes
            content_bytes = content.encode('utf8')
            tree = parser.parse(content_bytes)

            context = _TraversalContext(
                content_bytes=content_bytes,
                file_path=file_path,
                symbols=symbols,
                functions=functions,
                classes=classes,
                imports=imports,
                symbol_lookup=symbol_lookup,
            )

            self._traverse(tree.root_node, context)
            namespace = context.namespace

        except Exception as e:
            logger.warning(f"Error parsing PHP file {file_path}: {e}")

        file_info = FileInfo(
            language=self.get_language_name(),
            line_count=len(content.splitlines()),
            symbols={"functions": functions, "classes": classes},
            imports=imports,
            package=namespace,
        )

        return symbols, file_info

    def _traverse(self, node, context: '_TraversalContext',
                  current_class: Optional[str] = None,
                  current_method: Optional[str] = None) -> None:
        """Recursively traverse the AST and extract symbols."""

        node_type = node.type

        # ── Namespace declaration ──────────────────────────────────────────
        if node_type == 'namespace_definition':
            name_node = self._find_child_by_type(node, 'namespace_name')
            if name_node:
                context.namespace = self._bytes(context, name_node)
            for child in node.children:
                self._traverse(child, context, current_class, current_method)
            return

        # ── Use / import statements ────────────────────────────────────────
        if node_type in ('use_declaration', 'namespace_use_declaration'):
            # Extract the qualified name(s) from use clauses
            for child in node.children:
                if child.type in ('namespace_use_clause', 'qualified_name'):
                    import_path = self._bytes(context, child)
                    if import_path:
                        context.imports.append(import_path)
            return

        # ── Class / interface / trait declarations ─────────────────────────
        if node_type in ('class_declaration', 'interface_declaration',
                         'trait_declaration', 'enum_declaration'):
            name = self._get_name(node, context)
            if name:
                symbol_id = self._create_symbol_id(context.file_path, name)
                context.symbols[symbol_id] = SymbolInfo(
                    type="class",
                    file=context.file_path,
                    line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                )
                context.symbol_lookup[name] = symbol_id
                context.classes.append(name)

                for child in node.children:
                    self._traverse(child, context, current_class=name,
                                   current_method=current_method)
            return

        # ── Function / method declarations ─────────────────────────────────
        if node_type in ('function_definition', 'method_declaration'):
            name = self._get_name(node, context)
            if name:
                if current_class:
                    full_name = f"{current_class}.{name}"
                else:
                    full_name = name

                symbol_id = self._create_symbol_id(context.file_path, full_name)
                context.symbols[symbol_id] = SymbolInfo(
                    type="method" if current_class else "function",
                    file=context.file_path,
                    line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    signature=self._get_signature(node, context),
                )
                context.symbol_lookup[full_name] = symbol_id
                context.symbol_lookup[name] = symbol_id
                context.functions.append(full_name)

                for child in node.children:
                    self._traverse(child, context, current_class=current_class,
                                   current_method=symbol_id)
            return

        # ── Function / method calls ────────────────────────────────────────
        if node_type == 'function_call_expression' and current_method:
            called = self._get_called_name(node, context)
            if called and called in context.symbol_lookup:
                sid = context.symbol_lookup[called]
                sym = context.symbols[sid]
                if current_method not in sym.called_by:
                    sym.called_by.append(current_method)

        if node_type == 'member_call_expression' and current_method:
            called = self._get_member_call_name(node, context)
            if called:
                for lookup_name, sid in context.symbol_lookup.items():
                    if lookup_name.endswith(f".{called}"):
                        sym = context.symbols[sid]
                        if current_method not in sym.called_by:
                            sym.called_by.append(current_method)
                        break

        # ── Default: recurse into children ─────────────────────────────────
        for child in node.children:
            self._traverse(child, context, current_class, current_method)

    # ── Helpers ────────────────────────────────────────────────────────────

    def _bytes(self, context: '_TraversalContext', node) -> str:
        """Extract text from a node using byte offsets (correct for multi-byte UTF-8)."""
        try:
            return context.content_bytes[node.start_byte:node.end_byte].decode('utf8', errors='replace')
        except Exception:
            return ""

    def _find_child_by_type(self, node, child_type: str):
        for child in node.children:
            if child.type == child_type:
                return child
        return None

    def _get_name(self, node, context: '_TraversalContext') -> Optional[str]:
        """Extract the identifier name from a declaration node using byte offsets."""
        for child in node.children:
            if child.type == 'name':
                return self._bytes(context, child)
        return None

    def _get_signature(self, node, context: '_TraversalContext') -> str:
        """Extract the first line of a function/method as its signature."""
        try:
            raw = self._bytes(context, node)
            return raw.split('\n')[0].strip()
        except Exception:
            return ""

    def _get_called_name(self, node, context: '_TraversalContext') -> Optional[str]:
        """Extract the function name from a function_call_expression node."""
        for child in node.children:
            if child.type == 'name':
                return self._bytes(context, child)
        return None

    def _get_member_call_name(self, node, context: '_TraversalContext') -> Optional[str]:
        """Extract the method name from a member_call_expression node."""
        for child in node.children:
            if child.type == 'name':
                return self._bytes(context, child)
        return None


class _TraversalContext:
    """Context object passed during AST traversal."""

    def __init__(self, content_bytes: bytes, file_path: str, symbols: Dict,
                 functions: List, classes: List, imports: List,
                 symbol_lookup: Dict):
        self.content_bytes = content_bytes
        self.file_path = file_path
        self.symbols = symbols
        self.functions = functions
        self.classes = classes
        self.imports = imports
        self.symbol_lookup = symbol_lookup
        self.namespace: Optional[str] = None
