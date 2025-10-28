from pathlib import Path

from code_index_mcp.indexing.sqlite_index_manager import SQLiteIndexManager


def test_javascript_user_service_called_by():
    sample_project = (
        Path(__file__).resolve().parents[2]
        / "test"
        / "sample-projects"
        / "javascript"
        / "user-management"
    )
    assert sample_project.exists()

    manager = SQLiteIndexManager()
    assert manager.set_project_path(str(sample_project))
    assert manager.build_index()
    assert manager.load_index()

    summary = manager.get_file_summary("src/services/UserService.js")
    assert summary is not None

    method_calls = {info["name"]: info["called_by"] for info in summary["methods"]}

    expected_calls = {
        "UserService.createUser": ["src/routes/userRoutes.js:106"],
        "UserService.authenticateUser": ["src/routes/userRoutes.js:116"],
        "UserService.getAllUsers": ["src/routes/userRoutes.js:139"],
        "UserService.searchUsers": ["src/routes/userRoutes.js:148"],
        "UserService.getUserStats": ["src/routes/userRoutes.js:156"],
        "UserService.exportUsers": ["src/routes/userRoutes.js:164"],
        "UserService.getActiveUsers": ["src/routes/userRoutes.js:172"],
        "UserService.getUsersByRole": ["src/routes/userRoutes.js:181"],
        "UserService.getUserById": ["src/routes/userRoutes.js:189"],
        "UserService.getUserActivity": ["src/routes/userRoutes.js:197"],
        "UserService.updateUser": ["src/routes/userRoutes.js:205"],
        "UserService.changePassword": ["src/routes/userRoutes.js:215"],
        "UserService.resetPassword": ["src/routes/userRoutes.js:225"],
        "UserService.addPermission": ["src/routes/userRoutes.js:235"],
        "UserService.removePermission": ["src/routes/userRoutes.js:245"],
        "UserService.deleteUser": ["src/routes/userRoutes.js:254"],
        "UserService.hardDeleteUser": ["src/routes/userRoutes.js:263"],
    }

    for method_name, callers in expected_calls.items():
        assert method_calls.get(method_name) == callers

    assert method_calls.get("UserService.getUserByUsername") == []
    assert method_calls.get("UserService.getUserByEmail") == []

    auth_summary = manager.get_file_summary("src/middleware/auth.js")
    assert auth_summary is not None

    auth_functions = {info["name"]: info["called_by"] for info in auth_summary["functions"]}

    expected_auth_callers = [
        "src/routes/userRoutes.js:124",
        "src/routes/userRoutes.js:146",
        "src/routes/userRoutes.js:155",
        "src/routes/userRoutes.js:163",
        "src/routes/userRoutes.js:171",
        "src/routes/userRoutes.js:179",
        "src/routes/userRoutes.js:188",
        "src/routes/userRoutes.js:196",
        "src/routes/userRoutes.js:204",
        "src/routes/userRoutes.js:213",
        "src/routes/userRoutes.js:223",
        "src/routes/userRoutes.js:233",
        "src/routes/userRoutes.js:243",
        "src/routes/userRoutes.js:253",
        "src/routes/userRoutes.js:262",
    ]

    assert sorted(auth_functions.get("auth", [])) == expected_auth_callers
    assert auth_functions.get("authorize") == [
        "src/middleware/auth.js:120",
        "src/middleware/auth.js:126",
    ]
    assert auth_functions.get("requirePermission") == []
    assert auth_functions.get("selfOrAdmin") == []
    assert auth_functions.get("optionalAuth") == []
