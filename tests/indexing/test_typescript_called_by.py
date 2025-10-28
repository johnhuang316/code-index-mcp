from pathlib import Path

from code_index_mcp.indexing.sqlite_index_manager import SQLiteIndexManager


def test_typescript_rate_limiter_called_by():
    sample_project = (
        Path(__file__).resolve().parents[2]
        / "test"
        / "sample-projects"
        / "typescript"
        / "user-management"
    )
    assert sample_project.exists()

    manager = SQLiteIndexManager()
    assert manager.set_project_path(str(sample_project))
    assert manager.build_index()
    assert manager.load_index()

    summary = manager.get_file_summary("src/middleware/rateLimiter.ts")
    assert summary is not None

    limiter_calls = {info["name"]: info["called_by"] for info in summary["functions"]}

    expected_calls = {
        "generalLimiter": ["src/server.ts:59"],
        "createUserLimiter": ["src/routes/userRoutes.ts:121"],
        "authLimiter": ["src/routes/userRoutes.ts:136"],
        "exportLimiter": ["src/routes/userRoutes.ts:209"],
    }

    for limiter, callers in expected_calls.items():
        assert limiter_calls.get(limiter) == callers

    assert limiter_calls.get("passwordResetLimiter") == []
    assert limiter_calls.get("docsLimiter") == []
    assert limiter_calls.get("createCustomLimiter") == []
