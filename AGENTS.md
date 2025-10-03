# Repository Guidelines

## Project Structure & Module Organization
Code Index MCP lives in `src/code_index_mcp/`, with `indexing/` managing builders, `services/` exposing MCP tool implementations, `search/` coordinating query utilities, and `utils/` housing cross-cutting helpers. The lightweight CLI bootstrapper is `run.py`, which adds `src/` to `PYTHONPATH` before invoking `code_index_mcp.server`. Sample corpora for language regression reside under `test/sample-projects/` (for example `python/user_management/`). Reserve `tests/` for runnable suites and avoid checking in generated `__pycache__` artifacts.

## Build, Test, and Development Commands
Install dependencies with `uv sync` after cloning. Use `uv run code-index-mcp` to launch the MCP server directly, or `uv run python run.py` when you need the local sys.path shim. During development, `uv run code-index-mcp --help` will list available CLI flags, and `uv run python -m code_index_mcp.server` mirrors the published entry point for debugging.

## Coding Style & Naming Conventions
Target Python 3.10+ and follow the `.pylintrc` configuration: 4-space indentation, 100-character line limit, and restrained function signatures (<= 7 parameters). Modules and functions stay `snake_case`, classes use `PascalCase`, and constants remain uppercase with underscores. Prefer explicit imports from sibling packages (`from .services import ...`) and keep logging to stderr as implemented in `server.py`.

## Testing Guidelines
Automated tests should live under `tests/`, mirroring the package hierarchy (`tests/indexing/test_shallow_index.py`, etc.). Use `uv run pytest` (with optional `-k` selectors) for unit and integration coverage, and stage representative fixtures inside `test/sample-projects/` when exercising new language strategies. Document expected behaviors in fixtures' README files or inline comments, and fail fast if tree-sitter support is not available for a language you add.

## Commit & Pull Request Guidelines
Follow the Conventional Commits style seen in history (`feat`, `fix`, `refactor(scope): summary`). Reference issue numbers when relevant and keep subjects under 72 characters. Pull requests should include: 1) a concise problem statement, 2) before/after behavior or performance notes, 3) instructions for reproducing test runs (`uv run pytest`, `uv run code-index-mcp`). Attach updated screenshots or logs when touching developer experience flows, and confirm the file watcher still transitions to "active" in manual smoke tests.

## Agent Workflow Tips
Always call `set_project_path` before invoking other tools, and prefer `search_code_advanced` with targeted `file_pattern` filters to minimize noise. When editing indexing strategies, run `refresh_index` in between changes to confirm cache rebuilds. Clean up temporary directories via `clear_settings` if you notice stale metadata, and document any new tooling you introduce in this guide.

## Release Preparation Checklist
- Update the project version everywhere it lives: `pyproject.toml`, `src/code_index_mcp/__init__.py`, and `uv.lock`.
- Add a release note entry to `RELEASE_NOTE.txt` for the new version.
- Commit the version bump (plus any release artifacts) and push the branch to `origin`.
- Create a git tag for the new version and push the tag to `origin`.
