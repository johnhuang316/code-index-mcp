---
name: verify-multilang-support
description: Use when verifying code-index-mcp multi-language indexing and search behavior against the sample projects under test/sample-projects.
---

# Verify Multi-Language Support

## Overview
As an agent, your goal is to verify that the `code-index-mcp` server can correctly index, deep-index, and search code across different programming languages. Use the MCP tools available in your environment to interact with the sample projects located in `test/sample-projects`.

**Important**: This is not a "does it return something" test. You must compare the actual `get_file_summary` output against the expected baselines below and flag any discrepancy in language, symbol_count, function/method/class names, called_by relationships, and imports.

## Instructions

1. **Preparation**
   - Locate `test/sample-projects`.
   - Iterate through the language-specific sample projects listed below.

2. **Verification Loop**
   For each language, perform these steps sequentially:

   a. **Set Path**
      - Call `set_project_path` with the absolute path to the sample project.

   b. **Shallow Index**
      - Call `refresh_index` to build the shallow (file-list) index.

   c. **Deep Index**
      - Call `build_deep_index` to run full symbol extraction.

   d. **Search & Verify**
      - Run the listed **Verification Query** using `search_code_advanced`.
      - Treat the query as a literal search unless the table explicitly says otherwise.

   e. **Deep Summary Check — compare against baseline**
      - Call `get_file_summary` for the **Preferred File**.
      - Compare the result against the **Expected Baseline** for that language (see section below).
      - Check ALL of the following:
        1. `language` field matches expected value.
        2. `symbol_count` is >= the expected minimum.
        3. Every name listed in `expected_functions` appears in the `functions` list.
        4. Every name listed in `expected_methods` appears in the `methods` list.
        5. Every name listed in `expected_classes` appears in the `classes` list.
        6. For each entry in `expected_called_by`, verify the named symbol's `called_by` list contains the expected callers.
        7. Every entry in `expected_imports` appears in the `imports` list.
      - Mark PASS only if ALL checks pass. If any single check fails, mark FAIL and record which check failed.

   f. **Symbol Body Check**
      - Call `get_symbol_body` for the **Expected Symbol** in the **Preferred File**.
      - Pass when `status` is `"success"` and `code` is non-empty.

   g. **Record Status**
      - Track per language:
        - `SEARCH`: PASS/FAIL
        - `SUMMARY`: PASS/FAIL (with details on which checks failed)
        - `SYMBOL_BODY`: PASS/FAIL
        - `FINAL`: PASS/FAIL

3. **Behavior Smoke Checks**
   - After the language loop, run at least one literal-mode smoke check with a regex-like string such as `get.*Data` and confirm it remains literal when regex mode is omitted or disabled.
   - If native regex support is available, run one explicit regex smoke check and confirm it behaves as regex.
   - Report these separately from the language table.

4. **Reporting**
   - Summarize each language with its phase-level statuses in a table.
   - For any FAIL, list the specific check that failed and the actual vs expected values.

## Verification Targets

| Language | Relative Path | Verification Query | Expected Symbol | Preferred File |
| :--- | :--- | :--- | :--- | :--- |
| **Python** | `python` | `class UserManager` | `cli` | `cli.py` |
| **Go** | `go/user-management` | `UserService` | `CreateUser` | `internal/services/user_service.go` |
| **Java** | `java/user-management` | `class UserManager` | `UserManager.createUser` | `src/main/java/com/example/usermanagement/services/UserManager.java` |
| **JavaScript** | `javascript/user-management` | `class UserService` | `UserService.createUser` | `src/services/UserService.js` |
| **TypeScript** | `typescript/user-management` | `class UserService` | `user` | `src/services/UserService.ts` |
| **C#** | `csharp/orders` | `class OrderService` | `Orders.Services.OrderService.Create` | `src/Orders/Services/OrderService.cs` |
| **Kotlin** | `kotlin/notes-api` | `class NotesService` | `NotesService.createNote` | `src/main/kotlin/com/example/notes/NotesService.kt` |
| **Rust** | `rust/conversation` | `struct Conversation` | `Conversation.append` | `src/conversation.rs` |
| **Objective-C** | `objective-c` | `interface UserManager` | `UserManager.addUser` | `UserManager.m` |
| **Zig** | `zig/code-index-example` | `fn main` | `main` | `src/main.zig` |

