"""
File Watcher Service for automatic index rebuilds.

This module provides file system monitoring capabilities that automatically
trigger index rebuilds when relevant files are modified, created, or deleted.
It uses the watchdog library for cross-platform file system event monitoring.
"""
# pylint: disable=missing-function-docstring  # Fallback stub methods don't need docstrings

import logging
import os
import platform
import traceback
from threading import Timer
from typing import Optional, Callable, List, Type
from pathlib import Path

try:
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False


def _get_observer_class(observer_type: str = "auto") -> Type:
    """Get the appropriate Observer class based on config and platform.

    On macOS, the default FSEventsObserver has known reliability issues including
    thread safety problems, deadlocks, and "SystemError: Cannot start fsevents
    stream" errors. This function defaults to KqueueObserver on macOS for stability.

    See: https://github.com/gorakhargosh/watchdog/issues/765

    Args:
        observer_type: One of "auto", "kqueue", "fsevents", "polling"
            - "auto": kqueue on macOS, platform default elsewhere (recommended)
            - "kqueue": Force kqueue observer (macOS/BSD)
            - "fsevents": Force FSEvents observer (macOS only, has known issues)
            - "polling": Cross-platform polling fallback (slower but most compatible)

    Returns:
        Observer class to instantiate

    Raises:
        ValueError: If fsevents requested on non-macOS platform
        ImportError: If requested observer type is not available
    """
    system = platform.system()

    if observer_type == "kqueue":
        from watchdog.observers.kqueue import KqueueObserver
        return KqueueObserver
    elif observer_type == "fsevents":
        if system != "Darwin":
            raise ValueError("fsevents observer is only available on macOS")
        from watchdog.observers.fsevents import FSEventsObserver
        return FSEventsObserver
    elif observer_type == "polling":
        from watchdog.observers.polling import PollingObserver
        return PollingObserver
    else:  # "auto"
        # Use platform default (FSEvents on macOS, inotify on Linux, etc.)
        from watchdog.observers import Observer
        return Observer


if not WATCHDOG_AVAILABLE:
    # Fallback classes for when watchdog is not available
    class Observer:
        """Fallback Observer class when watchdog library is not available."""
        def __init__(self):
            pass
        def schedule(self, *args, **kwargs):
            pass
        def start(self):
            pass
        def stop(self):
            pass
        def join(self, *args, **kwargs):
            pass
        def is_alive(self):
            return False

    class FileSystemEventHandler:
        """Fallback FileSystemEventHandler class when watchdog library is not available."""
        def __init__(self):
            pass

    class FileSystemEvent:
        """Fallback FileSystemEvent class when watchdog library is not available."""
        def __init__(self):
            self.is_directory = False
            self.src_path = ""
            self.event_type = ""

    WATCHDOG_AVAILABLE = False

from .base_service import BaseService
from ..constants import SUPPORTED_EXTENSIONS


