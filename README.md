# Code Index MCP

<div align="center">

[![MCP Server](https://img.shields.io/badge/MCP-Server-blue)](https://modelcontextprotocol.io)
[![Python](https://img.shields.io/badge/Python-3.8%2B-green)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

A Model Context Protocol server for code indexing, searching, and analysis.

</div>

<a href="https://glama.ai/mcp/servers/@johnhuang316/code-index-mcp">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@johnhuang316/code-index-mcp/badge" alt="code-index-mcp MCP server" />
</a>

## What is Code Index MCP?

Code Index MCP is a specialized MCP server that provides intelligent code indexing and analysis capabilities. It enables Large Language Models to interact with your code repositories, offering real-time insights and navigation through complex codebases.

This server integrates with the [Model Context Protocol](https://modelcontextprotocol.io) (MCP), a standardized way for AI models to interact with external tools and data sources.

## Key Features

- **Project Indexing**: Recursively scans directories to build a searchable index of code files
- **Advanced Search**: Intelligent search with automatic detection of ugrep, ripgrep, ag, or grep for enhanced performance
- **Fuzzy Search**: Native fuzzy matching with ugrep, or safe fuzzy patterns for other tools
- **File Analysis**: Get detailed insights about file structure, imports, and complexity
- **Smart Filtering**: Automatically ignores build directories, dependencies, and non-code files
- **Persistent Storage**: Caches indexes for improved performance across sessions
- **Lazy Loading**: Search tools are detected only when needed for optimal startup performance

## Supported File Types

The server supports multiple programming languages and file extensions including:

- Python (.py)
- JavaScript/TypeScript (.js, .ts, .jsx, .tsx, .mjs, .cjs)
- Frontend Frameworks (.vue, .svelte, .astro)
- Java (.java)
- C/C++ (.c, .cpp, .h, .hpp)
- C# (.cs)
- Go (.go)
- Ruby (.rb)
- PHP (.php)
- Swift (.swift)
- Kotlin (.kt)
- Rust (.rs)
- Scala (.scala)
- Shell scripts (.sh, .bash)
- Zig (.zig)
- Web files (.html, .css, .scss, .less, .sass, .stylus, .styl)
- Template engines (.hbs, .handlebars, .ejs, .pug)
- **Database & SQL**:
  - SQL files (.sql, .ddl, .dml)
  - Database-specific (.mysql, .postgresql, .psql, .sqlite, .mssql, .oracle, .ora, .db2)
  - Database objects (.proc, .procedure, .func, .function, .view, .trigger, .index)
  - Migration & tools (.migration, .seed, .fixture, .schema, .liquibase, .flyway)
  - NoSQL & modern (.cql, .cypher, .sparql, .gql)
- Documentation/Config (.md, .mdx, .json, .xml, .yml, .yaml)

## Setup and Integration

There are several ways to set up and use Code Index MCP, depending on your needs.

### For General Use with Host Applications (Recommended)

This is the easiest and most common way to use the server. It's designed for users who want to use Code Index MCP within an AI application like Claude Desktop.

1.  **Prerequisite**: Make sure you have Python 3.8+ and [uv](https://github.com/astral-sh/uv) installed.

2.  **Configure the Host App**: Add the following to your host application's MCP configuration file.
    
    *Claude Desktop*  ->  `claude_desktop_config.json` 

    *Claude Code* -> `~/.claude.json`.  There is one `mcpServers` for each project and one global 

    ```json
    {
      "mcpServers": {
        "code-index": {
          "command": "uvx",
          "args": [
            "code-index-mcp"
          ]
        }
      }
    }
    ```

4.  **Restart the Host App**: After adding the configuration, restart the application. The `uvx` command will automatically handle the installation and execution of the `code-index-mcp` server in the background.

### For Local Development

If you want to contribute to the development of this project, follow these steps:

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/johnhuang316/code-index-mcp.git
    cd code-index-mcp
    ```

2.  **Install dependencies** using `uv`:
    ```bash
    uv sync
    ```

3.  **Configure Your Host App for Local Development**: To make your host application (e.g., Claude Desktop) use your local source code, update its configuration file to execute the server via `uv run`. This ensures any changes you make to the code are reflected immediately when the host app starts the server.

    ```json
    {
      "mcpServers": {
        "code-index": {
          "command": "uv",
          "args": [
            "run",
            "code_index_mcp"
          ]
        }
      }
    }
    ```

4.  **Debug with the MCP Inspector**: To debug your local server, you also need to tell the inspector to use `uv run`.
    ```bash
    npx @modelcontextprotocol/inspector uv run code_index_mcp
    ```

### Manual Installation via pip (Alternative)

If you prefer to manage your Python packages manually with `pip`, you can install the server directly.

1.  **Install the package**:
    ```bash
    pip install code-index-mcp
    ```

2.  **Configure the Host App**: You will need to manually update your host application's MCP configuration to point to the installed script. Replace `"command": "uvx"` with `"command": "code-index-mcp"`.

    ```json
    {
      "mcpServers": {
        "code-index": {
          "command": "code-index-mcp",
          "args": []
        }
      }
    }
    ```

## Available Tools

### Core Tools

- **set_project_path**: Sets the base project path for indexing.
- **search_code**: Enhanced search using external tools (ugrep/ripgrep/ag/grep) with fuzzy matching support.
- **find_files**: Finds files in the project matching a given pattern.
- **get_file_summary**: Gets a summary of a specific file, including line count, functions, imports, etc.
- **refresh_index**: Refreshes the project index.
- **get_settings_info**: Gets information about the project settings.

### Utility Tools

- **create_temp_directory**: Creates the temporary directory used for storing index data.
- **check_temp_directory**: Checks the temporary directory used for storing index data.
- **clear_settings**: Clears all settings and cached data.
- **refresh_search_tools**: Manually re-detect available command-line search tools (e.g., ripgrep).

## Common Workflows and Examples

Here’s a typical workflow for using Code Index MCP with an AI assistant like Claude.

### 1. Set Project Path & Initial Indexing

This is the first and most important step. When you set the project path, the server automatically creates a file index for the first time or loads a previously cached one.

**Example Prompt:**
```
Please set the project path to C:\Users\username\projects\my-react-app
```

### 2. Refresh the Index (When Needed)

If you make significant changes to your project files after the initial setup, you can manually refresh the index to ensure all tools are working with the latest information.

**Example Prompt:**
```
I've just added a few new components, please refresh the project index.
```
*(The assistant would use the `refresh_index` tool)*

### 3. Explore the Project Structure

Once the index is ready, you can find files using patterns (globs) to understand the codebase and locate relevant files.

**Example Prompt:**
```
Find all TypeScript component files in the 'src/components' directory.
```
*(The assistant would use the `find_files` tool with a pattern like `src/components/**/*.tsx`)*

### 4. Analyze a Specific File

Before diving into the full content of a file, you can get a quick summary of its structure, including functions, classes, and imports.

**Example Prompt:**
```
Can you give me a summary of the 'src/api/userService.ts' file?
```
*(The assistant would use the `get_file_summary` tool)*

### 5. Search for Code

With an up-to-date index, you can search for code snippets, function names, or any text pattern to find where specific logic is implemented.

**Example: Simple Search**
```
Search for all occurrences of the "processData" function.
```

**Example: Search with Fuzzy Matching**
```
I'm looking for a function related to user authentication, it might be named 'authUser', 'authenticateUser', or something similar. Can you do a fuzzy search for 'authUser'?
```

**Example: Search within Specific Files**
```
Search for the string "API_ENDPOINT" only in Python files.
```
*(The assistant would use the `search_code` tool with the `file_pattern` parameter set to `*.py`)*

## Development

### Building from Source

1. Clone the repository:

```bash
git clone https://github.com/username/code-index-mcp.git
cd code-index-mcp
```

2. Install dependencies:

```bash
uv sync
```

3. Run the server locally:

```bash
uv run code_index_mcp
```

## Debugging

You can use the MCP inspector to debug the server:

```bash
npx @modelcontextprotocol/inspector uvx code-index-mcp
```

## License

[MIT License](LICENSE)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Languages

- [繁體中文](README_zh.md)
