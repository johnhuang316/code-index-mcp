#!/usr/bin/env python3
"""Test for C# symbol discovery and call relationships."""

from code_index_mcp.indexing.strategies.csharp_strategy import CSharpParsingStrategy


C_SHARP_SAMPLE = """
namespace Demo.App
{
    using System;
    using DG.Tweening;

    class Service
    {
        public void Run() {}
    }

    static class StaticService
    {
        public static void Run() {}
    }

    class Greeter
    {
        private readonly string _name;

        public Greeter(string name)
        {
            _name = name;
            Helper();
        }

        public void Greet()
        {
            Helper();
            var svc = new Service();
            svc.Run();
            StaticService.Run();
        }

        void Helper() {}
    }
}
"""

C_SHARP_COMPLEX = """
namespace Complex.App;

using System;
using System.Collections.Generic;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using Alias = System.Collections.Generic.Dictionary<string, List<int>>;

[AttributeUsage(AttributeTargets.Method)]
sealed class MarkerAttribute : Attribute {}

partial class Outer<T> where T : class
{
    public partial class Inner<U> where U : struct
    {
        private Alias _map = new();

        public async IAsyncEnumerable<T> StreamAsync(
            Func<U, T> factory,
            [EnumeratorCancellation] System.Threading.CancellationToken ct = default)
        {
            yield return await Task.Run(() => factory(default), ct);
            yield return await Task.Run(() => factory(default), ct);
        }

        public T Invoke(Func<T> f) => f();
    }

    public partial class Inner<U>
    {
        [Marker]
        public T Make<U2>(U2 value) where U2 : notnull
        {
            return (T)(object)value.ToString();
        }
    }
}

partial class Outer<T>
{
    public static Outer<T>.Inner<int> Build(Func<int, T> factory)
    {
        var inner = new Inner<int>();
        var _ = inner.Invoke(() => factory(0));
        return inner;
    }
}
"""


def _symbol_by_name(symbols):
    result = {}
    for symbol_id, symbol_info in symbols.items():
        if "::" in symbol_id:
            result[symbol_id.split("::", 1)[1]] = (symbol_id, symbol_info)
    return result


def test_csharp_symbol_and_calls_discovery():
    strategy = CSharpParsingStrategy()
    symbols, file_info = strategy.parse_file("Demo/App/Greeter.cs", C_SHARP_SAMPLE)

    assert file_info.package == "Demo.App"
    assert "System" in file_info.imports
    assert "DG.Tweening" in file_info.imports

    discovered_functions = set(file_info.symbols.get("functions", []))
    assert "Demo.App.Greeter.#ctor" in discovered_functions
    assert "Demo.App.Greeter.Greet" in discovered_functions
    assert "Demo.App.Greeter.Helper" in discovered_functions
    assert "Demo.App.Service.Run" in discovered_functions
    assert "Demo.App.StaticService.Run" in discovered_functions

    discovered_classes = set(file_info.symbols.get("classes", []))
    assert "Demo.App.Greeter" in discovered_classes
    assert "Demo.App.Service" in discovered_classes
    assert "Demo.App.StaticService" in discovered_classes

    by_name = _symbol_by_name(symbols)
    helper_id, helper_info = by_name["Demo.App.Greeter.Helper"]
    greet_id, _ = by_name["Demo.App.Greeter.Greet"]
    ctor_id, _ = by_name["Demo.App.Greeter.#ctor"]
    static_run_id, static_run_info = by_name["Demo.App.StaticService.Run"]

    # Helper is called from both constructor and greet
    assert greet_id in helper_info.called_by
    assert ctor_id in helper_info.called_by

    # StaticService.Run is resolved as a call target
    assert static_run_info.called_by == [greet_id]


def test_csharp_complex_sample():
    strategy = CSharpParsingStrategy()
    symbols, file_info = strategy.parse_file("Complex/App/Outer.cs", C_SHARP_COMPLEX)

    assert file_info.package == "Complex.App"
    assert "System" in file_info.imports
    assert "System.Collections.Generic" in file_info.imports
    assert "System.Runtime.CompilerServices" in file_info.imports
    assert "System.Threading.Tasks" in file_info.imports

    discovered_classes = set(file_info.symbols.get("classes", []))
    assert "Complex.App.Outer" in discovered_classes
    assert "Complex.App.Outer.Inner" in discovered_classes

    discovered_functions = set(file_info.symbols.get("functions", []))
    assert "Complex.App.Outer.Inner.StreamAsync" in discovered_functions
    assert "Complex.App.Outer.Inner.Invoke" in discovered_functions
    assert "Complex.App.Outer.Inner.Make" in discovered_functions
    assert "Complex.App.Outer.Build" in discovered_functions

    by_name = _symbol_by_name(symbols)
    invoke_id, _ = by_name["Complex.App.Outer.Inner.Invoke"]
    build_id, _ = by_name["Complex.App.Outer.Build"]

    # inner.Invoke should be resolved as a call target of Build
    invoke_info = symbols.get(by_name["Complex.App.Outer.Inner.Invoke"][0])
    assert build_id in invoke_info.called_by
