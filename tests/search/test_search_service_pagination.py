"""Tests for search result pagination formatting."""
from pathlib import Path as _TestPath
from types import SimpleNamespace

from code_index_mcp.services.search_service import SearchService


def _create_service() -> SearchService:
    ctx = SimpleNamespace(
        request_context=SimpleNamespace(
            lifespan_context=SimpleNamespace(base_path="", settings=None)
        )
    )
    return SearchService(ctx)


def test_paginate_results_default_ordering():
    service = _create_service()

    raw_results = {
        "b/file.py": [(12, "second match"), (3, "first match")],
        "a/file.py": [(8, "another file")],
    }

    formatted, pagination = service._paginate_results(
        raw_results,
        start_index=0,
        max_results=None,
    )

    assert pagination == {
        "total_matches": 3,
        "returned": 3,
        "start_index": 0,
        "has_more": False,
        "end_index": 3,
    }

    assert formatted == [
        {"file": "a/file.py", "line": 8, "text": "another file"},
        {"file": "b/file.py", "line": 3, "text": "first match"},
        {"file": "b/file.py", "line": 12, "text": "second match"},
    ]


def test_paginate_results_with_start_and_limit():
    service = _create_service()

    raw_results = {
        "b/file.py": [(5, "line five"), (6, "line six")],
        "a/file.py": [(1, "line one"), (2, "line two")],
    }

    formatted, pagination = service._paginate_results(
        raw_results,
        start_index=1,
        max_results=2,
    )

    assert pagination == {
        "total_matches": 4,
        "returned": 2,
        "start_index": 1,
        "has_more": True,
        "max_results": 2,
        "end_index": 3,
    }

    assert formatted == [
        {"file": "a/file.py", "line": 2, "text": "line two"},
        {"file": "b/file.py", "line": 5, "text": "line five"},
    ]


def test_paginate_results_when_start_beyond_total():
    service = _create_service()

    formatted, pagination = service._paginate_results(
        {"only/file.py": [(1, "match")]},
        start_index=10,
        max_results=5,
    )

    assert formatted == []
    assert pagination == {
        "total_matches": 1,
        "returned": 0,
        "start_index": 1,
        "has_more": False,
        "max_results": 5,
        "end_index": 1,
    }
