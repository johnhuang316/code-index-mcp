---
name: release-prep
description: Use when preparing a versioned release for code-index-mcp after implementation is complete and you need to choose a semver bump, update release version files, tag, and publish a GitHub release.
---

# Release Prep

## Overview

Follow the code-index-mcp release checklist and use the helper script for quick repo status. Keep this file focused on the high-level workflow; the checklist contains the exact commands.

Release work is gated: do not start the bump/tag flow from a dirty tree or the wrong branch.

## Workflow

1. Run `scripts/run_release_checks.py` and review the output.
2. Stop immediately if the working tree is not clean or if the current branch is not the intended release branch. Resolve that first.
3. Review changes since the last tag and decide the semver bump using these rules:
   - `patch`: bug fixes or user-visible corrections without new surface area
   - `minor`: backward-compatible features or capability expansions
   - `major`: breaking API/behavior changes or migration-required releases
4. Confirm the target version and release branch with the user.
5. Run the full test suite: `uv run pytest`.
6. Update version files: `pyproject.toml`, `src/code_index_mcp/__init__.py`, `uv.lock`.
   - Regenerate `uv.lock` with the normal project workflow; do not hand-edit it.
7. Ensure the staged diff only touches release-related files. If anything else is present, explain why before committing.
8. Commit with Conventional Commits (e.g., `chore(release): vX.Y.Z`).
9. Draft release notes from the changes since the last tag. Focus on user-visible functional changes, note any breaking changes explicitly, and exclude purely technical-only housekeeping unless users need to know.
10. Confirm the release notes with the user before creating the GitHub release.
11. Create the annotated tag, push the release branch + tag, and create the GitHub release.
12. Verify the release exists remotely and follow up on CI/deploy jobs.

## Resources

### scripts/
- `scripts/run_release_checks.py` for repo status, latest tag, and version file presence before editing versions.

### references/
- `references/release_checklist.md` for the exact steps, commands, and files.
