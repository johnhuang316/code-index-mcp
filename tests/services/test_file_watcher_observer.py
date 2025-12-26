"""Tests for file watcher observer selection and per-directory scheduling.

Verify that the observer factory correctly selects the appropriate
observer class based on platform and configuration, and that kqueue
observers use per-directory scheduling to avoid excessive file descriptors.
"""

import platform
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from code_index_mcp.services.file_watcher_service import (
    _get_observer_class,
    FileWatcherService,
    DebounceEventHandler
)
from code_index_mcp.utils import FileFilter


def test_auto_uses_kqueue_on_macos():
    """Verify auto mode selects kqueue on macOS."""
    with patch('code_index_mcp.services.file_watcher_service.platform.system', return_value='Darwin'):
        ObserverClass = _get_observer_class('auto')
        assert 'Kqueue' in ObserverClass.__name__


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
    with patch('code_index_mcp.services.file_watcher_service.platform.system', return_value='Darwin'):
        ObserverClass = _get_observer_class('invalid_type')
        # Should get kqueue on macOS (auto behavior)
        assert 'Kqueue' in ObserverClass.__name__


# ============================================================================
# Tests for per-directory scheduling
# ============================================================================

class TestCollectWatchDirectories:
    """Tests for _collect_watch_directories method."""

    def test_excludes_node_modules(self, tmp_path):
        """Verify node_modules directories are excluded."""
        # Create directory structure
        src = tmp_path / "src"
        src.mkdir()
        (src / "components").mkdir()
        node_modules = tmp_path / "node_modules"
        node_modules.mkdir()
        (node_modules / "lodash").mkdir()

        file_filter = FileFilter()

        # Create a mock service to call the method
        mock_ctx = MagicMock()
        mock_ctx.request_context.lifespan_context = {}
        service = FileWatcherService(mock_ctx)

        dirs = service._collect_watch_directories(tmp_path, file_filter)
        dir_names = [d.name for d in dirs]

        assert "src" in dir_names
        assert "components" in dir_names
        assert "node_modules" not in dir_names
        assert "lodash" not in dir_names

    def test_excludes_git_directory(self, tmp_path):
        """Verify .git directories are excluded."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "objects").mkdir()
        (tmp_path / "src").mkdir()

        file_filter = FileFilter()
        mock_ctx = MagicMock()
        mock_ctx.request_context.lifespan_context = {}
        service = FileWatcherService(mock_ctx)

        dirs = service._collect_watch_directories(tmp_path, file_filter)
        dir_names = [d.name for d in dirs]

        assert "src" in dir_names
        assert ".git" not in dir_names
        assert "objects" not in dir_names

    def test_includes_nested_src_directories(self, tmp_path):
        """Verify nested source directories are included."""
        # Create nested structure: src/components/buttons
        src = tmp_path / "src"
        src.mkdir()
        components = src / "components"
        components.mkdir()
        buttons = components / "buttons"
        buttons.mkdir()

        file_filter = FileFilter()
        mock_ctx = MagicMock()
        mock_ctx.request_context.lifespan_context = {}
        service = FileWatcherService(mock_ctx)

        dirs = service._collect_watch_directories(tmp_path, file_filter)

        assert tmp_path in dirs
        assert src in dirs
        assert components in dirs
        assert buttons in dirs

    def test_respects_additional_excludes(self, tmp_path):
        """Verify additional exclude patterns are respected."""
        (tmp_path / "src").mkdir()
        (tmp_path / "vendor").mkdir()
        (tmp_path / "custom_exclude").mkdir()

        # Add custom exclusion
        file_filter = FileFilter(additional_excludes=["custom_exclude"])
        mock_ctx = MagicMock()
        mock_ctx.request_context.lifespan_context = {}
        service = FileWatcherService(mock_ctx)

        dirs = service._collect_watch_directories(tmp_path, file_filter)
        dir_names = [d.name for d in dirs]

        assert "src" in dir_names
        # vendor is in default excludes
        assert "vendor" not in dir_names
        # custom_exclude was added
        assert "custom_exclude" not in dir_names


class TestIsKqueueObserver:
    """Tests for _is_kqueue_observer method."""

    def test_identifies_kqueue_observer(self):
        """Verify KqueueObserver is correctly identified."""
        mock_ctx = MagicMock()
        mock_ctx.request_context.lifespan_context = {}
        service = FileWatcherService(mock_ctx)

        KqueueObserver = _get_observer_class('kqueue')
        assert service._is_kqueue_observer(KqueueObserver) is True

    def test_identifies_non_kqueue_observer(self):
        """Verify non-kqueue observers return False."""
        mock_ctx = MagicMock()
        mock_ctx.request_context.lifespan_context = {}
        service = FileWatcherService(mock_ctx)

        PollingObserver = _get_observer_class('polling')
        assert service._is_kqueue_observer(PollingObserver) is False


class TestScheduleWatches:
    """Tests for _schedule_watches method."""

    def test_kqueue_schedules_per_directory(self, tmp_path):
        """Verify kqueue uses non-recursive per-directory scheduling."""
        (tmp_path / "src").mkdir()
        (tmp_path / "lib").mkdir()

        file_filter = FileFilter()
        mock_ctx = MagicMock()
        mock_ctx.request_context.lifespan_context = {}
        service = FileWatcherService(mock_ctx)

        mock_observer = MagicMock()
        mock_handler = MagicMock()

        watch_count = service._schedule_watches(
            mock_observer, mock_handler, tmp_path,
            file_filter, use_per_directory=True
        )

        # Should schedule 3 directories: root, src, lib
        assert watch_count == 3
        assert mock_observer.schedule.call_count == 3

        # All calls should be non-recursive
        for call in mock_observer.schedule.call_args_list:
            args, kwargs = call
            assert kwargs.get('recursive', True) is False

    def test_non_kqueue_schedules_recursive(self, tmp_path):
        """Verify non-kqueue uses single recursive scheduling."""
        (tmp_path / "src").mkdir()
        (tmp_path / "lib").mkdir()

        file_filter = FileFilter()
        mock_ctx = MagicMock()
        mock_ctx.request_context.lifespan_context = {}
        service = FileWatcherService(mock_ctx)

        mock_observer = MagicMock()
        mock_handler = MagicMock()

        watch_count = service._schedule_watches(
            mock_observer, mock_handler, tmp_path,
            file_filter, use_per_directory=False
        )

        # Should schedule just 1 recursive watch
        assert watch_count == 1
        assert mock_observer.schedule.call_count == 1

        # Call should be recursive
        args, kwargs = mock_observer.schedule.call_args
        assert kwargs.get('recursive', False) is True


class TestDirectoryCreationRestart:
    """Tests for watcher restart on new directory creation."""

    def test_new_directory_triggers_restart_timer(self):
        """Verify new non-excluded directory schedules restart."""
        mock_watcher = MagicMock()
        handler = DebounceEventHandler(
            debounce_seconds=1.0,
            rebuild_callback=MagicMock(),
            base_path=Path("/test"),
            logger=MagicMock(),
            watcher_service=mock_watcher
        )

        # Simulate directory created event
        handler._handle_directory_created("/test/new_component")

        # Should have scheduled a restart timer
        assert handler.restart_timer is not None

    def test_excluded_directory_does_not_trigger_restart(self):
        """Verify excluded directory does not trigger restart."""
        mock_watcher = MagicMock()
        handler = DebounceEventHandler(
            debounce_seconds=1.0,
            rebuild_callback=MagicMock(),
            base_path=Path("/test"),
            logger=MagicMock(),
            watcher_service=mock_watcher
        )

        # Simulate node_modules directory created
        handler._handle_directory_created("/test/node_modules")

        # Should NOT have scheduled a restart timer
        assert handler.restart_timer is None

    def test_restart_debounces_multiple_directories(self):
        """Verify rapid directory creations are debounced."""
        mock_watcher = MagicMock()
        handler = DebounceEventHandler(
            debounce_seconds=1.0,
            rebuild_callback=MagicMock(),
            base_path=Path("/test"),
            logger=MagicMock(),
            watcher_service=mock_watcher
        )

        # Simulate mkdir -p a/b/c - multiple rapid directory creations
        handler._handle_directory_created("/test/a")
        first_timer = handler.restart_timer

        handler._handle_directory_created("/test/a/b")
        second_timer = handler.restart_timer

        handler._handle_directory_created("/test/a/b/c")
        third_timer = handler.restart_timer

        # Each call should cancel the previous timer and create a new one
        # The final timer should be different from the first
        assert first_timer is not third_timer
        # Only one timer should be active
        assert handler.restart_timer is third_timer

    def test_no_restart_without_watcher_service(self):
        """Verify no error when watcher_service is None."""
        handler = DebounceEventHandler(
            debounce_seconds=1.0,
            rebuild_callback=MagicMock(),
            base_path=Path("/test"),
            logger=MagicMock(),
            watcher_service=None  # No watcher service
        )

        # Should not raise, just log and return
        handler._handle_directory_created("/test/new_dir")
        assert handler.restart_timer is None
