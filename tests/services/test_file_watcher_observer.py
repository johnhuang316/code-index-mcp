"""Tests for file watcher observer selection.

Verify that the observer factory correctly selects the appropriate
observer class based on platform and configuration.
"""

import platform
import pytest
from unittest.mock import patch

from code_index_mcp.services.file_watcher_service import _get_observer_class


def test_auto_uses_platform_default():
    """Verify auto mode uses platform default observer."""
    # Auto should use the default Observer class (platform default)
    # On macOS this is FSEventsObserver, on Linux InotifyObserver, etc.
    ObserverClass = _get_observer_class('auto')
    assert ObserverClass is not None
    # Should NOT be kqueue (that's opt-in now)
    assert 'Kqueue' not in ObserverClass.__name__


def test_auto_uses_default_on_linux():
    """Verify auto mode uses platform default on Linux."""
    with patch('code_index_mcp.services.file_watcher_service.platform.system', return_value='Linux'):
        ObserverClass = _get_observer_class('auto')
        # On Linux, should get the default Observer (InotifyObserver)
        assert ObserverClass is not None


def test_auto_uses_default_on_windows():
    """Verify auto mode uses platform default on Windows."""
    with patch('code_index_mcp.services.file_watcher_service.platform.system', return_value='Windows'):
        ObserverClass = _get_observer_class('auto')
        # On Windows, should get the default Observer (WindowsApiObserver or ReadDirectoryChangesW)
        assert ObserverClass is not None


def test_explicit_kqueue():
    """Verify explicit kqueue selection works."""
    ObserverClass = _get_observer_class('kqueue')
    assert 'Kqueue' in ObserverClass.__name__


def test_explicit_polling():
    """Verify explicit polling selection works."""
    ObserverClass = _get_observer_class('polling')
    assert 'Polling' in ObserverClass.__name__


def test_fsevents_only_on_macos():
    """Verify fsevents raises error on non-macOS."""
    with patch('code_index_mcp.services.file_watcher_service.platform.system', return_value='Linux'):
        with pytest.raises(ValueError, match="only available on macOS"):
            _get_observer_class('fsevents')


def test_fsevents_works_on_macos():
    """Verify fsevents can be selected on macOS."""
    # Only run this test on actual macOS since fsevents module won't exist elsewhere
    if platform.system() == 'Darwin':
        ObserverClass = _get_observer_class('fsevents')
        assert 'FSEvents' in ObserverClass.__name__


def test_invalid_observer_type_falls_back_to_auto():
    """Verify invalid observer_type falls back to auto behavior."""
    # Invalid types should fall through to the else (auto) branch
    ObserverClass = _get_observer_class('invalid_type')
    # Should get the platform default (auto behavior), not kqueue
    assert ObserverClass is not None
    assert 'Kqueue' not in ObserverClass.__name__
