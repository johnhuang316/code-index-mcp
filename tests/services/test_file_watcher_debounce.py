"""Tests for debounce handler lifecycle safety."""

import logging
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace

import pytest

from code_index_mcp.services import file_watcher_service
from code_index_mcp.services.file_watcher_service import (
    DebounceEventHandler,
    FileWatcherService,
)


class DummyTimer:
    """Minimal timer test double that never starts a thread."""

    def __init__(self, interval, callback, args=None):
        self.interval = interval
        self.callback = callback
        self.args = tuple(args or ())
        self.started = False
        self.cancelled = False

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True


class FakeObserver:
    """Observer test double for restart coverage."""

    def __init__(self):
        self.scheduled = []
        self.stopped = False
        self.join_timeout = None
        self.started = False
        self.alive = True

    def schedule(self, handler, path, recursive=True):
        self.scheduled.append((handler, path, recursive))

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True
        self.alive = False

    def join(self, timeout=None):
        self.join_timeout = timeout

    def is_alive(self):
        return self.alive


@pytest.fixture
def no_thread_timer(monkeypatch):
    monkeypatch.setattr(file_watcher_service, "Timer", DummyTimer)


def test_trigger_rebuild_is_noop_after_handler_stopped():
    """Stopped handlers should not execute queued rebuild callbacks."""
    calls = []
    handler = DebounceEventHandler(
        debounce_seconds=1.0,
        rebuild_callback=lambda: calls.append("rebuilt"),
        base_path=Path("."),
        logger=logging.getLogger(__name__),
    )

    handler.stop()
    handler.trigger_rebuild()

    assert calls == []


def test_old_timer_generation_does_not_call_rebuild_after_reset(no_thread_timer):
    """Superseded timer callbacks should be ignored."""
    calls = []
    handler = DebounceEventHandler(
        debounce_seconds=1.0,
        rebuild_callback=lambda: calls.append("rebuilt"),
        base_path=Path("."),
        logger=logging.getLogger(__name__),
    )

    handler.reset_debounce_timer()
    first_generation = handler._generation
    first_timer = handler.debounce_timer
    handler.reset_debounce_timer()

    handler.trigger_rebuild(first_generation)

    assert calls == []
    assert first_timer.cancelled is True


def test_stop_waits_for_inflight_callback_before_returning():
    """Stopping should wait for an already-started callback to finish."""
    callback_started = Event()
    allow_callback_finish = Event()
    stop_finished = Event()

    def rebuild_callback():
        callback_started.set()
        allow_callback_finish.wait(timeout=1.0)

    handler = DebounceEventHandler(
        debounce_seconds=1.0,
        rebuild_callback=rebuild_callback,
        base_path=Path("."),
        logger=logging.getLogger(__name__),
    )

    trigger_thread = Thread(target=handler.trigger_rebuild)
    trigger_thread.start()
    assert callback_started.wait(timeout=1.0)

    stop_thread = Thread(target=lambda: (handler.stop(), stop_finished.set()))
    stop_thread.start()

    assert not stop_finished.wait(timeout=0.1)

    allow_callback_finish.set()
    trigger_thread.join(timeout=1.0)
    stop_thread.join(timeout=1.0)

    assert stop_finished.is_set()


def test_restart_observer_invalidates_old_handler_state(monkeypatch):
    """Restart should stop the old handler and install a fresh one."""
    calls = []
    old_handler = DebounceEventHandler(
        debounce_seconds=1.0,
        rebuild_callback=lambda: calls.append("rebuilt"),
        base_path=Path("."),
        logger=logging.getLogger(__name__),
    )
    old_handler.debounce_timer = DummyTimer(1.0, old_handler.trigger_rebuild, args=(1,))
    old_handler._generation = 1

    service = object.__new__(FileWatcherService)
    service.logger = logging.getLogger(__name__)
    service.helper = SimpleNamespace(
        base_path=".",
        settings=SimpleNamespace(
            get_file_watcher_config=lambda: {
                "observer_type": "auto",
                "debounce_seconds": 2.5,
            }
        ),
    )
    service.observer = FakeObserver()
    service.event_handler = old_handler
    service.is_monitoring = True
    service.restart_attempts = 0
    service.rebuild_callback = lambda: calls.append("rebuilt")

    monkeypatch.setattr(file_watcher_service, "_get_observer_class", lambda observer_type: FakeObserver)

    assert service.restart_observer() is True

    assert service.event_handler is not old_handler
    assert old_handler._stopped is True
    assert old_handler.debounce_timer is None
    assert isinstance(service.observer, FakeObserver)
    assert service.observer.started is True
    assert service.observer.scheduled == [(service.event_handler, ".", True)]

    old_handler.trigger_rebuild(old_handler._generation)

    assert calls == []
