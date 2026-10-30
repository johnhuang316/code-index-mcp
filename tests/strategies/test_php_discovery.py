#!/usr/bin/env python3
"""Tests for PHP symbol discovery and call relationships."""

from code_index_mcp.indexing.strategies.php_strategy import PhpParsingStrategy
from code_index_mcp.indexing.strategies.strategy_factory import StrategyFactory


PHP_SAMPLE = """<?php
namespace App\\Service;

use App\\Contracts\\Notifier;
use App\\Support\\Clock;

interface NotifierInterface {
    public function send(string $msg): bool;
}

trait Loggable {
    public function log(string $message): void {
        helper_fn($message);
    }
}

enum Status: string {
    case Active = 'active';
    public function label(): string { return 'active'; }
}

class Mailer implements NotifierInterface {
    use Loggable;

    /** Sends a message. */
    public function send(string $msg): bool {
        helper_fn($msg);
        $this->log($msg);
        Clock::now();
        return true;
    }

    public static function build(): self {
        return new self();
    }
}

function helper_fn(string $msg): void {}
"""


def _symbol_by_name(symbols):
    return {sid.split("::", 1)[1]: (sid, info) for sid, info in symbols.items()}


def test_php_symbol_discovery() -> None:
    strategy = PhpParsingStrategy()
    symbols, file_info = strategy.parse_file("app/Mailer.php", PHP_SAMPLE)

    assert file_info.language == "php"
    assert file_info.imports == ["App\\Contracts\\Notifier", "App\\Support\\Clock"]

    classes = set(file_info.symbols["classes"])
    assert {"NotifierInterface", "Loggable", "Status", "Mailer"} <= classes

    functions = set(file_info.symbols["functions"])
    assert "helper_fn" in functions
    assert "Mailer.send" in functions
    assert "Mailer.build" in functions
    assert "Loggable.log" in functions

    by_name = _symbol_by_name(symbols)
    send_id, send_info = by_name["Mailer.send"]

    assert send_info.type == "method"
    assert send_info.line > 0
    assert send_info.end_line >= send_info.line
    assert send_info.signature == "public function send(string $msg): bool"
    assert send_info.docstring == "Sends a message."

    assert by_name["Mailer"][1].type == "class"
    assert by_name["helper_fn"][1].type == "function"
    assert send_id == "app/Mailer.php::Mailer.send"


def test_php_method_names_are_owner_qualified_for_short_lookup() -> None:
    strategy = PhpParsingStrategy()
    symbols, file_info = strategy.parse_file("app/Mailer.php", PHP_SAMPLE)

    # get_symbol_body resolves "send" through the ".send" suffix of "Mailer.send",
    # which is why methods are stored owner-qualified rather than bare.
    functions = file_info.symbols["functions"]
    assert "Mailer.send" in functions
    assert "send" not in functions

    by_name = _symbol_by_name(symbols)
    assert "Mailer.send" in by_name
    assert "send" not in by_name


def test_php_call_relationships() -> None:
    strategy = PhpParsingStrategy()
    symbols, _ = strategy.parse_file("app/Mailer.php", PHP_SAMPLE)

    by_name = _symbol_by_name(symbols)
    send_id, _ = by_name["Mailer.send"]

    _, helper_info = by_name["helper_fn"]
    _, log_info = by_name["Loggable.log"]

    assert send_id in helper_info.called_by
    assert send_id in log_info.called_by

    # new self() must not invent a constructor symbol the class never declared.
    assert "Mailer.__construct" not in by_name


def test_php_constructor_call_is_linked() -> None:
    sample = """<?php
class Worker {
    public function __construct() {}
    public static function make(): self {
        return new self();
    }
}
"""
    strategy = PhpParsingStrategy()
    symbols, _ = strategy.parse_file("Worker.php", sample)

    by_name = _symbol_by_name(symbols)
    make_id, _ = by_name["Worker.make"]
    _, construct_info = by_name["Worker.__construct"]

    assert make_id in construct_info.called_by