## Expected Baselines

### Python — `cli.py`
```yaml
language: python
symbol_count_min: 11
expected_functions:
  - cli
  - create_user
  - get_user
  - list_users
  - update_user
  - delete_user
  - authenticate
  - stats
  - export
  - search
  - main
expected_methods: []
expected_classes: []
expected_called_by:
  cli: ["cli.py::main"]
  create_user: ["cli.py::create_user"]
expected_imports:
  - click
  - json
  - typing.Optional
  - services.user_manager.UserManager
  - services.auth_service.AuthService
```

### Go — `internal/services/user_service.go`
```yaml
language: go
symbol_count_min: 21
expected_functions:
  - UserService
  - NewUserService
expected_methods:
  - CreateUser
  - GetUserByID
  - GetUserByUsername
  - GetUserByEmail
  - UpdateUser
  - DeleteUser
  - HardDeleteUser
  - GetAllUsers
  - GetActiveUsers
  - GetUsersByRole
  - SearchUsers
  - GetUserStats
  - AuthenticateUser
  - ChangePassword
  - ResetPassword
  - AddPermission
  - RemovePermission
  - ExportUsers
  - GetUserActivity
expected_classes: []
expected_called_by:
  NewUserService: ["internal/services/user_service.go::CreateUser"]  # at least this caller
  GetUserByID:
    - "internal/services/user_service.go::UpdateUser"
    - "internal/services/user_service.go::DeleteUser"
    - "internal/services/user_service.go::ChangePassword"
  GetUserByUsername: ["internal/services/user_service.go::AuthenticateUser"]
  GetAllUsers: ["internal/services/user_service.go::ExportUsers"]
expected_imports:
  - encoding/json
  - errors
  - gorm.io/gorm
```

### Java — `src/main/java/com/example/usermanagement/services/UserManager.java`
```yaml
language: java
symbol_count_min: 25
expected_functions: []
expected_methods:
  - UserManager.createUser
  - UserManager.getUser
  - UserManager.updateUser
  - UserManager.deleteUser
  - UserManager.getAllUsers
  - UserManager.getActiveUsers
  - UserManager.getUsersByRole
  - UserManager.filterUsers
  - UserManager.searchUsers
  - UserManager.getUserStats
  - UserManager.exportUsers
  - UserManager.exportToJson
  - UserManager.exportToCsv
expected_classes:
  - UserManager
expected_called_by:
  UserManager.getUser:
    - "src/main/java/com/example/usermanagement/services/UserManager.java::UserManager.updateUser"
    - "src/main/java/com/example/usermanagement/services/UserManager.java::UserManager.deleteUser"
  UserManager.filterUsers:
    - "src/main/java/com/example/usermanagement/services/UserManager.java::UserManager.getUsersOlderThan"
    - "src/main/java/com/example/usermanagement/services/UserManager.java::UserManager.getUsersWithEmail"
    - "src/main/java/com/example/usermanagement/services/UserManager.java::UserManager.getUsersWithPermission"
  UserManager.getActiveUsers:
    - "src/main/java/com/example/usermanagement/services/UserManager.java::UserManager.getUserStats"
expected_imports:
  - com.example.usermanagement.models.User
  - com.example.usermanagement.models.UserRole
  - java.util.*
```

