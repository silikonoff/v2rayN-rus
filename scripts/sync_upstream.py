#!/usr/bin/env python3
"""Merge upstream while preserving fork-owned documentation and CI policy."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTECTED = (
    "README.md",
    "docs/ru",
    ".github/workflows",
    "scripts/check_docs.py",
    "scripts/sync_upstream.py",
    "package-debian-x86.sh",
    "package-rhel-x86.sh",
)


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, check=check)


def main() -> int:
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT):
        raise RuntimeError("Working tree must be clean before upstream merge")
    git("fetch", "--no-tags", "https://github.com/2dust/v2rayN.git", "refs/heads/master")
    upstream = subprocess.check_output(
        ["git", "rev-parse", "FETCH_HEAD"], cwd=ROOT, text=True
    ).strip()
    if git("merge-base", "--is-ancestor", upstream, "HEAD", check=False).returncode == 0:
        print("Upstream is already incorporated")
        return 0

    merged = git("merge", "--no-commit", "--no-ff", upstream, check=False)
    if merged.returncode and not (ROOT / ".git" / "MERGE_HEAD").is_file():
        raise RuntimeError("Merge could not start")

    changed = subprocess.check_output(
        ["git", "diff", "--name-only", "-z", "HEAD", "--", *PROTECTED], cwd=ROOT
    ).split(b"\0")
    for raw in changed:
        if not raw:
            continue
        path = raw.decode("utf-8", "surrogateescape")
        exists = git("cat-file", "-e", f"HEAD:{path}", check=False).returncode == 0
        if exists:
            git("restore", "--source=HEAD", "--staged", "--worktree", "--", path)
        else:
            git("rm", "-f", "--ignore-unmatch", "--", path)

    conflicts = subprocess.check_output(
        ["git", "diff", "--name-only", "--diff-filter=U", "-z"], cwd=ROOT
    )
    if conflicts:
        print("Unresolved upstream conflicts; no commit or push performed", file=sys.stderr)
        git("merge", "--abort", check=False)
        return 1
    git("diff", "--cached", "--check")
    git("commit", "-m", f"Merge upstream v2rayN {upstream[:12]}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Upstream sync failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
