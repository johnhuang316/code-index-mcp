"""
Code Index MCP Server

This MCP server allows LLMs to index, search, and analyze code from a project directory.
It provides tools for file discovery, content retrieval, and code analysis.

This version uses a service-oriented architecture where MCP decorators delegate
to domain-specific services for business logic.
"""
# Standard library imports
import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator, Dict, Any

# Third-party imports
from mcp import types
from mcp.server.fastmcp import FastMCP, Context

# Local imports
from .project_settings import ProjectSettings
from .services import (
    ProjectService, IndexService, SearchService,
    FileService, SettingsService, FileWatcherService
)
from .services.settings_service import manage_temp_directory
from .utils import (
    handle_mcp_resource_errors, handle_mcp_tool_errors
)

@dataclass
class CodeIndexerContext:
    """Context for the Code Indexer MCP server."""
    base_path: str
    settings: ProjectSettings
    file_count: int = 0
    file_index: dict = field(default_factory=dict)
    index_cache: dict = field(default_factory=dict)
    file_watcher_service: FileWatcherService = None

@asynccontextmanager
async def indexer_lifespan(_server: FastMCP) -> AsyncIterator[CodeIndexerContext]:
    """Manage the lifecycle of the Code Indexer MCP server."""
    # Don't set a default path, user must explicitly set project path
    base_path = ""  # Empty string to indicate no path is set

    print("Initializing Code Indexer MCP server...")

    # Initialize settings manager with skip_load=True to skip loading files
    settings = ProjectSettings(base_path, skip_load=True)

    # Initialize context - file watcher will be initialized later when project path is set
    context = CodeIndexerContext(
        base_path=base_path,
        settings=settings,
        file_watcher_service=None
    )

    try:
        print("Server ready. Waiting for user to set project path...")
        # Provide context to the server
        yield context
    finally:
        # Stop file watcher if it was started
        if context.file_watcher_service:
            print("Stopping file watcher service...")
            context.file_watcher_service.stop_monitoring()

        # Only save index if project path has been set
        if context.base_path and context.index_cache:
            print(f"Saving index for project: {context.base_path}")
            settings.save_index(context.index_cache)

# Create the MCP server with lifespan manager
mcp = FastMCP("CodeIndexer", lifespan=indexer_lifespan, dependencies=["pathlib"])

# ----- RESOURCES -----

@mcp.resource("config://code-indexer")
@handle_mcp_resource_errors
def get_config() -> str:
    """Get the current configuration of the Code Indexer."""
    ctx = mcp.get_context()
    return ProjectService(ctx).get_project_config()

@mcp.resource("files://{file_path}")
@handle_mcp_resource_errors
def get_file_content(file_path: str) -> str:
    """Get the content of a specific file."""
    ctx = mcp.get_context()
    return FileService(ctx).get_file_content(file_path)

@mcp.resource("structure://project")
@handle_mcp_resource_errors
def get_project_structure() -> str:
    """Get the structure of the project as a JSON tree."""
    ctx = mcp.get_context()
    return ProjectService(ctx).get_project_structure()

@mcp.resource("settings://stats")
@handle_mcp_resource_errors
def get_settings_stats() -> str:
    """Get statistics about the settings directory and files."""
    ctx = mcp.get_context()
    return SettingsService(ctx).get_settings_stats()

# ----- TOOLS -----

@mcp.tool()
@handle_mcp_tool_errors(return_type='str')
def set_project_path(path: str, ctx: Context) -> str:
    """Set the base project path for indexing."""
    return ProjectService(ctx).initialize_project(path)

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
    max_line_length: int = 200
) -> Dict[str, Any]:
    """
    Search for a code pattern in the project using an advanced, fast tool.

    This tool automatically selects the best available command-line search tool
    (like ugrep, ripgrep, ag, or grep) for maximum performance.

    Args:
        pattern: The search pattern. Can be literal text or regex (see regex parameter).
        case_sensitive: Whether the search should be case-sensitive.
        context_lines: Number of lines to show before and after the match.
        file_pattern: A glob pattern to filter files to search in
                     (e.g., "*.py", "*.js", "test_*.py").
        max_line_length: Optional. Default 200. Limits the length of lines when context_lines is used.
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

    Returns:
        A dictionary containing the search results or an error message.

    """
    return SearchService(ctx).search_code(
        pattern=pattern,
        case_sensitive=case_sensitive,
        context_lines=context_lines,
        file_pattern=file_pattern,
        fuzzy=fuzzy,
        regex=regex,
        max_line_length=max_line_length
    )

