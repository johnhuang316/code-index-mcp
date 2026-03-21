---
name: verify-multilang-support
description: Use when verifying code-index-mcp multi-language indexing and search behavior against the sample projects under test/sample-projects.
---

# Verify Multi-Language Support

## Overview
As an agent, your goal is to verify that the `code-index-mcp` server can correctly index and search code across different programming languages. Use the MCP tools available in your environment to interact with the sample projects located in `test/sample-projects`.

## Instructions

1. **Preparation**
   - Locate `test/sample-projects`.
   - Iterate through the language-specific sample projects listed below.

2. **Verification Loop**
   For each language, perform these steps sequentially:

   a. **Set Path**
      - Set the project path to the sample project.

   b. **Index**
      - Refresh the shallow index.

   c. **Search & Verify**
      - Run the listed **Verification Query**.
      - Treat the query as a literal search unless the table explicitly says otherwise.
      - Prefer symbol-specific searches over broad keyword matches.

   d. **Deep Summary Check**
      - Run a file summary for the **Preferred File**.
      - Pass when the **Expected Symbol** appears in `functions`, `classes`, or `methods`, either directly or as part of a qualified name.
      - Fallback order:
        1. If the preferred file path is wrong or missing, use the first code file returned by search.
        2. If the summary is empty or trivial, use the first non-trivial code file from the search results.
        3. For split declaration/implementation languages like Objective-C, use the header for search confirmation and the implementation file for summary confirmation.

   e. **Manual File Check**
      - If summary output is ambiguous, read the file content and confirm the symbol is present and not commented out.

   f. **Record Status**
      - Track:
        - `SEARCH`: PASS/FAIL
        - `SUMMARY`: PASS/FAIL/AMBIGUOUS
        - `MANUAL_CHECK`: YES/NO
        - `FINAL`: PASS/FAIL/EXPECTED_EMPTY
      - Mark intentionally empty sample projects as `EXPECTED_EMPTY` instead of `FAIL`.

3. **Behavior Smoke Checks**
   - After the language loop, run at least one literal-mode smoke check with a regex-like string such as `get.*Data` and confirm it remains literal when regex mode is omitted or disabled.
   - If native regex support is available, run one explicit regex smoke check and confirm it behaves as regex.
   - Report these separately from the language table.

4. **Reporting**
   - Summarize each language with its phase-level statuses.
   - Call out any manual fallback or environment-dependent regex behavior.

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
| **Objective-C** | `objective-c` | `interface UserManager` | `UserManager` | `UserManager.h` (search), `UserManager.m` (summary fallback) |
| **Zig** | `zig/code-index-example` | `fn main` | `main` | `src/main.zig` |
| **Dart** | `dart` | `void main` | `main` | *(Expect `EXPECTED_EMPTY` - empty sample project)* |

## Tips
- Confirm the sample project's real relative path before assuming the table is current.
- If declaration files have weak symbol extraction, try the implementation file before concluding failure.
- Broad keyword searches are weaker evidence than symbol-specific searches.
