---
name: release-prep
description: Prepare a release for this repository when the user says "release". Use to run the release checklist, pick the semver bump, run tests, update version files, tag, push, and draft the GitHub release for code-index-mcp.
---

# Release Prep

## Overview

Follow the code-index-mcp release checklist with the correct version files, tests,
tags, and GitHub release steps. Use the helper script for quick repo status and
the reference checklist for exact commands and file locations.

## Workflow

1. Confirm the target version, branch, and test scope (full vs. -k).
2. Run `scripts/run_release_checks.py` and review the output.
3. Run tests: `uv run pytest` (use `-k` if agreed).
4. Review changes since the last tag and choose the semver bump.
5. Update version files: `pyproject.toml`, `src/code_index_mcp/__init__.py`,
   `uv.lock`.
6. Ensure the diff only touches the three version files.
7. Commit with Conventional Commits (e.g., `chore(release): vX.Y.Z`).
8. Tag, push branch + tag, and create the GitHub release.
9. Follow up on CI/deploy jobs and required smoke tests.

## Resources

### scripts/
- `scripts/run_release_checks.py` for repo status, latest tag, and version file
  presence before editing versions.

### references/
- `references/release_checklist.md` for the exact steps, commands, and files.
