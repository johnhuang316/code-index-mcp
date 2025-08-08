# Code Index MCP

<div align="center">

[![MCP Server](https://img.shields.io/badge/MCP-Server-blue)](https://modelcontextprotocol.io)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

**Intelligent code indexing and analysis for Large Language Models**

Transform how AI understands your codebase with advanced search, analysis, and navigation capabilities.

</div>

<a href="https://glama.ai/mcp/servers/@johnhuang316/code-index-mcp">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@johnhuang316/code-index-mcp/badge" alt="code-index-mcp MCP server" />
</a>

## Table of Contents

- [Code Index MCP](#code-index-mcp)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
  - [Key Features](#key-features)
    - [🔍 **Intelligent Search \& Analysis**](#-intelligent-search--analysis)
    - [🗂️ **Multi-Language Support**](#️-multi-language-support)
    - [⚡ **Real-time Monitoring \& Auto-refresh**](#-real-time-monitoring--auto-refresh)
    - [⚡ **Performance \& Efficiency**](#-performance--efficiency)
  - [Supported File Types](#supported-file-types)
  - [Quick Start](#quick-start)
    - [🚀 **Recommended Setup (Most Users)**](#-recommended-setup-most-users)
    - [🛠️ **Development Setup**](#️-development-setup)
  - [Available Tools](#available-tools)
    - [🏗️ **Project Management**](#️-project-management)
    - [🔍 **Search \& Discovery**](#-search--discovery)
    - [🔄 **Monitoring \& Auto-refresh**](#-monitoring--auto-refresh)
    - [🛠️ **System \& Maintenance**](#️-system--maintenance)
  - [Usage Examples](#usage-examples)
    - [🎯 **Quick Start Workflow**](#-quick-start-workflow)
    - [🔍 **Advanced Search Examples**](#-advanced-search-examples)
  - [Troubleshooting](#troubleshooting)
    - [🔄 **Auto-refresh Not Working**](#-auto-refresh-not-working)
  - [Development \& Contributing](#development--contributing)
    - [🔧 **Building from Source**](#-building-from-source)
    - [🐛 **Debugging**](#-debugging)
    - [🤝 **Contributing**](#-contributing)
    - [📜 **License**](#-license)
    - [🌐 **Translations**](#-translations)

## Overview

Code Index MCP is a [Model Context Protocol](https://modelcontextprotocol.io) server that bridges the gap between AI models and complex codebases. It provides intelligent indexing, advanced search capabilities, and detailed code analysis to help AI assistants understand and navigate your projects effectively.

**Perfect for:** Code review, refactoring, documentation generation, debugging assistance, and architectural analysis.



## Key Features

### 🔍 **Intelligent Search & Analysis**

- **Advanced Search**: Auto-detects and uses the best available tool (ugrep, ripgrep, ag, or grep)
- **Regex Support**: Full regex pattern matching with ReDoS attack prevention
- **Fuzzy Search**: True fuzzy matching with edit distance (ugrep) or word boundary patterns
- **File Analysis**: Deep insights into structure, imports, classes, methods, and complexity metrics

### 🗂️ **Multi-Language Support**

- **Mainstream Languages**: Java, Python, JavaScript/TypeScript, C/C++, Go, Rust, C#
- **Mobile Development**: Swift, Kotlin, Objective-C/C++, React Native
- **Web Frontend**: Vue, React, Svelte, Astro, HTML, CSS, SCSS
- **Database**: SQL (MySQL, PostgreSQL, SQLite), NoSQL, stored procedures, migrations
- **Scripting**: Ruby, PHP, Shell, PowerShell, Bash
- **Systems**: C/C++, Rust, Go, Zig
- **JVM Ecosystem**: Java, Kotlin, Scala, Groovy
- **Others**: Lua, Perl, R, MATLAB, configuration files
- **50+ File Types Total** - [View feature support](#supported-file-types)

### ⚡ **Real-time Monitoring & Auto-refresh**

- **File Watcher**: Automatic index updates when files change
- **Cross-platform**: Native OS file system monitoring (inotify, FSEvents, ReadDirectoryChangesW)
- **Smart Debouncing**: Batches rapid changes to prevent excessive rebuilds (default: 6 seconds)
- **Thread-safe**: Non-blocking background operations with ThreadPoolExecutor

### ⚡ **Performance & Efficiency**

- **Smart Indexing**: Recursively scans with intelligent filtering of build directories
- **Persistent Caching**: Stores indexes for lightning-fast subsequent access
- **Lazy Loading**: Tools detected only when needed for optimal startup
- **Memory Efficient**: Intelligent caching strategies for large codebases

## Supported File Types

The following truth table details the features extracted for various file types based on the analyzers in the `src/code_index_mcp/indexing/analyzers/` directory.


| Feature / File Type  | Python |     JS/TS     | Java | Go |  C  | C++ | C# | Objective-C | Other Types<sup>1</sup> |
| :--------------------- | :------: | :--------------: | :----: | :---: | :---: | :---: | :---: | :-----------: | :-----------------------: |
| **Functions**        |   ✅   |       ✅       |  ✅  | ✅ | ✅ | ✅ | ✅ |     ✅     |           ✅           |
| **Classes**          |   ✅   |       ✅       |  ✅  | ✅ | ✅ | ✅ | ✅ |     ✅     |           ✅           |
| **Methods**          |   ✅   |       ✅       |  ✅  | ✅ | ✅ | ✅ | ✅ |     ✅     |           ✅           |
| **Imports**          |   ✅   |       ✅       |  ✅  | ✅ | ✅ | ✅ | ✅ |     ✅     |           ✅           |
| **Parameters**       |   ✅   |       ✅       |  ✅  | ✅ | ✅ | ✅ | ✅ |     ✅     |    ⚠️<sup>2</sup>    |
| **Line Numbers**     |   ✅   |       ✅       |  ✅  | ✅ | ✅ | ✅ | ✅ |     ✅     |    ⚠️<sup>3</sup>    |
| **Return Types**     |   ✅   |       ✅       |  ✅  | ✅ | ✅ | ✅ | ✅ |     ✅     |           ❌           |
| **Decorators**       |   ✅   | ❌<sup>4</sup> | N/A | N/A | N/A | N/A | N/A |     N/A     |           ❌           |
| **Async Functions**  |   ✅   |       ✅       |  ✅  | ✅ | N/A | N/A | ✅ |     N/A     |    ⚠️<sup>2</sup>    |
| **Inheritance**      |   ✅   |       ✅       |  ✅  | ✅ | ✅ | ✅ | ✅ |     ✅     |    ⚠️<sup>2</sup>    |
| **Properties**       |  N/A  |      N/A      | N/A | N/A | N/A | N/A | ✅ |     ✅     |           ❌           |
| **Interfaces**       |   ✅   |       ✅       |  ✅  | ✅ | N/A | ✅ | ✅ |     ✅     |    ⚠️<sup>2</sup>    |
| **Structs**          |   ✅   |      N/A      | N/A | ✅ | ✅ | ✅ | ✅ |     N/A     |    ⚠️<sup>2</sup>    |
| **Global Variables** |   ✅   |      N/A      |  ✅  | ✅ | ✅ | ✅ | ✅ |     N/A     |    ⚠️<sup>2</sup>    |
| **Includes**         |  N/A  |      N/A      | N/A | N/A | ✅ | ✅ | N/A |     N/A     |    ⚠️<sup>2</sup>    |
| **Exports**          |  N/A  |       ✅       | N/A | N/A | N/A | N/A | ✅ |     N/A     |           ❌           |
| **File Metrics**     |   ✅   |       ✅       |  ✅  | ✅ | ✅ | ✅ | ✅ |     ✅     |           ✅           |

**Notes:**
<sup>1</sup> "All Other Supported Types" refers to extensions in `SUPPORTED_EXTENSIONS` (e.g., `.rb`, `.php`, `.swift`, `.kt`, `.rs`, `.sh`, `.html`, `.css`, `.md`, `.json`, `.vue`, `.sql`, etc.) analyzed by the `GenericAnalyzer`.
<sup>2</sup> `GenericAnalyzer` provides basic support for these features using regex patterns. Accuracy and level of detail may vary.
<sup>3</sup> `GenericAnalyzer` provides estimated line numbers, often based on heuristics which may not always be precise.
<sup>4</sup> The language concept exists or is similar, but the current analyzer does not extract this feature.

<details>
<summary><strong>📖 Detailed Feature Descriptions</strong></summary>

- **Functions:** Extraction of function definitions, including name and parameters.
- **Classes:** Extraction of class definitions, including name.
- **Methods:** Extraction of method definitions, typically within classes.
- **Imports:** Extraction of import/include statements for modules/libraries.
- **Parameters:** Extraction of function/method parameter names and types (where available).
- **Line Numbers:** Identification of the start and end lines for extracted elements.
- **Return Types:** Extraction of return type hints or signatures for functions/methods.
- **Decorators:** Extraction of decorators (Python) or similar annotations.
- **Async Functions:** Identification of asynchronous functions (e.g., `async def`, `async function`).
- **Inheritance:** Identification of base classes or interfaces.
- **Properties:** Extraction of property definitions (common in C#, Objective-C, some Python).
- **Interfaces:** Extraction of interface definitions.
- **Structs:** Extraction of structure definitions (common in C, C++, Go, Swift).
- **Global Variables:** Extraction of global variable declarations.
- **Includes:** Extraction of `#include` (C/C++) or similar preprocessor directives.
- **Exports:** Extraction of export statements (e.g., ES6 modules, C#).
- **File Metrics:** Basic statistics like line count, character count, comment detection, indentation style.

**Analyzer Types:**

- **Dedicated Analyzers (✅):** Languages like Python, JavaScript/TypeScript, Java, Go, C, C++, C#, and Objective-C have specialized analyzers (`PythonAnalyzer`, `JavaScriptAnalyzer`, etc.) that provide accurate and detailed feature extraction.
- **Generic Analyzer (⚠️):** All other supported file types are analyzed by `GenericAnalyzer`, which uses common regex patterns. This provides a baseline level of analysis but may be less accurate or detailed than dedicated analyzers.

</details>

<details>
<summary><strong>🔧 How to Interpret the Table</strong></summary>

- **✅ (Full Support):** The feature is reliably and accurately extracted by the dedicated analyzer for that language.
- **⚠️ (Basic/Partial Support):** The feature is attempted by the `GenericAnalyzer` using regex. It may work for common patterns but could miss complex syntax, language-specific nuances, or provide less precise information (e.g., estimated line numbers).
- **❌ (Analyzer Not Supported):** The language concept exists or is similar, but the current analyzer does not extract this feature.
- **N/A (Not Applicable):** The feature is not applicable to this language.

</details>

## Quick Start

### 🚀 **Recommended Setup (Most Users)**

The easiest way to get started with any MCP-compatible application:

**Prerequisites:** Python 3.10+ and [uv](https://github.com/astral-sh/uv)

1. **Add to your MCP configuration** (e.g., `claude_desktop_config.json` or `~/.claude.json`):

   ```json
   {
     "mcpServers": {
       "code-index": {
         "command": "uvx",
         "args": ["code-index-mcp"]
       }
     }
   }
   ```
2. **Restart your application** – `uvx` automatically handles installation and execution

### 🛠️ **Development Setup**

For contributing or local development:

1. **Clone and install:**

   ```bash
   git clone https://github.com/johnhuang316/code-index-mcp.git
   cd code-index-mcp
   uv sync
   ```
2. **Configure for local development:**

   ```json
   {
     "mcpServers": {
       "code-index": {
         "command": "uv",
         "args": ["run", "code-index-mcp"]
       }
     }
   }
   ```
3. **Debug with MCP Inspector:**

   ```bash
   npx @modelcontextprotocol/inspector uv run code-index-mcp
   ```

<details>
<summary><strong>Alternative: Manual pip Installation</strong></summary>

If you prefer traditional pip management:

```bash
pip install code-index-mcp
```

Then configure:

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

</details>

## Available Tools

### 🏗️ **Project Management**


| Tool                    | Description                                   |
| ------------------------- | ----------------------------------------------- |
| **`set_project_path`**  | Initialize indexing for a project directory   |
| **`refresh_index`**     | Rebuild the project index after file changes  |
| **`get_settings_info`** | View current project configuration and status |

### 🔍 **Search & Discovery**


| Tool                       | Description                                                 |
| ---------------------------- | ------------------------------------------------------------- |
| **`search_code_advanced`** | Smart search with regex, fuzzy matching, and file filtering |
| **`find_files`**           | Locate files using glob patterns (e.g.,`**/*.py`)           |
| **`get_file_summary`**     | Analyze file structure, functions, imports, and complexity  |

### 🔄 **Monitoring & Auto-refresh**


| Tool                          | Description                                        |
| ------------------------------- | ---------------------------------------------------- |
| **`get_file_watcher_status`** | Check file watcher status and configuration        |
| **`configure_file_watcher`**  | Enable/disable auto-refresh and configure settings |

### 🛠️ **System & Maintenance**


| Tool                        | Description                                             |
| ----------------------------- | --------------------------------------------------------- |
| **`create_temp_directory`** | Set up storage directory for index data                 |
| **`check_temp_directory`**  | Verify index storage location and permissions           |
| **`clear_settings`**        | Reset all cached data and configurations                |
| **`refresh_search_tools`**  | Re-detect available search tools (ugrep, ripgrep, etc.) |

## Usage Examples

### 🎯 **Quick Start Workflow**

**1. Initialize Your Project**

```
Set the project path to /Users/dev/my-react-app
```

*Automatically indexes your codebase and creates searchable cache*

**2. Explore Project Structure**

```
Find all TypeScript component files in src/components
```

*Uses: `find_files` with pattern `src/components/**/*.tsx`*

**3. Analyze Key Files**

```
Give me a summary of src/api/userService.ts
```

*Uses: `get_file_summary` to show functions, imports, and complexity*

### 🔍 **Advanced Search Examples**

<details>
<summary><strong>Code Pattern Search</strong></summary>

```
Search for all function calls matching "get.*Data" using regex
```

*Finds: `getData()`, `getUserData()`, `getFormData()`, etc.*

</details>

<details>
<summary><strong>Fuzzy Function Search</strong></summary>

```
Find authentication-related functions with fuzzy search for 'authUser'
```

*Matches: `authenticateUser`, `authUserToken`, `userAuthCheck`, etc.*

</details>

<details>
<summary><strong>Language-Specific Search</strong></summary>

```
Search for "API_ENDPOINT" only in Python files
```

*Uses: `search_code_advanced` with `file_pattern: "*.py"`*

</details>

<details>
<summary><strong>Auto-refresh Configuration</strong></summary>

```
Configure automatic index updates when files change
```

*Uses: `configure_file_watcher` to enable/disable monitoring and set debounce timing*

</details>

<details>
<summary><strong>Project Maintenance</strong></summary>

```
I added new components, please refresh the project index
```

*Uses: `refresh_index` to update the searchable cache*

</details>

## Troubleshooting

### 🔄 **Auto-refresh Not Working**

If automatic index updates aren't working when files change, try:

- `pip install watchdog` (may resolve environment isolation issues)
- Use manual refresh: Call the `refresh_index` tool after making file changes
- Check file watcher status: Use `get_file_watcher_status` to verify monitoring is active

## Development & Contributing

### 🔧 **Building from Source**

```bash
git clone https://github.com/johnhuang316/code-index-mcp.git
cd code-index-mcp
uv sync
uv run code-index-mcp
```

### 🐛 **Debugging**

```bash
npx @modelcontextprotocol/inspector uvx code-index-mcp
```

### 🤝 **Contributing**

Contributions are welcome! Please feel free to submit a Pull Request.

---

### 📜 **License**

[MIT License](LICENSE)

### 🌐 **Translations**

- [繁體中文](README_zh.md)
- [日本語](README_ja.md)
