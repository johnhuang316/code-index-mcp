"""Service-level tests for regex mode handling in search service."""
from pathlib import Path as _TestPath
from types import SimpleNamespace
import sys

import pytest

ROOT = _TestPath(__file__).resolve().parents[2]
SRC_PATH = ROOT / 'src'
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from code_index_mcp.services.search_service import SearchService


class _FakeStrategy:
    def __init__(self, name: str):
        self.name = name
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        return {
            'src/example.py': [(7, 'matched line')],
        }


class _FakeSettings:
    def __init__(self, strategy):
        self.strategy = strategy

    def get_preferred_search_tool(self):
        return self.strategy

    def get_file_watcher_config(self):
        return {}

    def get_search_tools_config(self):
        return {
            'available_tools': [self.strategy.name],
            'preferred_tool': self.strategy.name,
        }


def _create_service(tmp_path, strategy: _FakeStrategy) -> SearchService:
    ctx = SimpleNamespace(
        request_context=SimpleNamespace(
            lifespan_context=SimpleNamespace(
                base_path=str(tmp_path),
                settings=_FakeSettings(strategy),
            )
        )
    )
    return SearchService(ctx)


def test_search_code_defaults_regex_none_to_false_for_basic_strategy(tmp_path):
    strategy = _FakeStrategy('basic')
    service = _create_service(tmp_path, strategy)

    response = service.search_code(pattern='hello.*world', regex=None)

    assert strategy.calls[0]['regex'] is False
    assert response['results'] == [
        {'file': 'src/example.py', 'line': 7, 'text': 'matched line'},
    ]


def test_search_code_rejects_regex_mode_for_basic_strategy(tmp_path):
    strategy = _FakeStrategy('basic')
    service = _create_service(tmp_path, strategy)

    with pytest.raises(ValueError, match='external search tool'):
        service.search_code(pattern='hello.*world', regex=True)


def test_search_code_allows_regex_mode_for_external_strategy(tmp_path):
    strategy = _FakeStrategy('ripgrep')
    service = _create_service(tmp_path, strategy)

    service.search_code(pattern='hello.*world', regex=True)

    assert strategy.calls[0]['regex'] is True


def test_search_code_rejects_malformed_explicit_regex(tmp_path):
    strategy = _FakeStrategy('ripgrep')
    service = _create_service(tmp_path, strategy)

    with pytest.raises(ValueError, match='Invalid regex pattern'):
        service.search_code(pattern='hello(', regex=True)


def test_get_search_capabilities_reports_no_regex_for_basic_only_setup(tmp_path):
    strategy = _FakeStrategy('basic')
    service = _create_service(tmp_path, strategy)

    capabilities = service.get_search_capabilities()

    assert capabilities['available_tools'] == ['basic']
    assert capabilities['preferred_tool'] == 'basic'
    assert capabilities['supports_regex'] is False
