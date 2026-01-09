"""
Code Index MCP Server

This MCP server allows LLMs to index, search, and analyze code from a project directory.
It provides tools for file discovery, content retrieval, and code analysis.

This version uses a service-oriented architecture where MCP decorators delegate
to domain-specific services for business logic.
"""

# Standard library imports
import argparse
import inspect
import logging
import os
import signal
import sys
import threading
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import wraps
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

# Third-party imports
from mcp.server.fastmcp import Context, FastMCP

# Local imports
from .project_settings import ProjectSettings
from .services import FileService, FileWatcherService, SearchService, SettingsService
from .services.code_intelligence_service import CodeIntelligenceService
from .services.file_discovery_service import FileDiscoveryService
from .services.index_management_service import IndexManagementService
from .services.project_management_service import ProjectManagementService
from .services.settings_service import manage_temp_directory
from .services.system_management_service import SystemManagementService
from .utils import handle_mcp_tool_errors

# Concurrency control with FIFO queue for fair request ordering
MAX_CONCURRENT_REQUESTS = 3


class FIFOConcurrencyLimiter:
    """
    FIFO queue-based concurrency limiter with timeout.

    Ensures requests are processed in arrival order while limiting
    concurrent executions. Uses a ticket-based system for fairness.
    """

    def __init__(self, max_concurrent: int, timeout: float = 60.0):
        self._max_concurrent = max_concurrent
        self._timeout = timeout
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._active_count = 0
        self._next_ticket = 0
        self._serving_ticket = 0

    def acquire(self, timeout: float = None) -> int:
        """Acquire a slot in FIFO order. Returns ticket number.

        Raises TimeoutError if slot cannot be acquired within timeout.
        """
        timeout = timeout or self._timeout

        with self._condition:
            my_ticket = self._next_ticket
            self._next_ticket += 1

            # Wait until it's our turn AND there's capacity
            start = time.monotonic()

            while self._serving_ticket != my_ticket or self._active_count >= self._max_concurrent:
                remaining = timeout - (time.monotonic() - start)
                if remaining <= 0:
                    # Timeout: skip our ticket so others can proceed
                    if self._serving_ticket == my_ticket:
                        self._serving_ticket += 1
                        self._condition.notify_all()
                    raise TimeoutError(f"Queue timeout after {timeout}s (ticket {my_ticket})")

                self._condition.wait(timeout=min(remaining, 1.0))

            # It's our turn, take the slot
            self._active_count += 1
            self._serving_ticket += 1
            self._condition.notify_all()
            return my_ticket

    def release(self):
        """Release a slot."""
        with self._condition:
            self._active_count -= 1
            self._condition.notify_all()

    @property
    def stats(self) -> dict:
        """Get current queue statistics."""
        with self._lock:
            return {
                "active": self._active_count,
                "max_concurrent": self._max_concurrent,
                "next_ticket": self._next_ticket,
                "serving_ticket": self._serving_ticket,
                "queued": self._next_ticket - self._serving_ticket
            }


_concurrency_limiter = FIFOConcurrencyLimiter(MAX_CONCURRENT_REQUESTS)


# Multi-session stability: Handle SIGINT gracefully
# Claude Code sends SIGINT to existing MCP processes when new sessions start
# We ignore SIGINT to maintain stability for the original session
def _setup_signal_handlers():
    """Setup signal handlers for multi-session stability."""
    def sigint_handler(signum, frame):
        # Log but don't exit - let the MCP server continue serving
        logging.getLogger(__name__).warning(
            "Received SIGINT - ignoring for multi-session stability"
        )

    def sigterm_handler(signum, frame):
        # SIGTERM is a polite termination request - we should honor it
        logging.getLogger(__name__).info(
            "Received SIGTERM - shutting down gracefully"
        )
        sys.exit(0)

    # Windows doesn't have SIGINT the same way, but we handle it anyway
    if hasattr(signal, 'SIGINT'):
        signal.signal(signal.SIGINT, sigint_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, sigterm_handler)

_setup_signal_handlers()


