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
import sys
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Dict, Any, List, Optional

# Third-party imports
from mcp.server.fastmcp import FastMCP, Context

# Local imports
from .project_settings import ProjectSettings
from .services import (
    SearchService, FileService, SettingsService, FileWatcherService
)
from .services.settings_service import manage_temp_directory
from .services.file_discovery_service import FileDiscoveryService
from .services.project_management_service import ProjectManagementService
from .services.index_management_service import IndexManagementService
from .services.code_intelligence_service import CodeIntelligenceService
from .services.system_management_service import SystemManagementService
from .utils import (
    handle_mcp_resource_errors, handle_mcp_tool_errors
)

# Setup logging without writing to files
def setup_indexing_performance_logging():
    """Setup logging (stderr only); remove any file-based logging."""

    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

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
        base_path=base_path,
        settings=settings,
        file_watcher_service=None
    )

    try:
        # Bootstrap project path when provided via CLI.
        if _CLI_CONFIG.project_path:
            bootstrap_ctx = Context(
                request_context=_BootstrapRequestContext(context),
                fastmcp=mcp
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

@mcp.resource("config://code-indexer")
@handle_mcp_resource_errors
def get_config() -> str:
    """Get the current configuration of the Code Indexer."""
    ctx = mcp.get_context()
    return ProjectManagementService(ctx).get_project_config()

@mcp.resource("files://{file_path}")
@handle_mcp_resource_errors
def get_file_content(file_path: str) -> str:
    """Get the content of a specific file."""
    ctx = mcp.get_context()
    # Use FileService for simple file reading - this is appropriate for a resource
    return FileService(ctx).get_file_content(file_path)

# Removed: structure://project resource - not necessary for most workflows
# Removed: settings://stats resource - this information is available via get_settings_info() tool
# and is more of a debugging/technical detail rather than context AI needs

# ----- TOOLS -----

@mcp.tool()
@handle_mcp_tool_errors(return_type='str')
def set_project_path(path: str, ctx: Context) -> str:
    """Set the base project path for indexing."""
    return ProjectManagementService(ctx).initialize_project(path)

@mcp.tool()
@handle_mcp_tool_errors(return_type='dict')
def search_code_advanced(
    pattern: str,
    ctx: Context,
    case_sensitive: bool = True,
    context_lines: int = 0,
    file_pattern: str = None,
    fuzzy: bool = False,
    regex: bool = None,
    start_index: int = 0,
        max_results: Optional[int] = 10
) -> Dict[str, Any]:
    """
    Search for a code pattern in the project using an advanced, fast tool with pagination support.

    This tool automatically selects the best available command-line search tool
    (like ugrep, ripgrep, ag, or grep) for maximum performance.

    Args:
        pattern: The search pattern. Can be literal text or regex (see regex parameter).
        case_sensitive: Whether the search should be case-sensitive.
        context_lines: Number of lines to show before and after the match.
        file_pattern: A glob pattern to filter files to search in
                     (e.g., "*.py", "*.js", "test_*.py").
                     All search tools now handle glob patterns consistently:
                     - ugrep: Uses glob patterns (*.py, *.{js,ts})
                     - ripgrep: Uses glob patterns (*.py, *.{js,ts})
                     - ag (Silver Searcher): Automatically converts globs to regex patterns
                     - grep: Basic glob pattern matching
                     All common glob patterns like "*.py", "test_*.js", "src/*.ts" are supported.
        fuzzy: If True, enables fuzzy/partial matching behavior varies by search tool:
               - ugrep: Native fuzzy search with --fuzzy flag (true edit-distance fuzzy search)
               - ripgrep, ag, grep, basic: Word boundary pattern matching (not true fuzzy search)
               IMPORTANT: Only ugrep provides true fuzzy search. Other tools use word boundary
               matching which allows partial matches at word boundaries.
               For exact literal matches, set fuzzy=False (default and recommended).
        regex: Controls regex pattern matching behavior:
               - If True, enables regex pattern matching
               - If False, forces literal string search
               - If None (default), automatically detects regex patterns and enables regex for patterns like "ERROR|WARN"
               The pattern will always be validated for safety to prevent ReDoS attacks.
        start_index: Zero-based offset into the flattened match list. Use to fetch subsequent pages.
        max_results: Maximum number of matches to return (default 10). Pass None to retrieve all matches.

    Returns:
        A dictionary containing:
        - results: List of matches with file, line, and text keys.
        - pagination: Metadata with total_matches, returned, start_index, end_index, has_more,
                      and optionally max_results.
        If an error occurs, an error message is returned instead.

    """
    return SearchService(ctx).search_code(
        pattern=pattern,
        case_sensitive=case_sensitive,
        context_lines=context_lines,
        file_pattern=file_pattern,
        fuzzy=fuzzy,
        regex=regex,
        start_index=start_index,
        max_results=max_results
    )

@mcp.tool()
@handle_mcp_tool_errors(return_type='str')
def find_files(pattern: str, ctx: Context) -> str:
    """
    Find files matching a glob pattern using pre-built file index.

    Use when:
    - Looking for files by pattern (e.g., "*.py", "test_*.js")
    - Searching by filename only (e.g., "README.md" finds all README files)
    - Checking if specific files exist in the project
    - Getting file lists for further analysis

    Pattern matching:
    - Supports both full path and filename-only matching
    - Uses standard glob patterns (*, ?, [])
    - Fast lookup using in-memory file index
    - Uses forward slashes consistently across all platforms
    - Automatically applies lenient search strategies (recursive, case-insensitive)

    Args:
        pattern: Glob pattern to match files (e.g., "*.py", "test_*.js", "README.md")

    Returns:
        Formatted string with file list and match quality information
    """
    search_result = FileDiscoveryService(ctx).find_files(pattern)
    return _format_file_search_result(search_result)


def _format_file_search_result(search_result) -> str:
    """
    Format FileSearchResult as a user-friendly string.
    
    Args:
        search_result: FileSearchResult from the service layer
        
    Returns:
        Formatted string with match information and file list
    """
    files = search_result.files
    
    if not files:
        return f"No files found matching pattern '{search_result.original_pattern}'."
    
    # Build the message based on match type
    message_parts = []
    
    if search_result.match_type == "exact":
        message_parts.append(f"Found {len(files)} file(s) matching '{search_result.original_pattern}':")
    elif search_result.match_type == "recursive":
        message_parts.append(
            f"Exact match for '{search_result.original_pattern}' did not yield any results. "
            f"But found {len(files)} file(s) through a recursive search (pattern: '{search_result.applied_pattern}'):"
        )
    elif search_result.match_type == "case_insensitive_root":
        message_parts.append(
            f"Exact match for '{search_result.original_pattern}' did not yield any results. "
            f"But found {len(files)} file(s) through a case-insensitive search:"
        )
    elif search_result.match_type == "case_insensitive_recursive":
        message_parts.append(
            f"Exact match for '{search_result.original_pattern}' did not yield any results. "
            f"But found {len(files)} file(s) through a case-insensitive recursive search (pattern: '{search_result.applied_pattern}'):"
        )
    elif search_result.match_type == "all":
        message_parts.append(f"All {len(files)} files in the project:")
    else:
        message_parts.append(f"Found {len(files)} file(s):")
    
    # Add file list
    message_parts.append("\n".join(files))
    
    return "\n".join(message_parts)

@mcp.tool()
@handle_mcp_tool_errors(return_type='dict')
def get_file_summary(file_path: str, ctx: Context) -> Dict[str, Any]:
    """
    Get a summary of a specific file, including:
    - Line count
    - Function/class definitions (for supported languages)
    - Import statements
    - Basic complexity metrics
    """
    return CodeIntelligenceService(ctx).analyze_file(file_path)

@mcp.tool()
@handle_mcp_tool_errors(return_type='str')
def refresh_index(ctx: Context) -> str:
    """
    Manually refresh the project index when files have been added/removed/moved.

    Use when:
    - File watcher is disabled or unavailable
    - After large-scale operations (git checkout, merge, pull) that change many files
    - When you want immediate index rebuild without waiting for file watcher debounce
    - When find_files results seem incomplete or outdated
    - For troubleshooting suspected index synchronization issues

    Important notes for LLMs:
    - Always available as backup when file watcher is not working
    - Performs full project re-indexing for complete accuracy
    - Use when you suspect the index is stale after file system changes
    - **Call this after programmatic file modifications if file watcher seems unresponsive**
    - Complements the automatic file watcher system

    Returns:
        Success message with total file count
    """
    return IndexManagementService(ctx).rebuild_index()

@mcp.tool()
@handle_mcp_tool_errors(return_type='str')
def build_deep_index(ctx: Context) -> str:
    """
    Build the deep index (full symbol extraction) for the current project.

    This performs a complete re-index and loads it into memory.
    """
    return IndexManagementService(ctx).rebuild_deep_index()

@mcp.tool()
@handle_mcp_tool_errors(return_type='dict')
def get_settings_info(ctx: Context) -> Dict[str, Any]:
    """Get information about the project settings."""
    return SettingsService(ctx).get_settings_info()

@mcp.tool()
@handle_mcp_tool_errors(return_type='dict')
def create_temp_directory() -> Dict[str, Any]:
    """Create the temporary directory used for storing index data."""
    return manage_temp_directory('create')

@mcp.tool()
@handle_mcp_tool_errors(return_type='dict')
def check_temp_directory() -> Dict[str, Any]:
    """Check the temporary directory used for storing index data."""
    return manage_temp_directory('check')

@mcp.tool()
@handle_mcp_tool_errors(return_type='str')
def clear_settings(ctx: Context) -> str:
    """Clear all settings and cached data."""
    return SettingsService(ctx).clear_all_settings()

@mcp.tool()
@handle_mcp_tool_errors(return_type='str')
def refresh_search_tools(ctx: Context) -> str:
    """
    Manually re-detect the available command-line search tools on the system.
    This is useful if you have installed a new tool (like ripgrep) after starting the server.
    """
    return SearchService(ctx).refresh_search_tools()

@mcp.tool()
@handle_mcp_tool_errors(return_type='dict')
def get_file_watcher_status(ctx: Context) -> Dict[str, Any]:
    """Get file watcher service status and statistics."""
    return SystemManagementService(ctx).get_file_watcher_status()

@mcp.tool()
@handle_mcp_tool_errors(return_type='str')
def configure_file_watcher(
    ctx: Context,
    enabled: bool = None,
    debounce_seconds: float = None,
    additional_exclude_patterns: list = None
) -> str:
    """Configure file watcher service settings."""
    return SystemManagementService(ctx).configure_file_watcher(enabled, debounce_seconds, additional_exclude_patterns)

# ----- PROMPTS -----
# Removed: analyze_code, code_search, set_project prompts

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the MCP server."""
    parser = argparse.ArgumentParser(description="Code Index MCP server")
    parser.add_argument(
        "--project-path",
        dest="project_path",
        help="Set the project path on startup (equivalent to calling set_project_path)."
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Transport protocol to use (default: stdio)."
    )
    parser.add_argument(
        "--mount-path",
        dest="mount_path",
        default=None,
        help="Mount path when using SSE transport."
    )
    parser.add_argument(
        "--host",
        dest="host",
        default="localhost",
        help="Host to bind when using streamable-http transport."
    )
    parser.add_argument(
        "--port",
        dest="port",
        type=int,
        default=8000,
        help="Port to bind when using streamable-http transport."
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None):
    """Main function to run the MCP server."""
    args = _parse_args(argv)

    # Store CLI configuration for lifespan bootstrap.
    _CLI_CONFIG.project_path = args.project_path

    run_kwargs = {"transport": args.transport}
    if args.transport == "sse" and args.mount_path:
        run_signature = inspect.signature(mcp.run)
        if "mount_path" in run_signature.parameters:
            run_kwargs["mount_path"] = args.mount_path
        else:
            logger.warning(
                "Ignoring --mount-path because this FastMCP version "
                "does not accept the parameter."
            )

    if args.transport == "streamable-http":
        mcp.settings.host = args.host
        mcp.settings.port = args.port

    try:
        mcp.run(**run_kwargs)
    except RuntimeError as exc:
        logger.error("MCP server terminated with error: %s", exc)
        raise SystemExit(1) from exc
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Unexpected MCP server error: %s", exc)
        raise

if __name__ == '__main__':
    main()