class FileWatcherService(BaseService):
    """
    Service for monitoring file system changes and triggering index rebuilds.

    This service uses the watchdog library to monitor file system events and
    automatically triggers background index rebuilds when relevant files change.
    It includes intelligent debouncing to batch rapid changes and filtering
    to only monitor relevant file types.
    """
    MAX_RESTART_ATTEMPTS = 3

    def __init__(self, ctx):
        """
        Initialize the file watcher service.

        Args:
            ctx: The MCP Context object
        """
        super().__init__(ctx)
        self.logger = logging.getLogger(__name__)
        self.observer: Optional[Observer] = None
        self.event_handler: Optional[DebounceEventHandler] = None
        self.is_monitoring = False
        self.restart_attempts = 0
        self.rebuild_callback: Optional[Callable] = None

        # Check if watchdog is available
        if not WATCHDOG_AVAILABLE:
            self.logger.warning("Watchdog library not available - file watcher disabled")

    def start_monitoring(self, rebuild_callback: Callable) -> bool:
        """
        Start file system monitoring.

        Args:
            rebuild_callback: Function to call when rebuild is needed

        Returns:
            True if monitoring started successfully, False otherwise
        """
        if not WATCHDOG_AVAILABLE:
            self.logger.warning("Cannot start file watcher - watchdog library not available")
            return False

        if self.is_monitoring:
            self.logger.debug("File watcher already monitoring")
            return True

        # Validate project setup
        error = self._validate_project_setup()
        if error:
            self.logger.error("Cannot start file watcher: %s", error)
            return False

        self.rebuild_callback = rebuild_callback

        # Get config options
        config = self.settings.get_file_watcher_config()
        debounce_seconds = config.get('debounce_seconds', 6.0)
        observer_type = config.get('observer_type', 'auto')

        try:
            ObserverClass = _get_observer_class(observer_type)
            self.observer = ObserverClass()
            self.logger.info("Using %s observer (type=%s)", ObserverClass.__name__, observer_type)
            self.event_handler = DebounceEventHandler(
                debounce_seconds=debounce_seconds,
                rebuild_callback=self.rebuild_callback,
                base_path=Path(self.base_path),
                logger=self.logger
            )

            # Log detailed Observer setup
            watch_path = str(self.base_path)
            self.logger.debug("Scheduling Observer for path: %s", watch_path)

            self.observer.schedule(
                self.event_handler,
                watch_path,
                recursive=True
            )

            # Log Observer start
            self.logger.debug("Starting Observer...")
            self.observer.start()
            self.is_monitoring = True
            self.restart_attempts = 0

            # Log Observer thread info
            if hasattr(self.observer, '_thread'):
                self.logger.debug("Observer thread: %s", self.observer._thread)

            # Verify observer is actually running
            if self.observer.is_alive():
                self.logger.info(
                    "File watcher started successfully",
                    extra={
                        "debounce_seconds": debounce_seconds,
                        "monitored_path": str(self.base_path),
                        "supported_extensions": len(SUPPORTED_EXTENSIONS)
                    }
                )

                # Add diagnostic test - create a test event to verify Observer works
                self.logger.debug("Observer thread is alive: %s", self.observer.is_alive())
                self.logger.debug("Monitored path exists: %s", os.path.exists(str(self.base_path)))
                self.logger.debug("Event handler is set: %s", self.event_handler is not None)

                # Log current directory for comparison
                current_dir = os.getcwd()
                self.logger.debug("Current working directory: %s", current_dir)
                self.logger.debug("Are paths same: %s", os.path.normpath(current_dir) == os.path.normpath(str(self.base_path)))

                return True
            else:
                self.logger.error("File watcher failed to start - Observer not alive")
                return False

        except Exception as e:
            self.logger.warning("Failed to start file watcher: %s", e)
            self.logger.info("Falling back to reactive index refresh")
            return False

    def stop_monitoring(self) -> None:
        """
        Stop file system monitoring and cleanup all resources.

        This method ensures complete cleanup of:
        - Observer thread
        - Event handler
        - Debounce timers
        - Monitoring state
        """
        if not self.observer and not self.is_monitoring:
            # Already stopped or never started
            return

        self.logger.info("Stopping file watcher monitoring...")

        try:
            # Step 1: Stop the observer first
            if self.observer:
                self.logger.debug("Stopping observer...")
                self.observer.stop()

                # Step 2: Cancel any active debounce timer
                if self.event_handler and self.event_handler.debounce_timer:
                    self.logger.debug("Cancelling debounce timer...")
                    self.event_handler.debounce_timer.cancel()

                # Step 3: Wait for observer thread to finish (with timeout)
                self.logger.debug("Waiting for observer thread to finish...")
                self.observer.join(timeout=5.0)

                # Step 4: Check if thread actually finished
                if self.observer.is_alive():
                    self.logger.warning("Observer thread did not stop within timeout")
                else:
                    self.logger.debug("Observer thread stopped successfully")

            # Step 5: Clear all references
            self.observer = None
            self.event_handler = None
            self.rebuild_callback = None
            self.is_monitoring = False

            self.logger.info("File watcher stopped and cleaned up successfully")

        except Exception as e:
            self.logger.error("Error stopping file watcher: %s", e)

            # Force cleanup even if there were errors
            self.observer = None
            self.event_handler = None
            self.rebuild_callback = None
            self.is_monitoring = False

    def is_active(self) -> bool:
        """
        Check if file watcher is actively monitoring.

        Returns:
            True if actively monitoring, False otherwise
        """
        return (self.is_monitoring and
                self.observer and
                self.observer.is_alive())

    def restart_observer(self) -> bool:
        """
        Attempt to restart the file system observer.

        Returns:
            True if restart successful, False otherwise
        """
        if self.restart_attempts >= self.MAX_RESTART_ATTEMPTS:
            self.logger.error("Max restart attempts reached, file watcher disabled")
            return False

        self.logger.info("Attempting to restart file watcher (attempt %d)",
                         self.restart_attempts + 1)
        self.restart_attempts += 1

        # Stop current observer if running
        if self.observer:
            try:
                self.observer.stop()
                self.observer.join(timeout=2.0)
            except Exception as e:
                self.logger.warning("Error stopping observer during restart: %s", e)

        # Start new observer
        try:
            config = self.settings.get_file_watcher_config()
            observer_type = config.get('observer_type', 'auto')
            ObserverClass = _get_observer_class(observer_type)
            self.observer = ObserverClass()
            self.observer.schedule(
                self.event_handler,
                str(self.base_path),
                recursive=True
            )
            self.observer.start()
            self.is_monitoring = True

            self.logger.info("File watcher restarted successfully with %s", ObserverClass.__name__)
            return True

        except Exception as e:
            self.logger.error("Failed to restart file watcher: %s", e)
            return False

    def get_status(self) -> dict:
        """
        Get current file watcher status information.

        Returns:
            Dictionary containing status information
        """
        # Get current config
        config = self.settings.get_file_watcher_config()
        debounce_seconds = config.get('debounce_seconds', 6.0)
        observer_type = config.get('observer_type', 'auto')

        # Determine actual observer class name
        observer_class_name = None
        if self.observer:
            observer_class_name = type(self.observer).__name__

        return {
            "available": WATCHDOG_AVAILABLE,
            "active": self.is_active(),
            "monitoring": self.is_monitoring,
            "restart_attempts": self.restart_attempts,
            "debounce_seconds": debounce_seconds,
            "observer_type": observer_type,
            "observer_class": observer_class_name,
            "base_path": self.base_path if self.base_path else None,
            "observer_alive": self.observer.is_alive() if self.observer else False
        }


