"""
TypeScript parsing strategy using tree-sitter - Optimized single-pass version.
"""

import logging
from typing import Dict, List, Tuple, Optional, Set
from .base_strategy import ParsingStrategy
from ..models import SymbolInfo, FileInfo

logger = logging.getLogger(__name__)

import tree_sitter
from tree_sitter_typescript import language_typescript


class TypeScriptParsingStrategy(ParsingStrategy):
    """TypeScript-specific parsing strategy using tree-sitter - Single Pass Optimized."""

    def __init__(self):
        self.ts_language = tree_sitter.Language(language_typescript())

    def get_language_name(self) -> str:
        return "typescript"

    def get_supported_extensions(self) -> List[str]:
        return ['.ts', '.tsx']

    def parse_file(self, file_path: str, content: str) -> Tuple[Dict[str, SymbolInfo], FileInfo]:
        """Parse TypeScript file using tree-sitter with single-pass optimization."""
        symbols = {}
        functions = []
        classes = []
        imports = []
        exports = []

        # Symbol lookup index for O(1) access
        symbol_lookup = {}  # name -> symbol_id mapping
        pending_calls: List[Tuple[str, str]] = []
        pending_call_set: Set[Tuple[str, str]] = set()
        variable_scopes: List[Dict[str, str]] = [{}]

        parser = tree_sitter.Parser(self.ts_language)
        tree = parser.parse(content.encode('utf8'))

        # Single-pass traversal that handles everything
        context = TraversalContext(
            content=content,
            file_path=file_path,
            symbols=symbols,
            functions=functions,
            classes=classes,
            imports=imports,
            exports=exports,
            symbol_lookup=symbol_lookup,
            pending_calls=pending_calls,
            pending_call_set=pending_call_set,
            variable_scopes=variable_scopes,
        )

        self._traverse_node_single_pass(tree.root_node, context)

        file_info = FileInfo(
            language=self.get_language_name(),
            line_count=len(content.splitlines()),
            symbols={"functions": functions, "classes": classes},
            imports=imports,
            exports=exports
        )

        if context.pending_calls:
            file_info.pending_calls = context.pending_calls

        return symbols, file_info

    def _traverse_node_single_pass(self, node, context: 'TraversalContext',
                                  current_function: Optional[str] = None,
                                  current_class: Optional[str] = None):
        """Single-pass traversal that extracts symbols and analyzes calls."""

        node_type = node.type

        # Handle function declarations
        if node_type == 'function_declaration':
            name = self._get_function_name(node, context.content)
            if name:
                symbol_id = self._create_symbol_id(context.file_path, name)
                signature = self._get_ts_function_signature(node, context.content)
                symbol_info = SymbolInfo(
                    type="function",
                    file=context.file_path,
                    line=node.start_point[0] + 1,
                    signature=signature
                )
                context.symbols[symbol_id] = symbol_info
                context.symbol_lookup[name] = symbol_id
                context.functions.append(name)

                # Traverse function body with updated context
                func_context = f"{context.file_path}::{name}"
                for child in node.children:
                    self._traverse_node_single_pass(child, context, current_function=func_context,
                                                   current_class=current_class)
                return

        # Handle class declarations
        elif node_type == 'class_declaration':
            name = self._get_class_name(node, context.content)
            if name:
                symbol_id = self._create_symbol_id(context.file_path, name)
                symbol_info = SymbolInfo(
                    type="class",
                    file=context.file_path,
                    line=node.start_point[0] + 1
                )
                context.symbols[symbol_id] = symbol_info
                context.symbol_lookup[name] = symbol_id
                context.classes.append(name)

                # Traverse class body with updated context
                for child in node.children:
                    self._traverse_node_single_pass(child, context, current_function=current_function,
                                                   current_class=name)
                return

        # Handle interface declarations
        elif node_type == 'interface_declaration':
            name = self._get_interface_name(node, context.content)
            if name:
                symbol_id = self._create_symbol_id(context.file_path, name)
                symbol_info = SymbolInfo(
                    type="interface",
                    file=context.file_path,
                    line=node.start_point[0] + 1
                )
                context.symbols[symbol_id] = symbol_info
                context.symbol_lookup[name] = symbol_id
                context.classes.append(name)  # Group interfaces with classes

                # Traverse interface body with updated context
                for child in node.children:
                    self._traverse_node_single_pass(child, context, current_function=current_function,
                                                   current_class=name)
                return

        # Handle method definitions
        elif node_type == 'method_definition':
            method_name = self._get_method_name(node, context.content)
            if method_name and current_class:
                full_name = f"{current_class}.{method_name}"
                symbol_id = self._create_symbol_id(context.file_path, full_name)
                signature = self._get_ts_function_signature(node, context.content)
                symbol_info = SymbolInfo(
                    type="method",
                    file=context.file_path,
                    line=node.start_point[0] + 1,
                    signature=signature
                )
                context.symbols[symbol_id] = symbol_info
                context.symbol_lookup[full_name] = symbol_id
                context.symbol_lookup[method_name] = symbol_id  # Also index by method name alone
                context.functions.append(full_name)

                # Traverse method body with updated context
                method_context = f"{context.file_path}::{full_name}"
                for child in node.children:
                    self._traverse_node_single_pass(child, context, current_function=method_context,
                                                   current_class=current_class)
                return

        # Handle variable declarations that define callable exports
        elif node_type in ['lexical_declaration', 'variable_statement']:
            handled = False
            for child in node.children:
                if child.type != 'variable_declarator':
                    continue
                name_node = child.child_by_field_name('name')
                value_node = child.child_by_field_name('value')
                if not name_node or not value_node:
                    continue

                if current_function is not None:
                    continue

                value_type = value_node.type
                if value_type not in [
                    'arrow_function',
                    'function',
                    'function_expression',
                    'call_expression',
                    'new_expression',
                    'identifier',
                    'member_expression',
                ]:
                    continue

                name = context.content[name_node.start_byte:name_node.end_byte]
                symbol_id = self._create_symbol_id(context.file_path, name)
                signature = context.content[child.start_byte:child.end_byte].split('\n')[0].strip()
                symbol_info = SymbolInfo(
                    type="function",
                    file=context.file_path,
                    line=child.start_point[0] + 1,
                    signature=signature
                )
                context.symbols[symbol_id] = symbol_info
                context.symbol_lookup[name] = symbol_id
                context.functions.append(name)
                handled = True

                if value_type in ['arrow_function', 'function', 'function_expression']:
                    func_context = f"{context.file_path}::{name}"
                    context.variable_scopes.append({})
                    self._traverse_node_single_pass(
                        value_node,
                        context,
                        current_function=func_context,
                        current_class=current_class
                    )
                    context.variable_scopes.pop()

            if handled:
                return

        # Handle function calls
        elif node_type == 'call_expression':
            caller = current_function or f"{context.file_path}:{node.start_point[0] + 1}"
            called_function = self._resolve_called_function(node, context, current_class)
            if caller and called_function:
                self._register_call(context, caller, called_function)
            if caller:
                self._collect_callback_arguments(node, context, caller, current_class, current_function)

        # Handle import declarations
        elif node.type == 'import_statement':
            import_text = context.content[node.start_byte:node.end_byte]
            context.imports.append(import_text)

        # Handle export declarations
        elif node.type in ['export_statement', 'export_default_declaration']:
            export_text = context.content[node.start_byte:node.end_byte]
            context.exports.append(export_text)

        # Continue traversing children for other node types
        for child in node.children:
            self._traverse_node_single_pass(child, context, current_function=current_function,
                                           current_class=current_class)

    def _register_call(self, context: 'TraversalContext', caller: str, called: str) -> None:
        if called in context.symbol_lookup:
            symbol_id = context.symbol_lookup[called]
            symbol_info = context.symbols[symbol_id]
            if caller not in symbol_info.called_by:
                symbol_info.called_by.append(caller)
            return

        key = (caller, called)
        if key not in context.pending_call_set:
            context.pending_call_set.add(key)
            context.pending_calls.append(key)

    def _collect_callback_arguments(
        self,
        node,
        context: 'TraversalContext',
        caller: str,
        current_class: Optional[str],
        current_function: Optional[str]
    ) -> None:
        arguments_node = node.child_by_field_name('arguments')
        if not arguments_node:
            return

        for argument in arguments_node.children:
            if not getattr(argument, "is_named", False):
                continue
            callback_name = self._resolve_argument_reference(argument, context, current_class)
            if callback_name:
                call_site = caller
                if current_function is None:
                    call_site = f"{context.file_path}:{argument.start_point[0] + 1}"
                self._register_call(context, call_site, callback_name)

    def _resolve_argument_reference(
        self,
        node,
        context: 'TraversalContext',
        current_class: Optional[str]
    ) -> Optional[str]:
        node_type = node.type

        if node_type == 'identifier':
            return context.content[node.start_byte:node.end_byte]

        if node_type == 'member_expression':
            property_node = node.child_by_field_name('property')
            if property_node is None:
                for child in node.children:
                    if child.type in ['property_identifier', 'identifier']:
                        property_node = child
                        break
            if property_node is None:
                return None

            property_name = context.content[property_node.start_byte:property_node.end_byte]
            qualifier_node = node.child_by_field_name('object')
            qualifier = self._resolve_member_qualifier(
                qualifier_node,
                context,
                current_class
            )
            if not qualifier:
                for child in node.children:
                    if child is property_node:
                        continue
                    qualifier = self._resolve_member_qualifier(
                        child,
                        context,
                        current_class
                    )
                    if qualifier:
                        break
            if qualifier:
                return f"{qualifier}.{property_name}"
            return property_name

        return None

    def _resolve_called_function(
        self,
        node,
        context: 'TraversalContext',
        current_class: Optional[str]
    ) -> Optional[str]:
        function_node = node.child_by_field_name('function')
        if function_node is None and node.children:
            function_node = node.children[0]
        if function_node is None:
            return None

        if function_node.type == 'identifier':
            return context.content[function_node.start_byte:function_node.end_byte]

        if function_node.type == 'member_expression':
            property_node = function_node.child_by_field_name('property')
            if property_node is None:
                for child in function_node.children:
                    if child.type in ['property_identifier', 'identifier']:
                        property_node = child
                        break
            if property_node is None:
                return None

            property_name = context.content[property_node.start_byte:property_node.end_byte]
            qualifier_node = function_node.child_by_field_name('object')
            qualifier = self._resolve_member_qualifier(
                qualifier_node,
                context,
                current_class
            )
            if not qualifier:
                for child in function_node.children:
                    if child is property_node:
                        continue
                    qualifier = self._resolve_member_qualifier(
                        child,
                        context,
                        current_class
                    )
                    if qualifier:
                        break
            if qualifier:
                return f"{qualifier}.{property_name}"
            return property_name

        return None

    def _resolve_member_qualifier(
        self,
        node,
        context: 'TraversalContext',
        current_class: Optional[str]
    ) -> Optional[str]:
        if node is None:
            return None

        node_type = node.type
        if node_type == 'this':
            return current_class

        if node_type == 'identifier':
            return context.content[node.start_byte:node.end_byte]

        if node_type == 'member_expression':
            property_node = node.child_by_field_name('property')
            if property_node is None:
                for child in node.children:
                    if child.type in ['property_identifier', 'identifier']:
                        property_node = child
                        break
            if property_node is None:
                return None

            qualifier = self._resolve_member_qualifier(
                node.child_by_field_name('object'),
                context,
                current_class
            )
            if not qualifier:
                for child in node.children:
                    if child is property_node:
                        continue
                    qualifier = self._resolve_member_qualifier(
                        child,
                        context,
                        current_class
                    )
                    if qualifier:
                        break

            property_name = context.content[property_node.start_byte:property_node.end_byte]
            if qualifier:
                return f"{qualifier}.{property_name}"
            return property_name

        return None

    def _get_function_name(self, node, content: str) -> Optional[str]:
        """Extract function name from tree-sitter node."""
        for child in node.children:
            if child.type == 'identifier':
                return content[child.start_byte:child.end_byte]
        return None

    def _get_class_name(self, node, content: str) -> Optional[str]:
        """Extract class name from tree-sitter node."""
        for child in node.children:
            if child.type == 'identifier':
                return content[child.start_byte:child.end_byte]
        return None

    def _get_interface_name(self, node, content: str) -> Optional[str]:
        """Extract interface name from tree-sitter node."""
        for child in node.children:
            if child.type == 'type_identifier':
                return content[child.start_byte:child.end_byte]
        return None

    def _get_method_name(self, node, content: str) -> Optional[str]:
        """Extract method name from tree-sitter node."""
        for child in node.children:
            if child.type == 'property_identifier':
                return content[child.start_byte:child.end_byte]
        return None

    def _get_ts_function_signature(self, node, content: str) -> str:
        """Extract TypeScript function signature."""
        return content[node.start_byte:node.end_byte].split('\n')[0].strip()


class TraversalContext:
    """Context object to pass state during single-pass traversal."""

    def __init__(
        self,
        content: str,
        file_path: str,
        symbols: Dict,
        functions: List,
        classes: List,
        imports: List,
        exports: List,
        symbol_lookup: Dict,
        pending_calls: List[Tuple[str, str]],
        pending_call_set: Set[Tuple[str, str]],
        variable_scopes: List[Dict[str, str]],
    ):
        self.content = content
        self.file_path = file_path
        self.symbols = symbols
        self.functions = functions
        self.classes = classes
        self.imports = imports
        self.exports = exports
        self.symbol_lookup = symbol_lookup
        self.pending_calls = pending_calls
        self.pending_call_set = pending_call_set
        self.variable_scopes = variable_scopes