def with_concurrency_limit(func):
    """Decorator to limit concurrent tool executions with FIFO ordering."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            _concurrency_limiter.acquire()
        except TimeoutError as e:
            # Return error dict instead of crashing
            logging.getLogger(__name__).warning("Queue timeout for %s: %s", func.__name__, e)
            return {
                "status": "error",
                "error": "queue_timeout",
                "message": f"Server busy, request queued too long. Please retry. ({e})"
            }
        try:
            return func(*args, **kwargs)
        finally:
            _concurrency_limiter.release()
    return wrapper


# Setup logging without writing to files
def setup_indexing_performance_logging():
    """Setup logging (stderr only); remove any file-based logging."""

    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # stderr for errors only
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    stderr_handler.setLevel(logging.ERROR)

    root_logger.addHandler(stderr_handler)
    root_logger.setLevel(logging.DEBUG)


# Initialize logging (no file handlers)
setup_indexing_performance_logging()
logger = logging.getLogger(__name__)


@dataclass
class CodeIndexerContext:
    """Context for the Code Indexer MCP server."""

    base_path: str
    settings: ProjectSettings
    file_count: int = 0
    file_watcher_service: FileWatcherService = None


@dataclass
class _CLIConfig:
    """Holds CLI configuration for bootstrap operations."""

    project_path: str | None = None


class _BootstrapRequestContext:
    """Minimal request context to reuse business services during bootstrap."""

    def __init__(self, lifespan_context: CodeIndexerContext):
        self.lifespan_context = lifespan_context
        self.session = None
        self.meta = None


_CLI_CONFIG = _CLIConfig()


@asynccontextmanager
async def indexer_lifespan(_server: FastMCP) -> AsyncIterator[CodeIndexerContext]:
    """Manage the lifecycle of the Code Indexer MCP server."""
    # Don't set a default path, user must explicitly set project path
    base_path = ""  # Empty string to indicate no path is set

    # Initialize settings manager with skip_load=True to skip loading files
    settings = ProjectSettings(base_path, skip_load=True)

    # Initialize context - file watcher will be initialized later when project path is set
    context = CodeIndexerContext(
        base_path=base_path, settings=settings, file_watcher_service=None
    )

    try:
        # Bootstrap project path when provided via CLI.
        if _CLI_CONFIG.project_path:
            bootstrap_ctx = Context(
                request_context=_BootstrapRequestContext(context), fastmcp=mcp
            )
            try:
                message = ProjectManagementService(bootstrap_ctx).initialize_project(
                    _CLI_CONFIG.project_path
                )
                logger.info("Project initialized from CLI flag: %s", message)
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Failed to initialize project from CLI flag: %s", exc)
                raise RuntimeError(
                    f"Failed to initialize project path '{_CLI_CONFIG.project_path}'"
                ) from exc

        # Provide context to the server
        yield context
    finally:
        # Stop file watcher if it was started
        if context.file_watcher_service:
            context.file_watcher_service.stop_monitoring()


# Create the MCP server with lifespan manager
mcp = FastMCP("CodeIndexer", lifespan=indexer_lifespan, dependencies=["pathlib"])

# ----- RESOURCES -----


@mcp.resource("files://{file_path}")
def get_file_content(file_path: str) -> str:
    """Get the content of a specific file."""
    decoded_path = unquote(file_path)
    ctx = mcp.get_context()
    return FileService(ctx).get_file_content(decoded_path)


# ----- TOOLS -----


@mcp.tool()
@handle_mcp_tool_errors(return_type="str")
def set_project_path(path: str, ctx: Context) -> str:
    """Set the base project path for indexing."""
    return ProjectManagementService(ctx).initialize_project(path)


@mcp.tool()
@handle_mcp_tool_errors(return_type="dict")
@with_concurrency_limit
def search_code_advanced(
    pattern: str,
    ctx: Context,
    case_sensitive: bool = True,
    context_lines: int = 0,
    file_pattern: str = None,
    fuzzy: bool = False,
    regex: bool = None,
    start_index: int = 0,
    max_results: int | None = 10,
) -> dict[str, Any]:
    """
Search for code pattern with pagination. Auto-selects best search tool (ugrep/ripgrep/ag/grep).
Supports glob file_pattern (e.g., "*.py"), regex patterns, and fuzzy matching (ugrep only).
"""
    return SearchService(ctx).search_code(
        pattern=pattern,
        case_sensitive=case_sensitive,
        context_lines=context_lines,
        file_pattern=file_pattern,
        fuzzy=fuzzy,
        regex=regex,
        start_index=start_index,
        max_results=max_results,
    )


@mcp.tool()
@handle_mcp_tool_errors(return_type="list")
def find_files(pattern: str, ctx: Context) -> list[str]:
    """
