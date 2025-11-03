#!/usr/bin/env python3
"""
Test for Python symbol discovery including all symbol types.
"""
import pytest
from textwrap import dedent

from code_index_mcp.indexing.strategies.python_strategy import PythonParsingStrategy


@pytest.fixture
def test_code_with_all_symbols():
    """Fixture with variables, constants, functions, classes and methods."""
    return '''
CONSTANT = 42
variable = 'hello'

def sync_function():
    """A regular synchronous function."""
    return "sync result"

async def async_function():
    """An asynchronous function."""
    return "async result"

def top_level_function(x, y):
    """Function without type hints."""
    return x + y

def function_with_types(name: str, age: int, active: bool = True) -> dict:
    """
    Function with type hints and default values.
    
    Args:
        name: The person's name
        age: The person's age
        active: Whether the person is active

    Returns:
        A dictionary with person info
    """
    return {"name": name, "age": age, "active": active}

def complex_function(items: list[str], *args: int, callback=None, **kwargs: str) -> tuple[int, str]:
    """Function with complex signature including *args and **kwargs."""
    return len(items), str(args)

class TestClass:
    """A test class with various methods."""
    CLASS_VAR = 123
    
    def __init__(self, value: int):
        """Initialize with a value."""
        self.value = value
    
    def sync_method(self):
        """A regular synchronous method."""
        return "sync method result"
    
    async def async_method(self):
        """An asynchronous method."""
        return "async method result"
    
    def method(self):
        return self.value
    
    def typed_method(self, x: float, y: float) -> float:
        """Method with type hints.
        
        Returns the sum of x and y.
        """
        return x + y
'''


def test_python_symbol_discovery(test_code_with_all_symbols):
    """Test that all Python symbol types are correctly discovered."""
    strategy = PythonParsingStrategy()
    symbols, file_info = strategy.parse_file("test.py", test_code_with_all_symbols)

    # Create a lookup dict by symbol name for easier access
    # This will throw KeyError if a symbol is missing
    symbol_lookup = {}
    for symbol_id, symbol_info in symbols.items():
        # Extract the symbol name from the ID (format: "file.py::SymbolName")
        if '::' in symbol_id:
            name = symbol_id.split('::')[1]
            symbol_lookup[name] = symbol_info
    
    # Verify all expected functions are in file_info
    discovered_functions = file_info.symbols.get('functions', [])
    expected_functions = ['sync_function', 'async_function', 'top_level_function', 
                          'function_with_types', 'complex_function']
    for func in expected_functions:
        assert func in discovered_functions, f"Function '{func}' not in file_info.symbols['functions']"
    
    # Verify all expected methods are discovered
    expected_methods = ['TestClass.__init__', 'TestClass.sync_method', 
                        'TestClass.async_method', 'TestClass.method', 'TestClass.typed_method']
    for method in expected_methods:
        assert method in symbol_lookup, f"Method '{method}' not found in symbols"
    
    # Verify class is discovered
    assert 'TestClass' in file_info.symbols.get('classes', [])
    assert 'TestClass' in symbol_lookup
    
    # Check symbol types
    assert symbol_lookup['sync_function'].type == 'function'
    assert symbol_lookup['async_function'].type == 'function'
    assert symbol_lookup['top_level_function'].type == 'function'
    assert symbol_lookup['function_with_types'].type == 'function'
    assert symbol_lookup['complex_function'].type == 'function'
    assert symbol_lookup['TestClass'].type == 'class'
    assert symbol_lookup['TestClass.__init__'].type == 'method'
    assert symbol_lookup['TestClass.sync_method'].type == 'method'
    assert symbol_lookup['TestClass.async_method'].type == 'method'
    assert symbol_lookup['TestClass.method'].type == 'method'
    assert symbol_lookup['TestClass.typed_method'].type == 'method'
    
    # Check docstrings explicitly
    assert symbol_lookup['sync_function'].docstring == "A regular synchronous function."
    assert symbol_lookup['async_function'].docstring == "An asynchronous function."
    assert symbol_lookup['top_level_function'].docstring == "Function without type hints."
    
    expected_docstring = dedent("""
        Function with type hints and default values.
        
        Args:
            name: The person's name
            age: The person's age
            active: Whether the person is active

        Returns:
            A dictionary with person info
    """).strip()
    assert symbol_lookup['function_with_types'].docstring == expected_docstring
    
    assert symbol_lookup['complex_function'].docstring == "Function with complex signature including *args and **kwargs."
    assert symbol_lookup['TestClass.__init__'].docstring == "Initialize with a value."
    assert symbol_lookup['TestClass.sync_method'].docstring == "A regular synchronous method."
    assert symbol_lookup['TestClass.async_method'].docstring == "An asynchronous method."
    assert symbol_lookup['TestClass.method'].docstring is None
    
    expected_typed_method_docstring = dedent("""
        Method with type hints.
        
        Returns the sum of x and y.
    """).strip()
    assert symbol_lookup['TestClass.typed_method'].docstring == expected_typed_method_docstring
    assert symbol_lookup['TestClass'].docstring == "A test class with various methods."
    
    # Check signatures explicitly
    assert symbol_lookup['sync_function'].signature == "def sync_function():"
    assert symbol_lookup['async_function'].signature == "def async_function():"
    assert symbol_lookup['top_level_function'].signature == "def top_level_function(x, y):"
    assert symbol_lookup['function_with_types'].signature == "def function_with_types(name, age, active):"
    assert symbol_lookup['complex_function'].signature == "def complex_function(items, *args, **kwargs):"
    assert symbol_lookup['TestClass.__init__'].signature == "def __init__(self, value):"
    assert symbol_lookup['TestClass.sync_method'].signature == "def sync_method(self):"
    assert symbol_lookup['TestClass.async_method'].signature == "def async_method(self):"
    assert symbol_lookup['TestClass.method'].signature == "def method(self):"
    assert symbol_lookup['TestClass.typed_method'].signature == "def typed_method(self, x, y):"
