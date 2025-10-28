"""
JavaScript parsing strategy using tree-sitter.
"""

import logging
from typing import Dict, List, Tuple, Optional, Set

import tree_sitter
from tree_sitter_javascript import language

from .base_strategy import ParsingStrategy
from ..models import SymbolInfo, FileInfo

logger = logging.getLogger(__name__)


class JavaScriptParsingStrategy(ParsingStrategy):
    """JavaScript-specific parsing strategy using tree-sitter."""

    def __init__(self):
        self.js_language = tree_sitter.Language(language())

    def get_language_name(self) -> str:
        return "javascript"

    def get_supported_extensions(self) -> List[str]:
        return ['.js', '.jsx', '.mjs', '.cjs']

    def parse_file(self, file_path: str, content: str) -> Tuple[Dict[str, SymbolInfo], FileInfo]:
        """Parse JavaScript file using tree-sitter."""
        symbols: Dict[str, SymbolInfo] = {}
        functions: List[str] = []
        classes: List[str] = []
        imports: List[str] = []
        exports: List[str] = []
        symbol_lookup: Dict[str, str] = {}
        pending_calls: List[Tuple[str, str]] = []
        pending_call_set: Set[Tuple[str, str]] = set()
        variable_scopes: List[Dict[str, str]] = [{}]

        parser = tree_sitter.Parser(self.js_language)
        tree = parser.parse(content.encode('utf8'))
        self._traverse_js_node(
            tree.root_node,
            content,
            file_path,
            symbols,
            functions,
            classes,
            imports,
            exports,
            symbol_lookup,
            pending_calls,
            pending_call_set,
            variable_scopes,
        )

        file_info = FileInfo(
            language=self.get_language_name(),
            line_count=len(content.splitlines()),
            symbols={"functions": functions, "classes": classes},
            imports=imports,
            exports=exports
        )

        if pending_calls:
            file_info.pending_calls = pending_calls

        return symbols, file_info

    def _traverse_js_node(
        self,
        node,
        content: str,
        file_path: str,
        symbols: Dict[str, SymbolInfo],
        functions: List[str],
        classes: List[str],
        imports: List[str],
        exports: List[str],
        symbol_lookup: Dict[str, str],
        pending_calls: List[Tuple[str, str]],
        pending_call_set: Set[Tuple[str, str]],
        variable_scopes: List[Dict[str, str]],
        current_function: Optional[str] = None,
        current_class: Optional[str] = None,
    ):
        """Traverse JavaScript AST node and collect symbols and relationships."""
        node_type = node.type

        if node_type == 'function_declaration':
            name = self._get_function_name(node, content)
            if name:
                symbol_id = self._create_symbol_id(file_path, name)
                signature = self._get_js_function_signature(node, content)
                symbols[symbol_id] = SymbolInfo(
                    type="function",
                    file=file_path,
                    line=node.start_point[0] + 1,
                    signature=signature
                )
                symbol_lookup[name] = symbol_id
                functions.append(name)
                function_id = f"{file_path}::{name}"
                variable_scopes.append({})
                for child in node.children:
                    self._traverse_js_node(
                        child,
                        content,
                        file_path,
                        symbols,
                        functions,
                        classes,
                        imports,
                        exports,
                        symbol_lookup,
                        pending_calls,
                        pending_call_set,
                        variable_scopes,
                        current_function=function_id,
                        current_class=current_class,
                    )
                variable_scopes.pop()
            return

        if node_type == 'class_declaration':
            name = self._get_class_name(node, content)
            if name:
                symbol_id = self._create_symbol_id(file_path, name)
                symbols[symbol_id] = SymbolInfo(
                    type="class",
                    file=file_path,
                    line=node.start_point[0] + 1
                )
                symbol_lookup[name] = symbol_id
                classes.append(name)
                for child in node.children:
                    self._traverse_js_node(
                        child,
                        content,
                        file_path,
                        symbols,
                        functions,
                        classes,
                        imports,
                        exports,
                        symbol_lookup,
                        pending_calls,
                        pending_call_set,
                        variable_scopes,
                        current_function=current_function,
                        current_class=name,
                    )
                return

        if node_type == 'method_definition':
            method_name = self._get_method_name(node, content)
            class_name = current_class or self._find_parent_class(node, content)
            if method_name and class_name:
                full_name = f"{class_name}.{method_name}"
                symbol_id = self._create_symbol_id(file_path, full_name)
                signature = self._get_js_function_signature(node, content)
                symbols[symbol_id] = SymbolInfo(
                    type="method",
                    file=file_path,
                    line=node.start_point[0] + 1,
                    signature=signature
                )
                symbol_lookup[full_name] = symbol_id
                symbol_lookup[method_name] = symbol_id
                functions.append(full_name)
                function_id = f"{file_path}::{full_name}"
                variable_scopes.append({})
                for child in node.children:
                    self._traverse_js_node(
                        child,
                        content,
                        file_path,
                        symbols,
                        functions,
                        classes,
                        imports,
                        exports,
                        symbol_lookup,
                        pending_calls,
                        pending_call_set,
                        variable_scopes,
                        current_function=function_id,
                        current_class=class_name,
                    )
                variable_scopes.pop()
            return

        if node_type in ['lexical_declaration', 'variable_declaration']:
            for child in node.children:
                if child.type != 'variable_declarator':
                    self._traverse_js_node(
                        child,
                        content,
                        file_path,
                        symbols,
                        functions,
                        classes,
                        imports,
                        exports,
                        symbol_lookup,
                        pending_calls,
                        pending_call_set,
                        variable_scopes,
                        current_function=current_function,
                        current_class=current_class,
                    )
                    continue

                name_node = child.child_by_field_name('name')
                value_node = child.child_by_field_name('value')
                if not name_node:
                    continue

                name = self._get_node_text(name_node, content)

                if value_node and value_node.type in ['arrow_function', 'function_expression', 'function']:
                    symbol_id = self._create_symbol_id(file_path, name)
                    signature = content[child.start_byte:child.end_byte].split('\n')[0].strip()
                    symbols[symbol_id] = SymbolInfo(
                        type="function",
                        file=file_path,
                        line=child.start_point[0] + 1,
                        signature=signature
                    )
                    symbol_lookup[name] = symbol_id
                    functions.append(name)
                    function_id = f"{file_path}::{name}"
                    variable_scopes.append({})
                    self._traverse_js_node(
                        value_node,
                        content,
                        file_path,
                        symbols,
                        functions,
                        classes,
                        imports,
                        exports,
                        symbol_lookup,
                        pending_calls,
                        pending_call_set,
                        variable_scopes,
                        current_function=function_id,
                        current_class=current_class,
                    )
                    variable_scopes.pop()
                else:
                    inferred = self._infer_expression_type(value_node, content)
                    if inferred:
                        self._set_variable_type(variable_scopes, name, inferred)
                    if value_node:
                        self._traverse_js_node(
                            value_node,
                            content,
                            file_path,
                            symbols,
                            functions,
                            classes,
                            imports,
                            exports,
                            symbol_lookup,
                            pending_calls,
                            pending_call_set,
                            variable_scopes,
                            current_function=current_function,
                            current_class=current_class,
                        )
            return

        if node_type == 'arrow_function':
            variable_scopes.append({})
            for child in node.children:
                self._traverse_js_node(
                    child,
                    content,
                    file_path,
                    symbols,
                    functions,
                    classes,
                    imports,
                    exports,
                    symbol_lookup,
                    pending_calls,
                    pending_call_set,
                    variable_scopes,
                    current_function=current_function,
                    current_class=current_class,
                )
            variable_scopes.pop()
            return

        if node_type == 'call_expression':
            caller = current_function or f"{file_path}:{node.start_point[0] + 1}"
            called = self._resolve_called_function(
                node,
                content,
                variable_scopes,
                current_class
            )
            if caller and called:
                self._register_call(
                    symbols,
                    symbol_lookup,
                    pending_calls,
                    pending_call_set,
                    caller,
                    called
                )
            if caller:
                self._collect_callback_arguments(
                    node,
                    content,
                    symbols,
                    symbol_lookup,
                    pending_calls,
                    pending_call_set,
                    variable_scopes,
                    current_class,
                    caller
                )

        if node_type in ['import_statement', 'require_call']:
            import_text = self._get_node_text(node, content)
            imports.append(import_text)
        elif node_type in ['export_statement', 'export_clause', 'export_default_declaration']:
            exports.append(self._get_node_text(node, content))

        for child in node.children:
            self._traverse_js_node(
                child,
                content,
                file_path,
                symbols,
                functions,
                classes,
                imports,
                exports,
                symbol_lookup,
                pending_calls,
                pending_call_set,
                variable_scopes,
                current_function=current_function,
                current_class=current_class,
            )

    def _collect_callback_arguments(
        self,
        call_node,
        content: str,
        symbols: Dict[str, SymbolInfo],
        symbol_lookup: Dict[str, str],
        pending_calls: List[Tuple[str, str]],
        pending_call_set: Set[Tuple[str, str]],
        variable_scopes: List[Dict[str, str]],
        current_class: Optional[str],
        caller: str
    ) -> None:
        """Capture identifier callbacks passed as call expression arguments."""
        arguments_node = call_node.child_by_field_name('arguments')
        if not arguments_node:
            return

        for argument in arguments_node.children:
            if not getattr(argument, "is_named", False):
                continue
            callback_name = self._resolve_argument_reference(
                argument,
                content,
                variable_scopes,
                current_class
            )
            if not callback_name:
                continue
            self._register_call(
                symbols,
                symbol_lookup,
                pending_calls,
                pending_call_set,
                caller,
                callback_name
            )

    def _resolve_argument_reference(
        self,
        node,
        content: str,
        variable_scopes: List[Dict[str, str]],
        current_class: Optional[str]
    ) -> Optional[str]:
        """Resolve a potential callback reference used as an argument."""
        node_type = node.type

        if node_type == 'identifier':
            return self._get_node_text(node, content)

        if node_type == 'member_expression':
            property_node = node.child_by_field_name('property')
            if property_node is None:
                for child in node.children:
                    if child.type in ['property_identifier', 'identifier']:
                        property_node = child
                        break
            if property_node is None:
                return None

            property_name = self._get_node_text(property_node, content)
            qualifier_node = node.child_by_field_name('object')
            qualifier = None
            if qualifier_node is not None:
                qualifier = self._resolve_member_qualifier(
                    qualifier_node,
                    content,
                    variable_scopes,
                    current_class
                )
            if not qualifier:
                for child in node.children:
                    if child is property_node:
                        continue
                    qualifier = self._resolve_member_qualifier(
                        child,
                        content,
                        variable_scopes,
                        current_class
                    )
                    if qualifier:
                        break
            if qualifier:
                return f"{qualifier}.{property_name}"
            return property_name

        if node_type in ['call_expression', 'arrow_function', 'function', 'function_expression']:
            return None

        return None

    def _get_function_name(self, node, content: str) -> Optional[str]:
        """Extract function name from tree-sitter node."""
        for child in node.children:
            if child.type == 'identifier':
                return self._get_node_text(child, content)
        return None

    def _get_class_name(self, node, content: str) -> Optional[str]:
        """Extract class name from tree-sitter node."""
        for child in node.children:
            if child.type == 'identifier':
                return self._get_node_text(child, content)
        return None

    def _get_method_name(self, node, content: str) -> Optional[str]:
        """Extract method name from tree-sitter node."""
        for child in node.children:
            if child.type == 'property_identifier':
                return self._get_node_text(child, content)
        return None

    def _find_parent_class(self, node, content: str) -> Optional[str]:
        """Find the parent class of a method."""
        parent = node.parent
        while parent:
            if parent.type == 'class_declaration':
                return self._get_class_name(parent, content)
            parent = parent.parent
        return None

    def _get_js_function_signature(self, node, content: str) -> str:
        """Extract JavaScript function signature."""
        return content[node.start_byte:node.end_byte].split('\n')[0].strip()

    def _get_node_text(self, node, content: str) -> str:
        return content[node.start_byte:node.end_byte]

    def _set_variable_type(self, variable_scopes: List[Dict[str, str]], name: str, value: str) -> None:
        if not variable_scopes:
            return
        variable_scopes[-1][name] = value

    def _lookup_variable_type(self, variable_scopes: List[Dict[str, str]], name: str) -> Optional[str]:
        for scope in reversed(variable_scopes):
            if name in scope:
                return scope[name]
        return None

    def _infer_expression_type(self, node, content: str) -> Optional[str]:
        """Infer the class/type from a simple expression like `new ClassName()`."""
        if node is None:
            return None

        if node.type == 'new_expression':
            constructor_node = node.child_by_field_name('constructor')
            if constructor_node is None:
                # Fallback: first identifier or member expression child
                for child in node.children:
                    if child.type in ['identifier', 'member_expression']:
                        constructor_node = child
                        break

            if constructor_node:
                if constructor_node.type == 'identifier':
                    return self._get_node_text(constructor_node, content)
                if constructor_node.type == 'member_expression':
                    property_node = constructor_node.child_by_field_name('property')
                    if property_node:
                        return self._get_node_text(property_node, content)
                    for child in reversed(constructor_node.children):
                        if child.type in ['identifier', 'property_identifier']:
                            return self._get_node_text(child, content)
        return None

    def _resolve_called_function(
        self,
        node,
        content: str,
        variable_scopes: List[Dict[str, str]],
        current_class: Optional[str]
    ) -> Optional[str]:
        function_node = node.child_by_field_name('function')
        if function_node is None and node.children:
            function_node = node.children[0]
        if function_node is None:
            return None

        if function_node.type == 'identifier':
            return self._get_node_text(function_node, content)

        if function_node.type == 'member_expression':
            property_node = function_node.child_by_field_name('property')
            if property_node is None:
                for child in function_node.children:
                    if child.type in ['property_identifier', 'identifier']:
                        property_node = child
                        break
            if property_node is None:
                return None

            property_name = self._get_node_text(property_node, content)
            object_node = function_node.child_by_field_name('object')
            qualifier = None
            if object_node is not None:
                qualifier = self._resolve_member_qualifier(
                    object_node,
                    content,
                    variable_scopes,
                    current_class
                )
            else:
                for child in function_node.children:
                    if child is property_node:
                        continue
                    qualifier = self._resolve_member_qualifier(
                        child,
                        content,
                        variable_scopes,
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
        content: str,
        variable_scopes: List[Dict[str, str]],
        current_class: Optional[str]
    ) -> Optional[str]:
        node_type = node.type
        if node_type == 'this':
            return current_class

        if node_type == 'identifier':
            name = self._get_node_text(node, content)
            var_type = self._lookup_variable_type(variable_scopes, name)
            return var_type or name

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
                content,
                variable_scopes,
                current_class
            )
            property_name = self._get_node_text(property_node, content)
            if qualifier:
                return f"{qualifier}.{property_name}"
            return property_name

        return None

    def _register_call(
        self,
        symbols: Dict[str, SymbolInfo],
        symbol_lookup: Dict[str, str],
        pending_calls: List[Tuple[str, str]],
        pending_call_set: Set[Tuple[str, str]],
        caller: str,
        called: str
    ) -> None:
        if called in symbol_lookup:
            symbol_info = symbols[symbol_lookup[called]]
            if caller not in symbol_info.called_by:
                symbol_info.called_by.append(caller)
            return

        key = (caller, called)
        if key not in pending_call_set:
            pending_call_set.add(key)
            pending_calls.append(key)
