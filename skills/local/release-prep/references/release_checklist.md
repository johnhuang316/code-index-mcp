# Release Checklist (code-index-mcp)

## Checklist

- Clean working tree:

```bash
git status
```

- Review changes since last tag:

```bash
git fetch --tags
PREV=$(git describe --tags --match 'v*' --abbrev=0)
git log ${PREV}..HEAD --oneline
git diff ${PREV}..HEAD --stat
```

- Run tests:

```bash
uv run pytest
```

- Verify version-only diff:

```bash
git diff --stat
```

- Commit release bump:

```bash
git add pyproject.toml src/code_index_mcp/__init__.py uv.lock
git commit -m "chore(release): vX.Y.Z"
```

- Tag and push:

```bash
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin <branch>
git push origin vX.Y.Z
```

- Create GitHub release:

```bash
gh release create vX.Y.Z --title "Release vX.Y.Z" --notes "..."
```
