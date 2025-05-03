[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/johnhuang316-code-index-mcp-badge.png)](https://mseep.ai/app/johnhuang316-code-index-mcp)

# Code Index MCP

<div align="center">

[![MCP Server](https://img.shields.io/badge/MCP-Server-blue)](https://modelcontextprotocol.io)
[![Python](https://img.shields.io/badge/Python-3.8%2B-green)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

A Model Context Protocol server for code indexing, searching, and analysis.

</div>

## What is Code Index MCP?

Code Index MCP is a specialized MCP server that provides intelligent code indexing and analysis capabilities. It enables Large Language Models to interact with your code repositories, offering real-time insights and navigation through complex codebases.

This server integrates with the [Model Context Protocol](https://modelcontextprotocol.io) (MCP), a standardized way for AI models to interact with external tools and data sources.

## Key Features

- **Project Indexing**: Recursively scans directories to build a searchable index of code files
- **Code Search**: Find patterns, function definitions, and references across your codebase
- **File Analysis**: Get detailed insights about file structure, imports, and complexity
- **Smart Filtering**: Automatically ignores build directories, dependencies, and non-code files
- **Persistent Storage**: Caches indexes for improved performance across sessions

## Supported File Types

The server supports multiple programming languages and file extensions including:

- Python (.py)
- JavaScript/TypeScript (.js, .ts, .jsx, .tsx)
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
- Web files (.html, .css, .scss)
- Documentation/Config (.md, .json, .xml, .yml, .yaml)

## Installation

### Prerequisites

- Python 3.8 or higher
- [uv](https://github.com/astral-sh/uv) package manager (recommended)

### Using uvx (recommended)

The easiest way to install and use code-index-mcp is with uvx:

```bash
uvx code-index-mcp
```

### Using pip

Alternatively, you can install via pip:

```bash
pip install code-index-mcp
```

After installation, you can run it as a module:

```bash
python -m code_index_mcp
```

## Integration with Claude Desktop

Add this to your Claude settings (`~/Library/Application Support/Claude/claude_desktop_config.json`):

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

After adding the configuration, restart Claude Desktop and the Code Index MCP tools will be available.

## Available Tools

### Core Tools

- **set_project_path**: Sets the base project path for indexing.
- **search_code**: Searches for code matches within the indexed files.
- **find_files**: Finds files in the project matching a given pattern.
- **get_file_summary**: Gets a summary of a specific file, including line count, functions, imports, etc.
- **refresh_index**: Refreshes the project index.
- **get_settings_info**: Gets information about the project settings.

### Utility Tools

- **create_temp_directory**: Creates the temporary directory used for storing index data.
- **check_temp_directory**: Checks the temporary directory used for storing index data.
- **clear_settings**: Clears all settings and cached data.

## Example Usage with Claude

Here are some examples of how to use Code Index MCP with Claude:

### Setting a Project Path

```
Please set the project path to C:\Users\username\projects\my-python-project
```

### Searching for Code Patterns

```
Search the code for all occurrences of "def process_data" in Python files
```

### Getting a File Summary

```
Give me a summary of the main.py file in the project
```

### Finding All Files of a Certain Type

```
Find all JavaScript files in the project
```

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