Find files matching glob pattern using in-memory index.
Supports path patterns (*.py, test_*.js) and filename-only matching (README.md).
"""
    return FileDiscoveryService(ctx).find_files(pattern)


@mcp.tool()
@handle_mcp_tool_errors(return_type="dict")
@with_concurrency_limit
def get_file_summary(file_path: str, ctx: Context) -> dict[str, Any]:
    """
    Get a summary of a specific file, including:
    - Line count
    - Function/class definitions (for supported languages)
    - Import statements
    - Basic complexity metrics
    """
    return CodeIntelligenceService(ctx).analyze_file(file_path)


@mcp.tool()
@handle_mcp_tool_errors(return_type="dict")
@with_concurrency_limit
def get_symbol_body(file_path: str, symbol_name: str, ctx: Context) -> dict[str, Any]:
    """
    Get the source code body of a specific symbol (function, method, or class).

    This tool retrieves only the code for the specified symbol, enabling efficient
    context usage by avoiding loading entire files.

    Args:
        file_path: Path to the file containing the symbol
        symbol_name: Name of the symbol to retrieve (e.g., "process_data", "MyClass.my_method")

    Returns:
        Dictionary containing:
        - status: "success" or "error"
        - symbol_name: Name of the symbol
        - type: Type of symbol (function, method, class)
        - line: Start line number
        - end_line: End line number
        - code: The actual source code
        - signature: Function/method signature (if available)
        - docstring: Documentation string (if available)
        - called_by: List of symbols that call this symbol
    """
    return CodeIntelligenceService(ctx).get_symbol_body(file_path, symbol_name)


@mcp.tool()
@handle_mcp_tool_errors(return_type="str")
def refresh_index(ctx: Context) -> str:
    """