class DebounceEventHandler(FileSystemEventHandler):
    """
    File system event handler with debouncing capability.

    This handler filters file system events to only relevant files and
    implements a debounce mechanism to batch rapid changes into single
    rebuild operations.
    """

    def __init__(self, debounce_seconds: float, rebuild_callback: Callable,
                 base_path: Path, logger: logging.Logger, additional_excludes: Optional[List[str]] = None):
        """
        Initialize the debounce event handler.

        Args:
            debounce_seconds: Number of seconds to wait before triggering rebuild
            rebuild_callback: Function to call when rebuild is needed
            base_path: Base project path for filtering
            logger: Logger instance for debug messages
            additional_excludes: Additional patterns to exclude
        """
        from ..utils import FileFilter
        
        super().__init__()
        self.debounce_seconds = debounce_seconds
        self.rebuild_callback = rebuild_callback
        self.base_path = base_path
        self.debounce_timer: Optional[Timer] = None
        self.logger = logger

        # Use centralized file filtering
        self.file_filter = FileFilter(additional_excludes)

    def on_any_event(self, event: FileSystemEvent) -> None:
        """
        Handle any file system event.

        Args:
            event: The file system event
        """
        # Check if event should be processed
        should_process = self.should_process_event(event)

        if should_process:
            self.logger.info("File changed: %s - %s", event.event_type, event.src_path)
            self.reset_debounce_timer()
        else:
            # Only log at debug level for filtered events
            self.logger.debug("Filtered: %s - %s", event.event_type, event.src_path)

    def should_process_event(self, event: FileSystemEvent) -> bool:
        """
        Determine if event should trigger index rebuild using centralized filtering.

        Args:
            event: The file system event to evaluate

        Returns:
            True if event should trigger rebuild, False otherwise
        """
        # Skip directory events
        if event.is_directory:
            self.logger.debug("Skipping directory event: %s", event.src_path)
            return False

        # Select path to check: dest_path for moves, src_path for others
        if event.event_type == 'moved':
            if not hasattr(event, 'dest_path'):
                return False
            target_path = event.dest_path
        else:
            target_path = event.src_path

        # Use centralized filtering logic
        try:
            path = Path(target_path)
            should_process = self.file_filter.should_process_path(path, self.base_path)
            
            # Skip temporary files using centralized logic
            if not should_process or self.file_filter.is_temporary_file(path):
                return False
                
            return True
        except Exception:
            return False






    def reset_debounce_timer(self) -> None:
        """Reset the debounce timer, canceling any existing timer."""
        if self.debounce_timer:
            self.debounce_timer.cancel()

        self.debounce_timer = Timer(
            self.debounce_seconds,
            self.trigger_rebuild
        )
        self.debounce_timer.start()

    def trigger_rebuild(self) -> None:
        """Trigger index rebuild after debounce period."""
        self.logger.info("File changes detected, triggering rebuild")

        if self.rebuild_callback:
            try:
                result = self.rebuild_callback()
            except Exception as e:
                self.logger.error("Rebuild callback failed: %s", e)
                traceback_msg = traceback.format_exc()
                self.logger.error("Traceback: %s", traceback_msg)
        else:
            self.logger.warning("No rebuild callback configured")
