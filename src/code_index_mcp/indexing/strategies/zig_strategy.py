"""
Zig parsing strategy using tree-sitter.
"""

import logging
from typing import Dict, List, Tuple, Optional
from .base_strategy import ParsingStrategy
from ..models import SymbolInfo, FileInfo

logger = logging.getLogger(__name__)

import tree_sitter
from tree_sitter_zig import language


class ZigParsingStrategy(ParsingStrategy):
    """Zig parsing strategy using tree-sitter."""

    def __init__(self):
        self.zig_language = tree_sitter.Language(language())

    def get_language_name(self) -> str:
        return "zig"

    def get_supported_extensions(self) -> List[str]:
        return ['.zig', '.zon']

    def parse_file(self, file_path: str, content: str) -> Tuple[Dict[str, SymbolInfo], FileInfo]:
        """Parse Zig file using tree-sitter."""
        return self._tree_sitter_parse(file_path, content)


    def _tree_sitter_parse(self, file_path: str, content: str) -> Tuple[Dict[str, SymbolInfo], FileInfo]:
        """Parse Zig file using tree-sitter."""
        symbols = {}
        functions = []
        classes = []
        imports = []

        parser = tree_sitter.Parser(self.zig_language)
        tree = parser.parse(content.encode('utf8'))

        # Phase 1: Extract symbols using tree-sitter
        self._traverse_zig_node(tree.root_node, content, file_path, symbols, functions, classes, imports)

        file_info = FileInfo(
            language=self.get_language_name(),
            line_count=len(content.splitlines()),
            symbols={"functions": functions, "classes": classes},
            imports=imports
        )

        return symbols, file_info

    def _traverse_zig_node(self, node, content: str, file_path: str, symbols: Dict, functions: List, classes: List, imports: List):
        """Traverse Zig AST node and extract symbols."""
        if node.type == 'function_declaration':
            func_name = self._extract_zig_function_name_from_node(node, content)
            if func_name:
                line_number = self._extract_line_number(content, node.start_byte)
                symbol_id = self._create_symbol_id(file_path, func_name)
                symbols[symbol_id] = SymbolInfo(
                    type="function",
                    file=file_path,
                    line=line_number,
                    end_line=node.end_point[0] + 1,
                    signature=self._safe_extract_text(content, node.start_byte, node.end_byte)
                )
                functions.append(func_name)

        elif node.type in ['struct_declaration', 'union_declaration', 'enum_declaration']:
            type_name = self._extract_zig_type_name_from_node(node, content)
            if type_name:
                line_number = self._extract_line_number(content, node.start_byte)
                symbol_id = self._create_symbol_id(file_path, type_name)
                symbols[symbol_id] = SymbolInfo(
                    type=node.type.replace('_declaration', ''),
                    file=file_path,
                    line=line_number,
                    end_line=node.end_point[0] + 1
                )
                classes.append(type_name)

        # Recurse through children
        for child in node.children:
            self._traverse_zig_node(child, content, file_path, symbols, functions, classes, imports)

    def _extract_zig_function_name_from_node(self, node, content: str) -> Optional[str]:
        """Extract function name from tree-sitter node."""
        for child in node.children:
            if child.type == 'identifier':
                return self._safe_extract_text(content, child.start_byte, child.end_byte)
        return None

    def _extract_zig_type_name_from_node(self, node, content: str) -> Optional[str]:
        """Extract type name from tree-sitter node."""
        for child in node.children:
            if child.type == 'identifier':
                return self._safe_extract_text(content, child.start_byte, child.end_byte)
        return None