### JavaScript — `src/services/UserService.js`
```yaml
language: javascript
symbol_count_min: 20
expected_functions: []
expected_methods:
  - UserService.createUser
  - UserService.getUserById
  - UserService.updateUser
  - UserService.deleteUser
  - UserService.hardDeleteUser
  - UserService.getAllUsers
  - UserService.searchUsers
  - UserService.authenticateUser
  - UserService.exportUsers
  - UserService.getUserActivity
expected_classes:
  - UserService
expected_called_by:
  UserService.createUser: ["src/routes/userRoutes.js:106"]
  UserService.getUserById: ["src/routes/userRoutes.js:189"]
  UserService.updateUser: ["src/routes/userRoutes.js:205"]
  UserService.deleteUser: ["src/routes/userRoutes.js:254"]
  UserService.getAllUsers: ["src/routes/userRoutes.js:139"]
expected_imports: []  # JS file has no extracted imports
```

### TypeScript — `src/services/UserService.ts`
```yaml
language: typescript
symbol_count_min: 5
expected_functions:
  - user
  - validationErrors
  - total
  - totalPages
  - token
expected_methods: []
expected_classes: []
expected_called_by:
  user:
    - "src/routes/userRoutes.ts:127"
    - "src/routes/userRoutes.ts:276"
expected_imports_contain:
  - "import { User } from '../models/User'"
  - "import { AppError } from '../utils/errors'"
```

### C# — `src/Orders/Services/OrderService.cs`
```yaml
language: csharp
symbol_count_min: 4
expected_functions:
  - Orders.Services.OrderService.#ctor
expected_methods:
  - Orders.Services.OrderService.Create
  - Orders.Services.OrderService.MarkPaid
expected_classes:
  - Orders.Services.OrderService
expected_called_by:
  Orders.Services.OrderService.#ctor: ["src/Orders/Program.cs::Orders.Program.Main"]
  Orders.Services.OrderService.Create: ["src/Orders/Program.cs::Orders.Program.Main"]
  Orders.Services.OrderService.MarkPaid: ["src/Orders/Program.cs::Orders.Program.Main"]
expected_imports:
  - Orders.Models
  - Orders.Repositories
```

### Kotlin — `src/main/kotlin/com/example/notes/NotesService.kt`
```yaml
language: kotlin
symbol_count_min: 4
expected_functions: []
expected_methods:
  - NotesService.createNote
  - NotesService.find
  - NotesService.publish
expected_classes:
  - NotesService
expected_called_by:
  NotesService.createNote: ["src/main/kotlin/com/example/notes/NotesApp.kt::NotesApp.run"]
  NotesService.find:
    - "src/main/kotlin/com/example/notes/NotesService.kt::NotesService.publish"
  NotesService.publish: ["src/main/kotlin/com/example/notes/NotesApp.kt::NotesApp.run"]
```

### Rust — `src/conversation.rs`
```yaml
language: rust
symbol_count_min: 7
expected_functions:
  - helper
  - run
expected_methods:
  - Conversation.new
  - Conversation.append
expected_classes:
  - Conversation
  - Status
  - Runnable
expected_called_by:
  helper:
    - "src/conversation.rs::run"
    - "src/conversation.rs::Conversation.append"
expected_imports:
  - std::collections::VecDeque
```

### Objective-C — `UserManager.m`
```yaml
language: objective-c
symbol_count_min: 5
expected_functions: []
expected_methods:
  - UserManager.sharedManager
  - UserManager.addUser
  - UserManager.findUserByName
  - UserManager.removeUser
  - UserManager.userCount
expected_classes: []
expected_called_by: {}  # Objective-C currently has no cross-method called_by tracking
expected_imports:
  - UserManager.h
```

### Zig — `src/main.zig`
```yaml
language: zig
symbol_count_min: 2
expected_functions:
  - main
  - testOne
expected_methods: []
expected_classes: []
expected_called_by: {}  # Zig currently has no called_by tracking
expected_imports: []
```

## Tips
- Confirm the sample project's real relative path before assuming the table is current.
- Objective-C does not have a subdirectory — its files sit directly under `test/sample-projects/objective-c/`.
- Python's sample project also has files at the top level (`cli.py`, `__init__.py`).
- If a baseline check fails, read the actual file to determine whether the baseline is stale (sample project changed) or the indexer has a bug. Update the baseline if the sample project legitimately changed.
- When new languages are added, add a baseline section here based on the actual `get_file_summary` output.
