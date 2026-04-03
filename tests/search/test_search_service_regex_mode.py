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


def test_search_service_loads_exclude_patterns(tmp_path):
    """SearchService should load additional_exclude_patterns from config."""
    strategy = _FakeStrategy('ripgrep')

    class _SettingsWithConfig(_FakeSettings):
        def load_config(self):
            return {"additional_exclude_patterns": ["dist/", "*.min.js"]}

    ctx = SimpleNamespace(
        request_context=SimpleNamespace(
            lifespan_context=SimpleNamespace(
                base_path=str(tmp_path),
                settings=_SettingsWithConfig(strategy),
            )
        )
    )
    service = SearchService(ctx)

    assert service.additional_exclude_patterns == ["dist/", "*.min.js"]


def test_search_service_loads_exclude_patterns_backward_compat(tmp_path):
    """SearchService should fall back to file_watcher.additional_exclude_patterns."""
    strategy = _FakeStrategy('ripgrep')

    class _SettingsOldConfig(_FakeSettings):
        def load_config(self):
            return {"file_watcher": {"additional_exclude_patterns": ["build/"]}}

    ctx = SimpleNamespace(
        request_context=SimpleNamespace(
            lifespan_context=SimpleNamespace(
                base_path=str(tmp_path),
                settings=_SettingsOldConfig(strategy),
            )
        )
    )
    service = SearchService(ctx)

    assert service.additional_exclude_patterns == ["build/"]


def test_search_service_loads_exclude_patterns_returns_empty_on_missing(tmp_path):
    """SearchService should return empty list when settings lacks load_config."""
    strategy = _FakeStrategy('ripgrep')
    service = _create_service(tmp_path, strategy)  # _FakeSettings has no load_config

    assert service.additional_exclude_patterns == []


def test_search_code_passes_exclude_patterns_to_strategy(tmp_path):
    """search_code should pass additional_exclude_patterns to strategy.search()."""
    strategy = _FakeStrategy('ripgrep')

    class _SettingsWithExcludes(_FakeSettings):
        def load_config(self):
            return {"additional_exclude_patterns": ["node_modules/"]}

    ctx = SimpleNamespace(
        request_context=SimpleNamespace(
            lifespan_context=SimpleNamespace(
                base_path=str(tmp_path),
                settings=_SettingsWithExcludes(strategy),
            )
        )
    )
    service = SearchService(ctx)
    service.search_code(pattern='hello', regex=False)

    assert strategy.calls[0]['exclude_patterns'] == ["node_modules/"]
