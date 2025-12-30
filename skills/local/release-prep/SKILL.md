---
name: release-prep
description: Prepare a release for this repository when the user says "release". Use to review changes since the last release, choose and confirm the semver bump, run tests, update version files, tag, push, and draft the GitHub release for code-index-mcp.
---

# Release Prep

## Overview

Follow the code-index-mcp release checklist and use the helper script for quick
repo status. Keep this file focused on the high-level workflow; the checklist
contains the exact commands.

## Workflow

1. Run `scripts/run_release_checks.py` and review the output.
2. Review changes since the last tag, decide the semver bump, and confirm the
   target version + branch with the user.
3. Confirm test scope (full vs. -k) and run: `uv run pytest`.
4. Update version files: `pyproject.toml`, `src/code_index_mcp/__init__.py`,
   `uv.lock`.
5. Ensure the diff only touches the three version files.
6. Commit with Conventional Commits (e.g., `chore(release): vX.Y.Z`).
7. Draft release notes focused only on functional changes (exclude technical-only
   modifications) and confirm the notes with the user before creating the GitHub
   release.
8. Tag, push branch + tag, and create the GitHub release.
9. Follow up on CI/deploy jobs.

## Resources

### scripts/
- `scripts/run_release_checks.py` for repo status, latest tag, and version file
  presence before editing versions.

### references/
- `references/release_checklist.md` for the exact steps, commands, and files.
