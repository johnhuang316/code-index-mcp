#!/usr/bin/env python
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def find_git_root(start: Path) -> Path | None:
    for parent in [start, *start.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)


def read_version(path: Path, pattern: str) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1) if match else None


def main() -> int:
    root = find_git_root(Path.cwd())
    if not root:
        print("No git repository found from the current working directory.")
        return 1

    print(f"Repo: {root}")

    status = run(["git", "status", "--porcelain"], root)
    if status.returncode == 0:
        if status.stdout.strip():
            print("Git status: DIRTY")
            print(status.stdout.strip())
        else:
            print("Git status: clean")
    else:
        print("Git status: unavailable")
        if status.stderr.strip():
            print(status.stderr.strip())

    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], root)
    if branch.returncode == 0:
        print(f"Branch: {branch.stdout.strip()}")

    prev_tag = None
    tag = run(["git", "describe", "--tags", "--match", "v*", "--abbrev=0"], root)
    if tag.returncode == 0 and tag.stdout.strip():
        prev_tag = tag.stdout.strip()
        print(f"Latest tag: {prev_tag}")
    else:
        print("Latest tag: not found")

    if prev_tag:
        log = run(["git", "log", "--oneline", f"{prev_tag}..HEAD", "-n", "20"], root)
        if log.returncode == 0 and log.stdout.strip():
            print("Recent changes since latest tag (max 20):")
            print(log.stdout.rstrip())
        else:
            print("No commits since latest tag.")

    print("Version files:")
    version_files = [
        ("pyproject.toml", r'^\s*version\s*=\s*"([^"]+)"'),
        ("src/code_index_mcp/__init__.py", r'__version__\s*=\s*"([^"]+)"'),
        ("uv.lock", None),
    ]
    for rel_path, pattern in version_files:
        path = root / rel_path
        if not path.exists():
            print(f"- {rel_path}: MISSING")
            continue
        if pattern:
            version = read_version(path, pattern)
            version_note = f" (version: {version})" if version else " (version: ?)"
        else:
            version_note = ""
        print(f"- {rel_path}: OK{version_note}")

    print("Next: run `uv run pytest` and update version files if needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