@mcp.tool()
@handle_mcp_tool_errors(return_type='dict')
def find_files(pattern: str, ctx: Context) -> Dict[str, Any]:
    """
    Find files matching a glob pattern using efficient directory tree traversal.

    Use when:
    - Looking for files by pattern (e.g., "*.py", "test_*.js", "src/**/*.ts")
    - Searching by filename only (e.g., "README.md" finds all README files)
    - Checking if specific files exist in the project
    - Getting file lists for further analysis

    Pattern matching:
    - Supports both full path and filename-only matching
    - Uses forward slashes consistently across all platforms
    - Efficient directory tree traversal for better performance

    Args:
        pattern: Glob pattern to match files (e.g., "*.py", "test_*.js", "README.md")

    Returns:
        Dictionary with files list and status information
    """
    return IndexService(ctx).find_files_by_pattern(pattern)

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
    return FileService(ctx).analyze_file(file_path)

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
    return IndexService(ctx).rebuild_index()

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
    try:
        # Check for file watcher errors first
        file_watcher_error = None
        if hasattr(ctx.request_context.lifespan_context, 'file_watcher_error'):
            file_watcher_error = ctx.request_context.lifespan_context.file_watcher_error

        # Get file watcher service from context
        file_watcher_service = None
        if hasattr(ctx.request_context.lifespan_context, 'file_watcher_service'):
            file_watcher_service = ctx.request_context.lifespan_context.file_watcher_service

        # If there's an error, return error status with recommendation
        if file_watcher_error:
            status = {
                "available": True,
                "active": False,
                "error": file_watcher_error,
                "recommendation": "Use refresh_index tool for manual updates",
                "manual_refresh_required": True
            }

            # Add basic configuration if available
            if hasattr(ctx.request_context.lifespan_context, 'settings') and ctx.request_context.lifespan_context.settings:
                file_watcher_config = ctx.request_context.lifespan_context.settings.get_file_watcher_config()
                status["configuration"] = file_watcher_config

            return status

        # If no service and no error, it's not initialized
        if not file_watcher_service:
            return {
                "available": True,
                "active": False,
                "status": "not_initialized",
                "message": "File watcher service not initialized. Set project path to enable auto-refresh.",
                "recommendation": "Use set_project_path tool to initialize file watcher"
            }

        # Get status from file watcher service
        status = file_watcher_service.get_status()

        # Add index service status
        index_service = IndexService(ctx)
        rebuild_status = index_service.get_rebuild_status()
        status["rebuild_status"] = rebuild_status

        # Add configuration
        if hasattr(ctx.request_context.lifespan_context, 'settings') and ctx.request_context.lifespan_context.settings:
            file_watcher_config = ctx.request_context.lifespan_context.settings.get_file_watcher_config()
            status["configuration"] = file_watcher_config

        return status

    except Exception as e:
        return {"status": "error", "message": f"Failed to get file watcher status: {e}"}

@mcp.tool()
@handle_mcp_tool_errors(return_type='str')
def configure_file_watcher(
    ctx: Context,
    enabled: bool = None,
    debounce_seconds: float = None,
    additional_exclude_patterns: list = None
) -> str:
    """Configure file watcher service settings."""
    try:
        # Get settings from context
        if not hasattr(ctx.request_context.lifespan_context, 'settings') or not ctx.request_context.lifespan_context.settings:
            return "Settings not available - project path not set"

        settings = ctx.request_context.lifespan_context.settings

        # Build updates dictionary
        updates = {}
        if enabled is not None:
            updates["enabled"] = enabled
        if debounce_seconds is not None:
            updates["debounce_seconds"] = debounce_seconds
        if additional_exclude_patterns is not None:
            updates["additional_exclude_patterns"] = additional_exclude_patterns

        if not updates:
            return "No configuration changes specified"

        # Update configuration
        settings.update_file_watcher_config(updates)

        # If file watcher is running, we would need to restart it for changes to take effect
        # For now, just return success message with note about restart
        return f"File watcher configuration updated: {updates}. Restart may be required for changes to take effect."

    except Exception as e:
        return f"Failed to update file watcher configuration: {e}"

# ----- PROMPTS -----

@mcp.prompt()
def analyze_code(file_path: str = "", query: str = "") -> list[types.PromptMessage]:
    """Prompt for analyzing code in the project."""
    messages = [
        types.PromptMessage(role="user", content=types.TextContent(type="text", text=f"""I need you to analyze some code from my project.

{f'Please analyze the file: {file_path}' if file_path else ''}
{f'I want to understand: {query}' if query else ''}

First, let me give you some context about the project structure. Then, I'll provide the code to analyze.
""")),
        types.PromptMessage(
            role="assistant",
            content=types.TextContent(
                type="text",
                text="I'll help you analyze the code. Let me first examine the project structure to get a better understanding of the codebase."
            )
        )
    ]
    return messages

@mcp.prompt()
def code_search(query: str = "") -> types.TextContent:
    """Prompt for searching code in the project."""
    search_text = "\"query\"" if not query else f"\"{query}\""
    return types.TextContent(
        type="text",
        text=f"""I need to search through my codebase for {search_text}.

Please help me find all occurrences of this query and explain what each match means in its context.
Focus on the most relevant files and provide a brief explanation of how each match is used in the code.

If there are too many results, prioritize the most important ones and summarize the patterns you see."""
    )

@mcp.prompt()
def set_project() -> list[types.PromptMessage]:
    """Prompt for setting the project path."""
    messages = [
        types.PromptMessage(role="user", content=types.TextContent(type="text", text="""
        I need to analyze code from a project, but I haven't set the project path yet. Please help me set up the project path and index the code.

        First, I need to specify which project directory to analyze.
        """)),
        types.PromptMessage(role="assistant", content=types.TextContent(type="text", text="""
        Before I can help you analyze any code, we need to set up the project path. This is a required first step.

        Please provide the full path to your project folder. For example:
        - Windows: "C:/Users/username/projects/my-project"
        - macOS/Linux: "/home/username/projects/my-project"

        Once you provide the path, I'll use the `set_project_path` tool to configure the code analyzer to work with your project.
        """))
    ]
    return messages

def main():
    """Main function to run the MCP server."""
    mcp.run()

if __name__ == '__main__':
    main()