Manually rebuild the project file index. Use after git operations or when index seems stale.
"""
    return IndexManagementService(ctx).rebuild_index()


@mcp.tool()
@handle_mcp_tool_errors(return_type="str")
@with_concurrency_limit
def build_deep_index(ctx: Context) -> str:
    """
    Build the deep index (full symbol extraction) for the current project.

    This performs a complete re-index and loads it into memory.
    """
    return IndexManagementService(ctx).rebuild_deep_index()


@mcp.tool()
@handle_mcp_tool_errors(return_type="dict")
def get_settings_info(ctx: Context) -> dict[str, Any]:
    """Get information about the project settings."""
    return SettingsService(ctx).get_settings_info()


@mcp.tool()
@handle_mcp_tool_errors(return_type="dict")
def create_temp_directory() -> dict[str, Any]:
    """Create the temporary directory used for storing index data."""
    return manage_temp_directory("create")


@mcp.tool()
@handle_mcp_tool_errors(return_type="dict")
def check_temp_directory() -> dict[str, Any]:
    """Check the temporary directory used for storing index data."""
    return manage_temp_directory("check")


@mcp.tool()
@handle_mcp_tool_errors(return_type="str")
def clear_settings(ctx: Context) -> str:
    """Clear all settings and cached data."""
    return SettingsService(ctx).clear_all_settings()


@mcp.tool()
@handle_mcp_tool_errors(return_type="str")
def refresh_search_tools(ctx: Context) -> str:
    """
    Manually re-detect the available command-line search tools on the system.
    This is useful if you have installed a new tool (like ripgrep) after starting the server.
    """
    return SearchService(ctx).refresh_search_tools()


@mcp.tool()
@handle_mcp_tool_errors(return_type="dict")
def get_file_watcher_status(ctx: Context) -> dict[str, Any]:
    """Get file watcher service status and statistics."""
    return SystemManagementService(ctx).get_file_watcher_status()


@mcp.tool()
@handle_mcp_tool_errors(return_type="str")
def configure_file_watcher(
    ctx: Context,
    enabled: bool = None,
    debounce_seconds: float = None,
    additional_exclude_patterns: list = None,
    observer_type: str = None,
) -> str:
    """Configure file watcher service settings.

    Args:
        enabled: Whether to enable file watcher
        debounce_seconds: Debounce time in seconds before triggering rebuild
        additional_exclude_patterns: Additional directory/file patterns to exclude
        observer_type: Observer backend to use. Options:
            - "auto" (default): kqueue on macOS for reliability, platform default elsewhere
            - "kqueue": Force kqueue observer (macOS/BSD)
            - "fsevents": Force FSEvents observer (macOS only, has known reliability issues)
            - "polling": Cross-platform polling fallback (slower but most compatible)
    """
    return SystemManagementService(ctx).configure_file_watcher(
        enabled, debounce_seconds, additional_exclude_patterns, observer_type
    )


# ----- PROMPTS -----
# Removed: analyze_code, code_search, set_project prompts


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the MCP server."""
    parser = argparse.ArgumentParser(description="Code Index MCP server")
    parser.add_argument(
        "--project-path",
        dest="project_path",
        help="Set the project path on startup (equivalent to calling set_project_path).",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Transport protocol to use (default: stdio).",
    )
    parser.add_argument(
        "--mount-path",
        dest="mount_path",
        default=None,
        help="Mount path when using SSE transport.",
    )
    parser.add_argument(
        "--indexer-path",
        dest="indexer_path",
        default=None,
        help="Custom path for storing indices (overrides default /tmp/code_indexer location).",
    )
    parser.add_argument(
        "--tool-prefix",
        dest="tool_prefix",
        default=None,
        help="Prefix to add to all tool names (e.g., 'prefix:' -> 'prefix:tool_name').",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for SSE transport (default: 8000)."
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None):
    """Main function to run the MCP server."""
    args = _parse_args(argv)

    # Store CLI configuration for lifespan bootstrap.
    _CLI_CONFIG.project_path = args.project_path

    # Configure custom index root if provided
    if args.indexer_path:
        # Patch ProjectSettings class to use the custom root
        ProjectSettings.custom_index_root = args.indexer_path

        # Ensure the directory exists
        try:
            os.makedirs(args.indexer_path, exist_ok=True)
        except Exception as e:
            logger.error(
                f"Failed to create custom indexer path {args.indexer_path}: {e}"
            )
            sys.exit(1)

    # Rename tools if prefix is provided
    if args.tool_prefix:
        prefix = args.tool_prefix
        try:
            # Access internal tool registry (FastMCP specific)
            # FastMCP stores tools in _tool_manager._tools or directly in _tools
            # We need to support both for resilience
            tool_registry = None
            if hasattr(mcp, "_tool_manager") and hasattr(mcp._tool_manager, "_tools"):
                tool_registry = mcp._tool_manager._tools
            elif hasattr(mcp, "_tools"):
                tool_registry = mcp._tools

            if tool_registry:
                # Create a new registry with prefixed names
                new_registry = {}
                for name, tool in tool_registry.items():
                    new_name = f"{prefix}{name}"
                    tool.name = new_name
                    new_registry[new_name] = tool

                # Replace the registry
                if hasattr(mcp, "_tool_manager") and hasattr(
                    mcp._tool_manager, "_tools"
                ):
                    mcp._tool_manager._tools = new_registry
                elif hasattr(mcp, "_tools"):
                    mcp._tools = new_registry

                logger.info(
                    f"Applied tool prefix '{prefix}' to {len(new_registry)} tools"
                )
            else:
                logger.warning("Could not find tool registry to apply prefix")

        except Exception as e:
            logger.error(f"Failed to apply tool prefix: {e}")
            # Fatal error: cannot apply requested prefix
            sys.exit(1)

    # For HTTP transports, add project context middleware for per-project isolation
    if args.transport in ("sse", "streamable-http"):
        import asyncio
        import uvicorn
        from .middleware import ProjectContextMiddleware

        # Set port via settings
        mcp.settings.port = args.port

        # Get the appropriate Starlette app
        if args.transport == "sse":
            starlette_app = mcp.sse_app(args.mount_path)
        else:
            starlette_app = mcp.streamable_http_app()

        # Add project context middleware for per-project manager isolation
        starlette_app.add_middleware(ProjectContextMiddleware)
        logger.info("Added ProjectContextMiddleware for per-project isolation")

        # Run with uvicorn
        config = uvicorn.Config(
            starlette_app,
            host=mcp.settings.host,
            port=mcp.settings.port,
            log_level="warning",
        )
        server = uvicorn.Server(config)

        try:
            asyncio.run(server.serve())
        except RuntimeError as exc:
            logger.error("MCP server terminated with error: %s", exc)
            raise SystemExit(1) from exc
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Unexpected MCP server error: %s", exc)
            raise
    else:
        # For stdio transport, use default run method
        try:
            mcp.run(transport=args.transport)
        except RuntimeError as exc:
            logger.error("MCP server terminated with error: %s", exc)
            raise SystemExit(1) from exc
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Unexpected MCP server error: %s", exc)
            raise


if __name__ == "__main__":
    main()
