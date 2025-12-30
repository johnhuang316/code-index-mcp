# Release Checklist (code-index-mcp)

Use this checklist when preparing a release for this repository.

## Required version files

- `pyproject.toml`
- `src/code_index_mcp/__init__.py`
- `uv.lock`

## Steps

1. Ensure the working tree is clean:

```bash
git status
```

2. Review changes since the last tag and choose the semver bump:

```bash
git fetch --tags
PREV=$(git describe --tags --match 'v*' --abbrev=0)
git log ${PREV}..HEAD --oneline
git diff ${PREV}..HEAD --stat
```

3. Run tests:

```bash
uv run pytest
```

4. Update version files (keep them in sync):

- `pyproject.toml`
- `src/code_index_mcp/__init__.py`
- `uv.lock`

5. Confirm the diff only touches those three files:

```bash
git diff --stat
```

6. Commit the release bump:

```bash
git add pyproject.toml src/code_index_mcp/__init__.py uv.lock
git commit -m "chore(release): vX.Y.Z"
```

7. Tag and push:

```bash
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin <branch>
git push origin vX.Y.Z
```

8. Create the GitHub release (CLI or web UI):

```bash
gh release create vX.Y.Z --title "Release vX.Y.Z" --notes "..."
```

9. Follow up on CI/deploy jobs and any required smoke tests.
