#!/usr/bin/env python3
"""Tests for Nim symbol discovery."""

from code_index_mcp.indexing.strategies.strategy_factory import StrategyFactory
from code_index_mcp.indexing.strategies.nim_strategy import NimParsingStrategy


NIM_SAMPLE = """
import std/[os, strutils]
from std/sequtils import mapIt
export gateway

type
  Person* = object
    name*: string
  Mode = enum
    fast, slow

const
  MaxSize* = 10

let runCli* = proc(args: seq[string]) =
  discard

proc greet*(p: Person): string =
  result = p.name

func add(a, b: int): int =
  a + b

macro makeThing*(body: untyped): untyped =
  body
"""


def _symbol_by_name(symbols):
    by_name = {}
    for symbol_id, symbol_info in symbols.items():
        if "::" in symbol_id:
            by_name[symbol_id.split("::", 1)[1]] = (symbol_id, symbol_info)
    return by_name


def test_nim_symbol_discovery() -> None:
    strategy = NimParsingStrategy()
    symbols, file_info = strategy.parse_file("src/sample.nim", NIM_SAMPLE)

    assert file_info.language == "nim"
    assert file_info.imports == ["std/[os, strutils]", "std/sequtils/mapIt"]
    assert file_info.exports == ["gateway"]

    discovered_functions = set(file_info.symbols.get("functions", []))
    assert "greet" in discovered_functions
    assert "add" in discovered_functions
    assert "makeThing" in discovered_functions

    discovered_classes = set(file_info.symbols.get("classes", []))
    assert "Person" in discovered_classes
    assert "Mode" in discovered_classes

    by_name = _symbol_by_name(symbols)
    assert by_name["Person"][1].type == "class"
    assert by_name["Mode"][1].type == "class"
    assert by_name["MaxSize"][1].type == "const"
    assert by_name["runCli"][1].type == "let"
    assert by_name["greet"][1].type == "proc"
    assert by_name["add"][1].type == "func"
    assert by_name["makeThing"][1].type == "macro"

    greet_id, greet_info = by_name["greet"]
    assert greet_id == "src/sample.nim::greet"
    assert greet_info.line > 0
    assert greet_info.end_line is not None
    assert greet_info.end_line >= greet_info.line
    assert "proc greet" in greet_info.signature


def test_nim_strategy_factory_reports_nim_as_specialized_only() -> None:
    factory = StrategyFactory()

    assert type(factory.get_strategy(".nim")).__name__ == "NimParsingStrategy"
    assert type(factory.get_strategy(".nims")).__name__ == "NimParsingStrategy"
    assert ".nim" in factory.get_specialized_extensions()
    assert ".nims" in factory.get_specialized_extensions()
    assert ".nim" not in factory.get_fallback_extensions()
    assert ".nims" not in factory.get_fallback_extensions()

    strategy_info = factory.get_strategy_info()
    assert ".nim" in strategy_info["nim"]
    assert ".nims" in strategy_info["nim"]
