---
name: verify-multilang-support
description: Instructs the Agent to verify the code-index-mcp server's multi-language support by sequentially using MCP tools on sample projects.
---

# Verify Multi-Language Support

## Overview
As an Agent, your goal is to verify that the `code-index-mcp` server can correctly index and search code across different programming languages. You will use the **MCP Tools** available to you (`set_project_path`, `refresh_index`, `search_code_advanced`, `get_file_summary`) to interact with the sample projects located in `test/sample-projects`.

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
        - Treat the query as a **literal search** unless the table explicitly says otherwise.
        - The goal is to verify realistic symbol discovery, not broad keyword coincidence.
    
    d.  **Deep Summary Check**: Call `mcp_code-index_get_file_summary` for the **Preferred File**.
        - *Goal*: Verify that the summary JSON includes the expected symbol in the `functions`, `classes`, or `methods` list.
        - *Pass Criteria*: The **Expected Symbol** must appear in the summary output, either directly or as part of a qualified symbol name.
        - **Deterministic Fallback Order**:
          1. If the preferred file path is wrong or missing, use the first code file returned by search.
          2. If the summary is empty/trivial, use the first non-trivial code file from the search results.
          3. If the language commonly splits declaration/implementation (for example Objective-C `.h`/`.m`), use the header for search verification and the implementation file for summary verification.
    
    e.  **Full Text Check**: If the summary check is ambiguous or fails, read the actual file content.
        - *Goal*: Visually confirm that the symbol (e.g., `class UserManager`) is present in the code and is NOT commented out.
    
    f.  **Check Results**:
        - Track results by phase:
          - `SEARCH`: PASS/FAIL
          - `SUMMARY`: PASS/FAIL/AMBIGUOUS
          - `MANUAL_CHECK`: YES/NO
          - `FINAL`: PASS/FAIL/EXPECTED_EMPTY
        - If the search returns results AND the file summary (or manual check) confirms the symbol, mark the language as **PASS**.
        - If the project is intentionally empty, mark it as **EXPECTED_EMPTY** instead of FAIL.
        - Otherwise, mark it as **FAIL**.

3.  **Behavior Smoke Checks**:
    - After the language verification loop, run at least one literal-mode smoke check using a regex-like string (for example `get.*Data` with `regex=False` or omitted) and confirm it is treated literally.
    - If the current environment advertises native regex support, run one explicit regex smoke check with `regex=True` and confirm it behaves as regex.
    - Record any mismatch separately from the language PASS/FAIL table.

4.  **Reporting**:
    - After checking all languages, generate a summary report of PASS/FAIL status.
    - Include the phase-level status (`SEARCH`, `SUMMARY`, `MANUAL_CHECK`, `FINAL`) for any non-trivial or ambiguous case.

## Verification Targets

| Language | Relative Path | Verification Query | Expected Symbol | Preferred File |
| :--- | :--- | :--- | :--- | :--- |
| **Python** | `python` | `class UserManager` | `UserManager` | `user_management/services/user_manager.py` |
| **Go** | `go/user-management` | `UserService` | `UserService` | `internal/services/user_service.go` |
| **Java** | `java/user-management` | `class UserManager` | `UserManager` | `src/main/java/com/example/usermanagement/services/UserManager.java` |
| **JavaScript** | `javascript/user-management` | `class UserService` | `UserService` | `src/services/UserService.js` |
| **TypeScript** | `typescript` | `interface PersonInterface` | `PersonInterface` | `sample.ts` |
| **C#** | `csharp/orders` | `class OrderService` | `OrderService` | `src/Orders/Services/OrderService.cs` |
| **Kotlin** | `kotlin/notes-api` | `class NotesService` | `NotesService` | `src/main/kotlin/com/example/notes/NotesService.kt` |
| **Objective-C**| `objective-c` | `interface UserManager` | `UserManager` | `UserManager.h` (search), `UserManager.m` (summary fallback) |
| **Zig** | `zig/code-index-example` | `fn main` | `main` | `src/main.zig` |
| **Dart** | `dart` | `void main` | `main` | *(Expect `EXPECTED_EMPTY` - empty sample project)* |

## Tips
- Use `set_project_path` carefully; it requires an absolute path. Start by finding the absolute path of `test/sample-projects`.
- Prefer specific symbol queries over broad terms like `function` or `class` when the project structure allows it.
- If a search fails, first confirm the sample project's real relative path and preferred file path before broadening the query.
- If summary extraction is weak for a declaration file, use the implementation file before falling back to manual file reading.
