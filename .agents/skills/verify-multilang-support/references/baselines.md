# Multi-Language Summary Baselines

Compare every listed field with the actual `get_file_summary` output. A language
passes only when every required value is present.

## Python — `user_management/cli.py`

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
  cli: ["user_management/cli.py::main"]
  create_user: ["user_management/cli.py::create_user"]
expected_imports:
  - click
  - json
  - typing.Optional
  - services.user_manager.UserManager
  - services.auth_service.AuthService
```

## Go — `internal/services/user_service.go`

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

## Java — `src/main/java/com/example/usermanagement/services/UserManager.java`

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

## JavaScript — `src/services/UserService.js`

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

## TypeScript — `src/services/UserService.ts`

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

## C# — `src/Orders/Services/OrderService.cs`

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

## Kotlin — `src/main/kotlin/com/example/notes/NotesService.kt`

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

## Rust — `src/conversation.rs`

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

## Objective-C — `UserManager.m`

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

## Zig — `src/main.zig`

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
