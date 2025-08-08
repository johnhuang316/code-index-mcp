"""
Command-line interface for local testing and debugging of the Code Indexer.

This tool allows for direct interaction with the indexer's services,
bypassing the MCP server layer for rapid, iterative development and testing.
"""

import argparse
import json
import asyncio
import sys
import os
from types import SimpleNamespace
import inspect

# Ensure the src directory is in the Python path
src_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if src_root not in sys.path:
    sys.path.insert(0, src_root)

from code_index_mcp.server import mcp as server, indexer_lifespan
from mcp.server.fastmcp import Context
from code_index_mcp.services import (
    ProjectService, IndexService, SearchService,
    FileService, SettingsService
)
from code_index_mcp.services.settings_service import manage_temp_directory

def get_service_mapping(ctx):
    """Create a mapping from tool names to service methods."""
    # Helper to check if a function is async
    def is_async(func):
        return asyncio.iscoroutinefunction(func) or asyncio.iscoroutinefunction(getattr(func, '__call__', None))

    # Service instances
    project_service = ProjectService(ctx)
    index_service = IndexService(ctx)
    search_service = SearchService(ctx)
    file_service = FileService(ctx)
    settings_service = SettingsService(ctx)

    mapping = {
        "set_project_path": project_service.initialize_project,
        "search_code_advanced": search_service.search_code,
        "find_files": index_service.find_files_by_pattern,
        "get_file_summary": file_service.analyze_file,
        "refresh_index": index_service.rebuild_index,
        "get_settings_info": settings_service.get_settings_info,
        "create_temp_directory": manage_temp_directory,
        "check_temp_directory": manage_temp_directory,
        "clear_settings": settings_service.clear_all_settings,
        "refresh_search_tools": search_service.refresh_search_tools,
        # get_file_watcher_status and configure_file_watcher are more complex and omitted for now
    }
    
    # Add async flag to each method
    return {name: (func, is_async(func)) for name, func in mapping.items()}

def setup_arg_parser():
    """Set up the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="CLI for interacting with the Code Indexer."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 'index' command
    index_parser = subparsers.add_parser(
        "index", help="Run the indexing process for a project."
    )
    index_parser.add_argument(
        "--path", type=str, required=True, help="The project path to index."
    )

    # 'call' command
    call_parser = subparsers.add_parser(
        "call", help="Call a tool method with specified parameters."
    )
    call_parser.add_argument(
        "tool_name", type=str, help="The name of the tool to call."
    )
    call_parser.add_argument(
        "--params",
        type=str,
        default="{}",
        help="A JSON string with the parameters for the tool.",
    )
    call_parser.add_argument(
        "--path",
        type=str,
        default=".",
        help="The project path to use for the tool call.",
    )

    return parser

async def main():
    """Main async function to run the CLI."""
    parser = setup_arg_parser()
    args = parser.parse_args()

    async with indexer_lifespan(server) as lifespan_context:
        mock_request_context = SimpleNamespace(lifespan_context=lifespan_context)
        mcp_context = Context(request_context=mock_request_context)
        service_mapping = get_service_mapping(mcp_context)

        if args.command == "index":
            print(f"Starting indexing for project at: {args.path}")
            tool_name = "set_project_path"
            if tool_name in service_mapping:
                service_method, is_async = service_mapping[tool_name]
                params = {'path': args.path}
                if is_async:
                    response = await service_method(**params)
                else:
                    response = service_method(**params)
                print(response)
                print("Project path set. Indexing complete.")
            else:
                print(f"Error: Tool '{tool_name}' not found.")

        elif args.command == "call":
            # Set the project path first to ensure context is initialized
            set_path_method, is_async_set_path = service_mapping["set_project_path"]
            if is_async_set_path:
                await set_path_method(path=args.path)
            else:
                set_path_method(path=args.path)

            tool_name = args.tool_name
            if tool_name not in service_mapping:
                print(f"Error: Tool '{tool_name}' not found.")
                return

            try:
                params = json.loads(args.params)
            except json.JSONDecodeError:
                print("Error: --params must be a valid JSON string.")
                return

            print(f"Calling tool '{tool_name}' with params: {params}")
            service_method, is_async = service_mapping[tool_name]

            try:
                if is_async:
                    response = await service_method(**params)
                else:
                    response = service_method(**params)
                
                print("\n--- Response ---")
                print(json.dumps(response, indent=2))
                print("----------------\n")

            except Exception as e:
                print(f"\n--- Error ---")
                print(f"An error occurred while calling the tool: {e}")
                print("----------------\n")

if __name__ == "__main__":
    asyncio.run(main())
