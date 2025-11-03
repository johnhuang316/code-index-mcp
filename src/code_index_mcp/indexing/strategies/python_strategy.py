"""
Python parsing strategy using AST - Optimized single-pass version.
"""

import ast
import logging
from typing import Dict, List, Tuple, Optional, Set
from .base_strategy import ParsingStrategy
from ..models import SymbolInfo, FileInfo

logger = logging.getLogger(__name__)


class PythonParsingStrategy(ParsingStrategy):
    """Python-specific parsing strategy using Python's built-in AST - Single Pass Optimized."""
    
    def get_language_name(self) -> str:
        return "python"
    
    def get_supported_extensions(self) -> List[str]:
        return ['.py', '.pyw']
    
    def parse_file(self, file_path: str, content: str) -> Tuple[Dict[str, SymbolInfo], FileInfo]:
        """Parse Python file using AST with single-pass optimization."""
        symbols = {}
        functions = []
        classes = []
        imports = []
        
        try:
            tree = ast.parse(content)
            # Single-pass visitor that handles everything at once
            visitor = SinglePassVisitor(symbols, functions, classes, imports, file_path)
            visitor.visit(tree)
        except SyntaxError as e:
            logger.warning(f"Syntax error in Python file {file_path}: {e}")
        except Exception as e:
            logger.warning(f"Error parsing Python file {file_path}: {e}")
        
        file_info = FileInfo(
            language=self.get_language_name(),
            line_count=len(content.splitlines()),
            symbols={"functions": functions, "classes": classes},
            imports=imports
        )

        pending_calls = visitor.resolve_deferred_calls()
        if pending_calls:
            file_info.pending_calls = pending_calls
        
        return symbols, file_info


