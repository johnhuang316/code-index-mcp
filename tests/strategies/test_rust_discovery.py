#!/usr/bin/env python3
"""Tests for Rust symbol discovery and call relationships."""

from code_index_mcp.indexing.strategies.strategy_factory import StrategyFactory
from code_index_mcp.indexing.strategies.rust_strategy import RustParsingStrategy


RUST_SAMPLE = """
use std::fmt::Display;
pub use std::collections::HashMap;

pub fn helper() {
    println!("helper");
}

pub fn run() {
    helper();
    Worker::new();
}

pub struct Worker {
    value: i32,
}

impl Worker {
    pub fn new() -> Self {
        Worker { value: 0 }
    }

    pub fn do_work(&self) {
        helper();
    }
}

pub enum State {
    Ready,
    Running,
}

pub trait Runnable {
    fn execute(&self);
}
"""


def _symbol_by_name(symbols):
    by_name = {}
    for symbol_id, symbol_info in symbols.items():
        if "::" in symbol_id:
            by_name[symbol_id.split("::", 1)[1]] = (symbol_id, symbol_info)
    return by_name


def test_rust_symbol_discovery() -> None:
    strategy = RustParsingStrategy()
    symbols, file_info = strategy.parse_file("src/lib.rs", RUST_SAMPLE)

    assert "std::fmt::Display" in file_info.imports
    assert "std::collections::HashMap" in file_info.imports

    discovered_functions = set(file_info.symbols.get("functions", []))
    assert "helper" in discovered_functions
    assert "run" in discovered_functions
    assert "Worker.new" in discovered_functions
    assert "Worker.do_work" in discovered_functions

    discovered_classes = set(file_info.symbols.get("classes", []))
    assert "Worker" in discovered_classes
    assert "State" in discovered_classes
    assert "Runnable" in discovered_classes

    by_name = _symbol_by_name(symbols)

    helper_id, helper_info = by_name["helper"]
    run_id, run_info = by_name["run"]
    worker_new_id, worker_new_info = by_name["Worker.new"]
    worker_do_work_id, worker_do_work_info = by_name["Worker.do_work"]

    assert run_info.type == "function"
    assert worker_new_info.type == "method"
    assert worker_do_work_info.type == "method"

    # Called-by links should include direct call_expression targets.
    assert run_id in helper_info.called_by
    assert worker_do_work_id in helper_info.called_by
    assert run_id in worker_new_info.called_by

    # Basic line and signature coverage.
    assert run_info.line > 0
    assert run_info.end_line is not None
    assert run_info.end_line >= run_info.line
    assert run_info.signature is not None
    assert "fn run" in run_info.signature

    assert worker_do_work_info.line > worker_new_info.line
    assert worker_do_work_info.end_line is not None
    assert worker_do_work_info.end_line >= worker_do_work_info.line

    # Symbol ids remain stable and include method-qualified names.
    assert helper_id == "src/lib.rs::helper"
    assert worker_new_id == "src/lib.rs::Worker.new"


RUST_AMBIGUOUS_NEW_SAMPLE = """
pub fn run() {
    new();
}

pub struct User;
pub struct Admin;

impl User {
    pub fn new() -> Self {
        User
    }
}

impl Admin {
    pub fn new() -> Self {
        Admin
    }
}
"""


def test_rust_short_name_ambiguity_does_not_create_false_called_by() -> None:
    strategy = RustParsingStrategy()
    symbols, _ = strategy.parse_file("src/lib.rs", RUST_AMBIGUOUS_NEW_SAMPLE)

    by_name = _symbol_by_name(symbols)
    run_id, _ = by_name["run"]
    user_new_id, user_new_info = by_name["User.new"]
    admin_new_id, admin_new_info = by_name["Admin.new"]

    assert user_new_id != admin_new_id
    assert run_id not in user_new_info.called_by
    assert run_id not in admin_new_info.called_by


RUST_MODULE_SAMPLE = """
fn helper() {}

mod foo {
    pub fn helper() {}

    pub fn run() {
        helper();
    }
}

pub fn run_root() {
    foo::helper();
}
"""


def test_rust_module_namespaces_are_preserved() -> None:
    strategy = RustParsingStrategy()
    symbols, file_info = strategy.parse_file("src/lib.rs", RUST_MODULE_SAMPLE)

    discovered_functions = set(file_info.symbols.get("functions", []))
    assert "helper" in discovered_functions
    assert "foo::helper" in discovered_functions
    assert "foo::run" in discovered_functions
    assert "run_root" in discovered_functions

    by_name = _symbol_by_name(symbols)
    helper_id, helper_info = by_name["helper"]
    foo_helper_id, foo_helper_info = by_name["foo::helper"]
    foo_run_id, _ = by_name["foo::run"]
    run_root_id, _ = by_name["run_root"]

    assert helper_id != foo_helper_id
    assert foo_run_id in foo_helper_info.called_by
    assert run_root_id in foo_helper_info.called_by
    assert run_root_id not in helper_info.called_by


def test_rust_strategy_factory_reports_rs_as_specialized_only() -> None:
    factory = StrategyFactory()

    assert type(factory.get_strategy(".rs")).__name__ == "RustParsingStrategy"
    assert ".rs" in factory.get_specialized_extensions()
    assert ".rs" not in factory.get_fallback_extensions()

    strategy_info = factory.get_strategy_info()
    assert ".rs" in strategy_info["rust"]
    assert ".rs" not in strategy_info.get("fallback_rust", [])
