---
name: verify-multilang-support
description: Use when validating code-index-mcp language strategies, tree-sitter symbol extraction, called_by or import baselines, or sample projects under test/sample-projects after parser and indexing changes.
---

# Verify Multi-Language Support

## Overview

Verify search and deep indexing for every supported sample language. Non-empty
results are insufficient; summaries must match maintained baselines.

## When to Use

- A language strategy, tree-sitter query, symbol range, indexer, or sample changes.
- Search, summaries, symbol bodies, imports, or `called_by` may have regressed.

Run focused unit tests first when a specific failing strategy is known.

## Verification Loop

Use each row in **Targets**, resolving paths below `test/sample-projects`.

1. Call `set_project_path` with the sample project's absolute path.
2. Call `refresh_index`, then `build_deep_index`.
3. Run the query with `search_code_advanced` in literal mode.
4. Call `get_file_summary` for the preferred file, then read
   [the baselines](references/baselines.md) and compare:
   - exact `language`
   - `symbol_count` at or above the minimum
   - every expected function, method, class, import, and `called_by` relationship
5. Call `get_symbol_body`; require `status: success` and non-empty `code`.
6. Record `SEARCH`, `SUMMARY`, `SYMBOL_BODY`, and `FINAL`. Any failed assertion makes
   the language FAIL.

After the final target, restore `set_project_path` to the repository root and call
`refresh_index`.

## Targets

| Language | Relative path | Literal query | Expected symbol | Preferred file |
|---|---|---|---|---|
| Python | `python` | `class UserManager` | `cli` | `user_management/cli.py` |
| Go | `go/user-management` | `UserService` | `CreateUser` | `internal/services/user_service.go` |
| Java | `java/user-management` | `class UserManager` | `UserManager.createUser` | `src/main/java/com/example/usermanagement/services/UserManager.java` |
| JavaScript | `javascript/user-management` | `class UserService` | `UserService.createUser` | `src/services/UserService.js` |
| TypeScript | `typescript/user-management` | `class UserService` | `user` | `src/services/UserService.ts` |
| C# | `csharp/orders` | `class OrderService` | `Orders.Services.OrderService.Create` | `src/Orders/Services/OrderService.cs` |
| Kotlin | `kotlin/notes-api` | `class NotesService` | `NotesService.createNote` | `src/main/kotlin/com/example/notes/NotesService.kt` |
| Rust | `rust/conversation` | `struct Conversation` | `Conversation.append` | `src/conversation.rs` |
| Objective-C | `objective-c` | `interface UserManager` | `UserManager.addUser` | `UserManager.m` |
| Zig | `zig/code-index-example` | `fn main` | `main` | `src/main.zig` |

## Behavior Smoke Checks

After the language loop:

- Search `get.*Data` with regex disabled and confirm literal behavior.
- If regex is available, repeat with it enabled and confirm regex behavior.

Report these separately from the language table.

## Failure Triage

Report the failed check and actual versus expected value, then read the sample:

- If the sample legitimately changed, update `references/baselines.md`.
- Otherwise, treat it as an indexer or language-strategy regression.

Do not weaken or delete a baseline merely to make verification pass.

## Common Mistakes

- Using a stale or cross-project file path.
- Skipping deep indexing before inspecting summaries.
- Treating one search hit as full language support.
- Forgetting that Objective-C files sit directly under `objective-c/`.
- Leaving the MCP server pointed at a sample project after verification.
