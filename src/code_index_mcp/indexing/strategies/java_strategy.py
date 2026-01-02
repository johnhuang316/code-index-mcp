"""
Java parsing strategy using tree-sitter - Optimized single-pass version.
"""

import logging
from typing import Dict, List, Tuple, Optional, Set
from .base_strategy import ParsingStrategy
from ..models import SymbolInfo, FileInfo

logger = logging.getLogger(__name__)

import tree_sitter
from tree_sitter_java import language


class JavaParsingStrategy(ParsingStrategy):
    """Java-specific parsing strategy - Single Pass Optimized."""

    def __init__(self):
        self.java_language = tree_sitter.Language(language())

    def get_language_name(self) -> str:
        return "java"

    def get_supported_extensions(self) -> List[str]:
        return ['.java']

    def parse_file(self, file_path: str, content: str) -> Tuple[Dict[str, SymbolInfo], FileInfo]:
        """Parse Java file using tree-sitter with single-pass optimization."""
        symbols = {}
        functions = []
        classes = []
        imports = []
        package = None
        
        # Symbol lookup index for O(1) access
        symbol_lookup = {}  # name -> symbol_id mapping

        parser = tree_sitter.Parser(self.java_language)

        try:
            tree = parser.parse(content.encode('utf8'))
            
            # Extract package info first
            for node in tree.root_node.children:
                if node.type == 'package_declaration':
                    package = self._extract_java_package(node, content)
                    break
            
            # Single-pass traversal that handles everything
            context = TraversalContext(
                content=content,
                file_path=file_path,
                symbols=symbols,
                functions=functions,
                classes=classes,
                imports=imports,
                symbol_lookup=symbol_lookup
            )
            
            self._traverse_node_single_pass(tree.root_node, context)
            
        except Exception as e:
            logger.warning(f"Error parsing Java file {file_path}: {e}")

        file_info = FileInfo(
            language=self.get_language_name(),
            line_count=len(content.splitlines()),
            symbols={"functions": functions, "classes": classes},
            imports=imports,
            package=package
        )

        return symbols, file_info

    def _traverse_node_single_pass(self, node, context: 'TraversalContext', 
                                  current_class: Optional[str] = None,
                                  current_method: Optional[str] = None):
        """Single-pass traversal that extracts symbols and analyzes calls."""
        
        # Handle class declarations
        if node.type == 'class_declaration':
            name = self._get_java_class_name(node, context.content)
            if name:
                symbol_id = self._create_symbol_id(context.file_path, name)
                symbol_info = SymbolInfo(
                    type="class",
                    file=context.file_path,
                    line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1
                )
                context.symbols[symbol_id] = symbol_info
                context.symbol_lookup[name] = symbol_id
                context.classes.append(name)
                
                # Traverse class body with updated context
                for child in node.children:
                    self._traverse_node_single_pass(child, context, current_class=name, current_method=current_method)
                return
        
        # Handle method declarations
        elif node.type == 'method_declaration':
            name = self._get_java_method_name(node, context.content)
            if name:
                # Build full method name with class context
                if current_class:
                    full_name = f"{current_class}.{name}"
                else:
                    full_name = name
                
                symbol_id = self._create_symbol_id(context.file_path, full_name)
                symbol_info = SymbolInfo(
                    type="method",
                    file=context.file_path,
                    line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    signature=self._get_java_method_signature(node, context.content)
                )
                context.symbols[symbol_id] = symbol_info
                context.symbol_lookup[full_name] = symbol_id
                context.symbol_lookup[name] = symbol_id  # Also index by method name alone
                context.functions.append(full_name)
                
                # Traverse method body with updated context
                for child in node.children:
                    self._traverse_node_single_pass(child, context, current_class=current_class, 
                                                   current_method=symbol_id)
                return
        
        # Handle method invocations (calls)
        elif node.type == 'method_invocation':
            if current_method:
                called_method = self._get_called_method_name(node, context.content)
                if called_method:
                    # Use O(1) lookup instead of O(n) iteration
                    if called_method in context.symbol_lookup:
                        symbol_id = context.symbol_lookup[called_method]
                        symbol_info = context.symbols[symbol_id]
                        if current_method not in symbol_info.called_by:
                            symbol_info.called_by.append(current_method)
                    else:
                        # Try to find method with class prefix
                        for name, sid in context.symbol_lookup.items():
                            if name.endswith(f".{called_method}"):
                                symbol_info = context.symbols[sid]
                                if current_method not in symbol_info.called_by:
                                    symbol_info.called_by.append(current_method)
                                break
        
        # Handle import declarations
        elif node.type == 'import_declaration':
            import_text = context.content[node.start_byte:node.end_byte]
            # Extract the import path (remove 'import' keyword and semicolon)
            import_path = import_text.replace('import', '').replace(';', '').strip()
            if import_path:
                context.imports.append(import_path)
        
        # Continue traversing children for other node types
        for child in node.children:
            self._traverse_node_single_pass(child, context, current_class=current_class, 
                                           current_method=current_method)

    def _get_java_class_name(self, node, content: str) -> Optional[str]:
        for child in node.children:
            if child.type == 'identifier':
                return content[child.start_byte:child.end_byte]
        return None

    def _get_java_method_name(self, node, content: str) -> Optional[str]:
        for child in node.children:
            if child.type == 'identifier':
                return content[child.start_byte:child.end_byte]
        return None

    def _get_java_method_signature(self, node, content: str) -> str:
        return content[node.start_byte:node.end_byte].split('\n')[0].strip()

    def _extract_java_package(self, node, content: str) -> Optional[str]:
        for child in node.children:
            if child.type == 'scoped_identifier':
                return content[child.start_byte:child.end_byte]
        return None

    def _get_called_method_name(self, node, content: str) -> Optional[str]:
        """Extract called method name from method invocation node."""
        # Handle obj.method() pattern - look for the method name after the dot
        for child in node.children:
            if child.type == 'field_access':
                # For field_access nodes, get the field (method) name
                for subchild in child.children:
                    if subchild.type == 'identifier' and subchild.start_byte > child.start_byte:
                        # Get the rightmost identifier (the method name)
                        return content[subchild.start_byte:subchild.end_byte]
            elif child.type == 'identifier':
                # Direct method call without object reference
                return content[child.start_byte:child.end_byte]
        return None


class TraversalContext:
    """Context object to pass state during single-pass traversal."""
    
    def __init__(self, content: str, file_path: str, symbols: Dict, 
                 functions: List, classes: List, imports: List, symbol_lookup: Dict):
        self.content = content
        self.file_path = file_path
        self.symbols = symbols
        self.functions = functions
        self.classes = classes
        self.imports = imports
        self.symbol_lookup = symbol_lookup