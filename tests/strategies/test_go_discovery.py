#!/usr/bin/env python3
"""
Test for Go symbol discovery including all symbol types.
"""
import pytest
from textwrap import dedent

from code_index_mcp.indexing.strategies.go_strategy import GoParsingStrategy


@pytest.fixture
def test_code_with_all_symbols():
    """Fixture with variables, constants, functions, structs, interfaces and methods."""
    return '''
package main

import (
    "fmt"
    "strings"
)

import "errors"

// Application version constant
const VERSION = "1.0.0"

// Global variable for configuration
var config string = "default"

// Add returns the sum of two integers.
func Add(x int, y int) int {
    return x + y
}

// ComplexFunc demonstrates a complex function signature.
// It takes multiple parameters including variadic args.
func ComplexFunc(name string, values ...int) (int, error) {
    sum := 0
    for _, v := range values {
        sum += v
    }
    return sum, nil
}

// User represents a user in the system.
type User struct {
    ID       int
    Name     string
    Email    string
    IsActive bool
}

// NewUser creates a new User instance.
func NewUser(id int, name string, email string) *User {
    return &User{
        ID:    id,
        Name:  name,
        Email: email,
    }
}

// GetFullName returns the user's full name.
func (u *User) GetFullName() string {
    return u.Name
}

// Activate marks the user as active.
// This is a pointer receiver method.
func (u *User) Activate() {
    u.IsActive = true
}

// IsValid checks if the user has valid data.
// This is a value receiver method.
func (u User) IsValid() bool {
    return u.ID > 0 && u.Name != ""
}

// Repository interface defines data access methods.
type Repository interface {
    // Save stores an entity
    Save(entity interface{}) error
    
    // FindByID retrieves an entity by ID
    FindByID(id int) (interface{}, error)
    
    // Delete removes an entity
    Delete(id int) error
}

// Logger is a simple interface for logging.
type Logger interface {
    Log(message string)
}

// Calculate is a function type
type Calculate func(a, b int) int
'''


def test_go_symbol_discovery(test_code_with_all_symbols):
    """Test that all Go symbol types are correctly discovered."""
    strategy = GoParsingStrategy()
    symbols, file_info = strategy.parse_file("test.go", test_code_with_all_symbols)

    # Create a lookup dict by symbol name for easier access
    # This will throw KeyError if a symbol is missing
    symbol_lookup = {}
    for symbol_id, symbol_info in symbols.items():
        # Extract the symbol name from the ID (format: "file.go::SymbolName")
        if '::' in symbol_id:
            name = symbol_id.split('::')[1]
            symbol_lookup[name] = symbol_info
    
    # Verify package is extracted
    assert file_info.package == "main"
    
    # Verify imports are extracted (both multi-line block and single-line)
    assert "fmt" in file_info.imports
    assert "strings" in file_info.imports
    assert "errors" in file_info.imports
    
    # Verify all expected functions are in file_info
    discovered_functions = file_info.symbols.get('functions', [])
    expected_functions = ['Add', 'ComplexFunc', 'NewUser', 'GetFullName', 'Activate', 'IsValid']
    for func in expected_functions:
        assert func in discovered_functions, f"Function '{func}' not in file_info.symbols['functions']"
    
    # Verify structs and interfaces are discovered (in 'classes')
    discovered_classes = file_info.symbols.get('classes', [])
    assert 'User' in discovered_classes
    assert 'Repository' in discovered_classes
    assert 'Logger' in discovered_classes
    
    # Verify all symbols are in lookup
    assert 'Add' in symbol_lookup
    assert 'ComplexFunc' in symbol_lookup
    assert 'User' in symbol_lookup
    assert 'NewUser' in symbol_lookup
    assert 'GetFullName' in symbol_lookup
    assert 'Activate' in symbol_lookup
    assert 'IsValid' in symbol_lookup
    assert 'Repository' in symbol_lookup
    assert 'Logger' in symbol_lookup
    
    # Check symbol types
    assert symbol_lookup['Add'].type == 'function'
    assert symbol_lookup['ComplexFunc'].type == 'function'
    assert symbol_lookup['NewUser'].type == 'function'
    assert symbol_lookup['GetFullName'].type == 'method'
    assert symbol_lookup['Activate'].type == 'method'
    assert symbol_lookup['IsValid'].type == 'method'
    assert symbol_lookup['User'].type == 'struct'
    assert symbol_lookup['Repository'].type == 'interface'
    assert symbol_lookup['Logger'].type == 'interface'
    
    # Check signatures are captured
    assert symbol_lookup['Add'].signature is not None
    assert 'Add' in symbol_lookup['Add'].signature
    assert 'int' in symbol_lookup['Add'].signature
    
    assert symbol_lookup['ComplexFunc'].signature is not None
    assert 'ComplexFunc' in symbol_lookup['ComplexFunc'].signature
    assert '...int' in symbol_lookup['ComplexFunc'].signature or 'values' in symbol_lookup['ComplexFunc'].signature
    
    assert symbol_lookup['GetFullName'].signature is not None
    assert 'GetFullName' in symbol_lookup['GetFullName'].signature
    assert 'User' in symbol_lookup['GetFullName'].signature or '*User' in symbol_lookup['GetFullName'].signature
    
    # Check line numbers are correct (approximate, since we know the structure)
    assert symbol_lookup['Add'].line > 10
    assert symbol_lookup['User'].line > symbol_lookup['Add'].line
    assert symbol_lookup['GetFullName'].line > symbol_lookup['User'].line
    
    # Check that methods are associated with correct receivers
    # Method signatures should contain receiver information
    assert 'User' in symbol_lookup['GetFullName'].signature
    assert 'User' in symbol_lookup['Activate'].signature
    assert 'User' in symbol_lookup['IsValid'].signature
    
    # Note: Go strategy currently does not extract comments/docstrings
    # The following assertions would pass if docstring extraction is implemented:
    # assert symbol_lookup['Add'].docstring == "Add returns the sum of two integers."
    # assert symbol_lookup['User'].docstring == "User represents a user in the system."
    # assert symbol_lookup['Repository'].docstring == "Repository interface defines data access methods."
