"""Tests for C/C++ symbol discovery and call relationships."""

from code_index_mcp.indexing.strategies.c_cpp_strategy import CAndCppParsingStrategy


C_SAMPLE = """
#include "demo.h"
#include <stdio.h>

typedef struct {
    int id;
} User;

struct Session {
    User user;
};

static void helper(void) {}

void run(void) {
    helper();
}
"""


CPP_SAMPLE = """
#include "greeter.hpp"
#include <string>

namespace Demo {
struct Config {
    int enabled;
};

class Greeter {
public:
    Greeter() { init(); }
    void greet() { helper(); }
    static void helper() {}
private:
    void init() {}
};

void boot() {
    Greeter g;
    g.greet();
    Greeter::helper();
}
}
"""


def _symbol_by_name(symbols):
    result = {}
    for symbol_id, symbol_info in symbols.items():
        if "::" in symbol_id:
            result[symbol_id.split("::", 1)[1]] = (symbol_id, symbol_info)
    return result


def test_c_symbol_and_call_discovery():
    strategy = CAndCppParsingStrategy()
    symbols, file_info = strategy.parse_file("src/demo.c", C_SAMPLE)

    assert file_info.language == "c"
    assert "demo.h" in file_info.imports
    assert "stdio.h" in file_info.imports

    assert set(file_info.symbols["classes"]) == {"User", "Session"}
    assert set(file_info.symbols["functions"]) == {"helper", "run"}

    by_name = _symbol_by_name(symbols)
    run_id, _ = by_name["run"]
    _, helper_info = by_name["helper"]
    assert run_id in helper_info.called_by
    assert by_name["User"][1].type == "struct"
    assert by_name["Session"][1].type == "struct"


def test_h_files_are_parsed_as_c():
    strategy = CAndCppParsingStrategy()
    _, file_info = strategy.parse_file("include/demo.h", C_SAMPLE)

    assert file_info.language == "c"


def test_cpp_symbol_and_call_discovery():
    strategy = CAndCppParsingStrategy()
    symbols, file_info = strategy.parse_file("src/greeter.cpp", CPP_SAMPLE)

    assert file_info.language == "cpp"
    assert "greeter.hpp" in file_info.imports
    assert "string" in file_info.imports

    discovered_classes = set(file_info.symbols["classes"])
    assert "Demo.Config" in discovered_classes
    assert "Demo.Greeter" in discovered_classes

    discovered_functions = set(file_info.symbols["functions"])
    assert "Demo.Greeter.Greeter" in discovered_functions
    assert "Demo.Greeter.greet" in discovered_functions
    assert "Demo.Greeter.helper" in discovered_functions
    assert "Demo.Greeter.init" in discovered_functions
    assert "Demo.boot" in discovered_functions

    by_name = _symbol_by_name(symbols)
    boot_id, _ = by_name["Demo.boot"]

    assert "src/greeter.cpp:12" in by_name["Demo.Greeter.init"][1].called_by
    assert "src/greeter.cpp:13" in by_name["Demo.Greeter.helper"][1].called_by
    assert boot_id in by_name["Demo.Greeter.greet"][1].called_by
    assert boot_id in by_name["Demo.Greeter.helper"][1].called_by
