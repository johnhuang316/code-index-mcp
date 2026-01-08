---
name: verify-multilang-support
description: Instructs the Agent to verify the code-index-mcp server's multi-language support by sequentially using MCP tools on sample projects.
---

# Verify Multi-Language Support

## Overview
As an Agent, your goal is to verify that the `code-index-mcp` server can correctly index and search code across different programming languages. You will use the **MCP Tools** available to you (`set_project_path`, `refresh_index`, `search_code_advanced`) to interact with the sample projects located in `test/sample-projects`.

## Instructions

1.  **Preparation**:
    - Locate the `test/sample-projects` directory.
    - Understand that you will need to iterate through specific subdirectories.

2.  **Verification Loop**:
    For each language listed in the **Verification Targets** table below, perform the following steps **sequentially**:
    
    a.  **Set Path**: Call `mcp_code-index_set_project_path` with the absolute path to the language's sample project.
        - *Example*: `.../test/sample-projects/python`
    
    b.  **Index**: Call `mcp_code-index_refresh_index` to ensure the files are parsed.
    
    c.  **Search & Verify**: Call `mcp_code-index_search_code_advanced` using the **Verification Query** from the table.
    
    d.  **Deep Summary Check**: Call `mcp_code-index_get_file_summary` for the **Expected File Match**.
        - *Goal*: Verify that the summary JSON includes the expected symbols (classes/functions) in the `functions` or `classes` list.
        - *Pass Criteria*: The **Verification Query** symbol name must appear in the summary output.
        - **Smart Fallback**: If the summary implies the file is trivial (e.g., no symbols found), **select another non-trivial file** from the project (using `list_dir` to find larger files) and repeat the summary check on that new file.
    
    e.  **Full Text Check**: If the summary check is ambiguous or fails, call `view_file` to read the actual file content.
        - *Goal*: Visually confirm that the symbol (e.g., `class UserManager`) is present in the code and is NOT commented out.
    
    f.  **Check Results**:
        - If the search returns results AND the file summary (or manual check) confirms the symbol, mark as **PASS**.
        - Otherwise, mark as **FAIL**.

3.  **Reporting**:
    - After checking all languages, generate a summary report of PASS/FAIL status.

## Verification Targets

| Language | Relative Path | Verification Query | Expected File Match |
| :--- | :--- | :--- | :--- |
| **Python** | `python` | `class UserManager` | `UserManager.py` |
| **Go** | `go` | `UserService` | `user_service.go` |
| **Java** | `java/user-management` | `class UserManager` | `UserManager.java` |
| **JavaScript** | `javascript/user-management` | `function` | `User.js` |
| **TypeScript** | `typescript` | `interface PersonInterface` | `sample.ts` |
| **C#** | `csharp/orders` | `class OrderService` | `OrderService.cs` |
| **Kotlin** | `kotlin/notes-api` | `class NotesService` | `NotesService.kt` |
| **Objective-C**| `objective-c` | `interface UserManager` | `UserManager.h` or `.m` |
| **Zig** | `zig` | `fn main` | `main.zig` |
| **Dart** | `dart` | `void main` | *(Expect FAIL - Empty Project)* |

## Tips
- Use `set_project_path` carefully; it requires an absolute path. Start by finding the absolute path of `test/sample-projects`.
- If a search fails, try a broader query or check `list_dir` to ensure the file exists.