def test_php_short_name_ambiguity_does_not_create_false_called_by() -> None:
    sample = """<?php
class User {
    public function run(): void {}
}

class Admin {
    public function run(): void {}
}

function caller(): void {
    run();
}
"""
    strategy = PhpParsingStrategy()
    symbols, _ = strategy.parse_file("Ambiguous.php", sample)

    by_name = _symbol_by_name(symbols)
    caller_id, _ = by_name["caller"]
    _, user_run = by_name["User.run"]
    _, admin_run = by_name["Admin.run"]

    assert caller_id not in user_run.called_by
    assert caller_id not in admin_run.called_by


def test_php_braced_namespaces_are_both_extracted() -> None:
    sample = """<?php
namespace First {
    class Alpha {
        public function act(): void {}
    }
}

namespace Second {
    function call(): void {}
}
"""
    strategy = PhpParsingStrategy()
    symbols, file_info = strategy.parse_file("Braced.php", sample)

    classes = set(file_info.symbols["classes"])
    functions = set(file_info.symbols["functions"])

    assert "Alpha" in classes
    assert "Alpha.act" in functions
    assert "call" in functions


def test_php_inherited_member_call_resolves_to_parent_declaration() -> None:
    sample = """<?php
class Base {
    public function run(): void {}
}

class Child extends Base {
    public function go(): void {
        $this->run();
        parent::run();
    }
}
"""
    strategy = PhpParsingStrategy()
    symbols, file_info = strategy.parse_file("Inherit.php", sample)

    by_name = _symbol_by_name(symbols)
    go_id, _ = by_name["Child.go"]
    _, base_run = by_name["Base.run"]

    # Child declares no run(), so $this->run() resolves to the inherited
    # Base.run rather than inventing a Child.run symbol.
    assert "Child.run" not in by_name
    assert go_id in base_run.called_by
    assert getattr(file_info, "pending_calls", []) == []


def test_php_variable_function_call_is_skipped() -> None:
    sample = """<?php
function target(): void {}

function caller(): void {
    $fn = 'target';
    $fn();
}
"""
    strategy = PhpParsingStrategy()
    symbols, file_info = strategy.parse_file("Variable.php", sample)

    by_name = _symbol_by_name(symbols)
    caller_id, _ = by_name["caller"]
    _, target_info = by_name["target"]

    assert caller_id not in target_info.called_by
    assert getattr(file_info, "pending_calls", []) == []


def test_php_strategy_factory_reports_php_as_specialized_only() -> None:
    factory = StrategyFactory()

    assert type(factory.get_strategy(".php")).__name__ == "PhpParsingStrategy"
    assert ".php" in factory.get_specialized_extensions()
    assert ".php" not in factory.get_fallback_extensions()

    strategy_info = factory.get_strategy_info()
    assert ".php" in strategy_info["php"]
    assert ".php" not in strategy_info.get("fallback_php", [])


def test_php_factory_parse_no_longer_yields_zero_symbols() -> None:
    factory = StrategyFactory()
    strategy = factory.get_strategy(".php")
    symbols, file_info = strategy.parse_file("app/Mailer.php", PHP_SAMPLE)

    assert len(symbols) > 0
    assert file_info.symbols["classes"]
    assert file_info.symbols["functions"]


def test_php_namespace_surfaces_as_package() -> None:
    strategy = PhpParsingStrategy()
    _, file_info = strategy.parse_file("app/Mailer.php", PHP_SAMPLE)

    assert file_info.package == "App\\Service"


def test_php_phtml_template_declarations_are_extracted() -> None:
    template = """<div class="wrapper">
<?php
function template_helper($value) { return $value; }
class Block { public function render() {} }
?>
</div>"""

    strategy = PhpParsingStrategy()
    symbols, file_info = strategy.parse_file("view/template.phtml", template)

    assert "template_helper" in file_info.symbols["functions"]
    assert "Block.render" in file_info.symbols["functions"]
    assert "Block" in file_info.symbols["classes"]
    assert len(symbols) == 3


def test_php_and_phtml_extensions_are_registered() -> None:
    factory = StrategyFactory()
    strategy = PhpParsingStrategy()

    assert ".php" in strategy.get_supported_extensions()
    assert ".phtml" in strategy.get_supported_extensions()

    for extension in (".php", ".phtml"):
        assert type(factory.get_strategy(extension)).__name__ == "PhpParsingStrategy"
