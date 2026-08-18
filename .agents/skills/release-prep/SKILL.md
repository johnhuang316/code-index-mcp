---
name: release-prep
description: Use when code-index-mcp implementation is complete and a version bump, release notes, tag, package publication, or GitHub release is being prepared.
---

# Release Prep

## Overview

Prepare code-index-mcp releases from a verified commit with an explicit version and
release target. The reference checklist owns exact commands; this file owns the
decision points and safety gates.

## When to Use

- Implementation is complete and ready for a versioned release.
- The user requests a semver recommendation, version bump, release notes, tag, or
  GitHub release.
- A release candidate needs a final repository and test check.

Do not use during ordinary implementation or when the user has excluded release
work.

## Required Gates

- Stop on a dirty working tree or an unintended branch.
- Confirm the target version and release branch with the user before editing.
- Confirm release notes before creating a tag or GitHub release.
- Treat pushes, tags, package publication, and GitHub releases as separate external
  actions requiring user authorization.

## Workflow

1. From the repository root, run
   `uv run python .agents/skills/release-prep/scripts/run_release_checks.py`;
   resolve every failed precondition.
2. Review changes since the latest `v*` tag and recommend:
   - `patch`: bug fixes or user-visible corrections without new surface area
   - `minor`: backward-compatible features or capability expansions
   - `major`: breaking API/behavior changes or migration-required releases
3. After confirmation, run the full test suite using the checklist command.
4. Update all four release artifacts:
   `pyproject.toml`, `src/code_index_mcp/__init__.py`,
   `.well-known/mcp.llmfeed.json`, and `uv.lock`.
   Regenerate `uv.lock`; never hand-edit it.
5. Review a release-only diff and rerun the preflight checks.
6. Commit with `chore(release): vX.Y.Z`.
7. Draft user-facing release notes and obtain confirmation.
8. Only when authorized, create the annotated tag, push the branch and tag, and
   create the GitHub release.
9. Verify the remote tag, release, and related CI or publication jobs.

## Resources

| Resource | Use |
|---|---|
| `scripts/run_release_checks.py` | Check repository state, latest tag, and version files; invoke it with the command above. |
| `references/release_checklist.md` | Follow the exact commands and file checklist, resolving paths relative to this skill directory. |

## Common Mistakes

- Choosing a version from commit count instead of user-visible compatibility.
- Updating only three of the four release artifacts.
- Including unrelated changes in the release commit.
- Treating a local tag as proof that the release was published.
