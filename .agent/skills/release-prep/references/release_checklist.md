# Release Checklist (code-index-mcp)

## Checklist

- Verify clean working tree and correct branch:

```bash
git status
git branch --show-current
```

- Stop if `git status` is not clean or if you are not on the intended release branch.

- Review changes since last tag:

```bash
git fetch --tags
PREV=$(git describe --tags --match 'v*' --abbrev=0)
git log ${PREV}..HEAD --oneline
git diff ${PREV}..HEAD --stat
```

- Choose semver bump:
  - `patch`: bug fixes / user-visible corrections
  - `minor`: backward-compatible features
  - `major`: breaking changes / migration-required release

- Run full test suite (pytest is not in project deps, install it first):

```bash
uv pip install pytest
uv run python -m pytest tests/
```

- Update versions and lockfile (all four files must stay in sync):

```bash
# edit pyproject.toml                       -> version = "X.Y.Z"
# edit src/code_index_mcp/__init__.py       -> __version__ = "X.Y.Z"
# edit .well-known/mcp.llmfeed.json         -> "version": "X.Y.Z"
uv lock
```

- Verify release-only diff:

```bash
git diff --stat
```

- Expected: only release-related files change. If other files appear, explain and review them before commit.

- Commit release bump:

```bash
git add pyproject.toml src/code_index_mcp/__init__.py uv.lock .well-known/mcp.llmfeed.json
git commit -m "chore(release): vX.Y.Z"
```

- Confirm tag does not already exist:

```bash
git rev-parse "vX.Y.Z" 2>/dev/null
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

- Verify published release and remote tag:

```bash
gh release view vX.Y.Z
git ls-remote --tags origin vX.Y.Z
git rev-list -n 1 vX.Y.Z
```

- Follow up on CI / publish jobs as needed.
