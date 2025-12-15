#!/usr/bin/env python3
"""Test for Kotlin symbol discovery and basic call relationships."""

import pytest

from code_index_mcp.indexing.strategies.kotlin_strategy import KotlinParsingStrategy


@pytest.fixture
def kotlin_code_sample() -> str:
    return """
package com.example.app

import kotlin.collections.List
import com.foo.Bar as Baz
import com.foo.util.*

interface Repo {
    fun save()
}

class Greeter(private val name: String) : Repo {
    override fun save() {
        helper()
    }

    fun greet(): String {
        helper()
        staticCall()
        return "Hi, $name"
    }

    private fun helper() {}

    companion object {
        fun staticCall() {}
    }
}

object Singleton {
    fun run() {
        Greeter("x").greet()
    }
}

fun topLevel(x: Int): Int {
    return x + 1
}
"""


def test_kotlin_symbol_discovery(kotlin_code_sample: str) -> None:
    strategy = KotlinParsingStrategy()
    symbols, file_info = strategy.parse_file("test.kt", kotlin_code_sample)

    assert file_info.package == "com.example.app"

    assert "kotlin.collections.List" in file_info.imports
    assert "com.foo.Bar" in file_info.imports
    assert "com.foo.util.*" in file_info.imports

    discovered_functions = set(file_info.symbols.get("functions", []))
    assert "topLevel" in discovered_functions
    assert "Greeter.greet" in discovered_functions
    assert "Greeter.helper" in discovered_functions
    assert "Greeter.staticCall" in discovered_functions
    assert "Singleton.run" in discovered_functions

    discovered_classes = set(file_info.symbols.get("classes", []))
    assert "Greeter" in discovered_classes
    assert "Singleton" in discovered_classes
    assert "Repo" in discovered_classes

    # Verify symbol lookup by name.
    symbol_by_name = {}
    for symbol_id, symbol_info in symbols.items():
        if "::" in symbol_id:
            symbol_by_name[symbol_id.split("::", 1)[1]] = (symbol_id, symbol_info)

    assert "topLevel" in symbol_by_name
    assert "Greeter.greet" in symbol_by_name
    assert "Greeter.helper" in symbol_by_name

    assert symbol_by_name["topLevel"][1].type == "function"
    assert symbol_by_name["Greeter.greet"][1].type == "method"

    # Basic call discovery: helper() is discovered as a pending call because helper is declared later.
    greet_id, _ = symbol_by_name["Greeter.greet"]
    save_id, _ = symbol_by_name.get("Greeter.save", (None, None))
    pending = set(getattr(file_info, "pending_calls", []))
    assert (greet_id, "helper") in pending
    if save_id:
        assert (save_id, "helper") in pending