class SinglePassVisitor(ast.NodeVisitor):
    """Single-pass AST visitor that extracts symbols and analyzes calls in one traversal."""
    
    def __init__(self, symbols: Dict[str, SymbolInfo], functions: List[str], 
                 classes: List[str], imports: List[str], file_path: str):
        self.symbols = symbols
        self.functions = functions
        self.classes = classes
        self.imports = imports
        self.file_path = file_path
        
        # Context tracking for call analysis
        self.current_function_stack = []
        self.current_class = None
        self.variable_type_stack: List[Dict[str, str]] = [{}]
        
        # Symbol lookup index for O(1) access
        self.symbol_lookup = {}  # name -> symbol_id mapping for fast lookups
        
        # Track processed nodes to avoid duplicates
        self.processed_nodes: Set[int] = set()
        # Deferred call relationships for forward references
        self.deferred_calls: List[Tuple[str, str]] = []
    
    def visit_ClassDef(self, node: ast.ClassDef):
        """Visit class definition - extract symbol and analyze in single pass."""
        class_name = node.name
        symbol_id = self._create_symbol_id(self.file_path, class_name)
        
        # Extract docstring
        docstring = ast.get_docstring(node)
        
        # Create symbol info
        symbol_info = SymbolInfo(
            type="class",
            file=self.file_path,
            line=node.lineno,
            docstring=docstring
        )
        
        # Store in symbols and lookup index
        self.symbols[symbol_id] = symbol_info
        self.symbol_lookup[class_name] = symbol_id
        self.classes.append(class_name)
        
        # Track class context for method processing
        old_class = self.current_class
        self.current_class = class_name
        
        method_nodes = []
        # First pass: register methods so forward references resolve
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._register_method(child, class_name)
                method_nodes.append(child)
            else:
                self.visit(child)

        # Second pass: visit method bodies for call analysis
        for method_node in method_nodes:
            self._visit_registered_method(method_node, class_name)
        
        # Restore previous class context
        self.current_class = old_class
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Visit function definition - extract symbol and track context."""
        self._process_function(node)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Visit async function definition - extract symbol and track context."""
        self._process_function(node)
    
    def _process_function(self, node):
        """Process both sync and async function definitions."""
        # Skip if this is a method (already handled by ClassDef)
        if self.current_class:
            return
        
        # Skip if already processed
        node_id = id(node)
        if node_id in self.processed_nodes:
            return
        self.processed_nodes.add(node_id)
        
        func_name = node.name
        symbol_id = self._create_symbol_id(self.file_path, func_name)
        
        # Extract function signature and docstring
        signature = self._extract_function_signature(node)
        docstring = ast.get_docstring(node)
        
        # Create symbol info
        symbol_info = SymbolInfo(
            type="function",
            file=self.file_path,
            line=node.lineno,
            signature=signature,
            docstring=docstring
        )
        
        # Store in symbols and lookup index
        self.symbols[symbol_id] = symbol_info
        self.symbol_lookup[func_name] = symbol_id
        self.functions.append(func_name)
        
        # Track function context for call analysis
        function_id = f"{self.file_path}::{func_name}"
        self.variable_type_stack.append({})
        self.current_function_stack.append(function_id)
        
        # Visit function body to analyze calls
        self.generic_visit(node)
        
        # Pop function from stack
        self.current_function_stack.pop()
        self.variable_type_stack.pop()
    
    def visit_Assign(self, node: ast.Assign):
        """Track simple variable assignments to class instances."""
        class_name = self._infer_class_name(node.value)
        if class_name:
            current_scope = self._current_var_types()
            for target in node.targets:
                if isinstance(target, ast.Name):
                    current_scope[target.id] = class_name
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        """Track annotated assignments that instantiate classes."""
        class_name = self._infer_class_name(node.value)
        if class_name and isinstance(node.target, ast.Name):
            self._current_var_types()[node.target.id] = class_name
        self.generic_visit(node)

    def _current_var_types(self) -> Dict[str, str]:
        return self.variable_type_stack[-1]

    def _infer_class_name(self, value: Optional[ast.AST]) -> Optional[str]:
        if isinstance(value, ast.Call):
            func = value.func
            if isinstance(func, ast.Name):
                return func.id
            if isinstance(func, ast.Attribute):
                return func.attr
        return None
    
    def _register_method(self, node: ast.FunctionDef, class_name: str):
        """Register a method symbol without visiting its body."""
        method_name = f"{class_name}.{node.name}"
        method_symbol_id = self._create_symbol_id(self.file_path, method_name)

        method_signature = self._extract_function_signature(node)
        method_docstring = ast.get_docstring(node)

        symbol_info = SymbolInfo(
            type="method",
            file=self.file_path,
            line=node.lineno,
            signature=method_signature,
            docstring=method_docstring
        )

        self.symbols[method_symbol_id] = symbol_info
        self.symbol_lookup[method_name] = method_symbol_id
        self.symbol_lookup[node.name] = method_symbol_id  # Also index by short method name
        self.functions.append(method_name)

    def _visit_registered_method(self, node: ast.FunctionDef, class_name: str):
        """Visit a previously registered method body for call analysis."""
        method_name = f"{class_name}.{node.name}"
        function_id = f"{self.file_path}::{method_name}"
        self.variable_type_stack.append({})
        self.current_function_stack.append(function_id)
        for child in node.body:
            self.visit(child)
        self.current_function_stack.pop()
        self.variable_type_stack.pop()
    
    def visit_Import(self, node: ast.Import):
        """Handle import statements."""
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Handle from...import statements."""
        if node.module:
            for alias in node.names:
                self.imports.append(f"{node.module}.{alias.name}")
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call):
        """Visit function call and record relationship using O(1) lookup."""
        if not self.current_function_stack:
            self.generic_visit(node)
            return
        
        try:
            # Get the function name being called
            called_function = None
            
            if isinstance(node.func, ast.Name):
                # Direct function call: function_name()
                called_function = self._qualify_name(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                # Method call: obj.method() or module.function()
                if not self._is_super_call(node.func):
                    qualifier = self._infer_attribute_qualifier(node.func.value)
                    if qualifier:
                        called_function = f"{qualifier}.{node.func.attr}"
                    else:
                        called_function = node.func.attr
            
            if called_function:
                caller_function = self.current_function_stack[-1]
                if not self._register_call_relationship(caller_function, called_function):
                    self.deferred_calls.append((caller_function, called_function))
        except Exception:
            # Silently handle parsing errors for complex call patterns
            pass
        
        # Continue visiting child nodes
        self.generic_visit(node)

    def _register_call_relationship(self, caller_function: str, called_function: str) -> bool:
        """Attempt to resolve a call relationship immediately."""
        try:
            if called_function in self.symbol_lookup:
                symbol_id = self.symbol_lookup[called_function]
                symbol_info = self.symbols[symbol_id]
                if symbol_info.type in ["function", "method"]:
                    if caller_function not in symbol_info.called_by:
                        symbol_info.called_by.append(caller_function)
                return True

            for name, symbol_id in self.symbol_lookup.items():
                if name.endswith(f".{called_function}"):
                    symbol_info = self.symbols[symbol_id]
                    if symbol_info.type in ["function", "method"]:
                        if caller_function not in symbol_info.called_by:
                            symbol_info.called_by.append(caller_function)
                    return True
        except Exception:
            return False

        return False

    def _qualify_name(self, name: str) -> str:
        """Map bare identifiers to fully qualified symbol names."""
        if name in self.symbol_lookup:
            return name
        if name and name[0].isupper():
            return f"{name}.__init__"
        return name

    def _infer_attribute_qualifier(self, value: ast.AST) -> Optional[str]:
        """Infer class name for attribute-based calls."""
        if isinstance(value, ast.Name):
            return self._current_var_types().get(value.id)
        if isinstance(value, ast.Call):
            return self._infer_class_name(value)
        if isinstance(value, ast.Attribute):
            if isinstance(value.value, ast.Name):
                inferred = self._current_var_types().get(value.value.id)
                if inferred:
                    return inferred
            return value.attr
        return None

    def resolve_deferred_calls(self) -> List[Tuple[str, str]]:
        """Resolve stored call relationships once all symbols are known."""
        if not self.deferred_calls:
            return []
        current = list(self.deferred_calls)
        unresolved: List[Tuple[str, str]] = []
        self.deferred_calls.clear()
        for caller, called in current:
            if not self._register_call_relationship(caller, called):
                unresolved.append((caller, called))
        self.deferred_calls = unresolved
        return unresolved

    @staticmethod
    def _is_super_call(attr_node: ast.Attribute) -> bool:
        """Detect super().method(...) patterns."""
        value = attr_node.value
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
            return value.func.id == "super"
        return False
    
    def _create_symbol_id(self, file_path: str, symbol_name: str) -> str:
        """Create a unique symbol ID."""
        return f"{file_path}::{symbol_name}"
    
    def _extract_function_signature(self, node: ast.FunctionDef) -> str:
        """Extract function signature from AST node."""
        # Build basic signature
        args = []
        
        # Regular arguments
        for arg in node.args.args:
            args.append(arg.arg)
        
        # Varargs (*args)
        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")
        
        # Keyword arguments (**kwargs)
        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")
        
        signature = f"def {node.name}({', '.join(args)}):"
        return signature
