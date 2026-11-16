"""Regression checks for upstream merge policy; no application builds."""

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sync_upstream as sync


class SyncPolicyTests(unittest.TestCase):
    def test_import_whitespace_and_preserve_fork(self):
        self.exercise(conflict=False)

    def test_conflict_aborts_without_commit(self):
        self.exercise(conflict=True)

    def exercise(self, conflict):
        scratch = Path(__file__).resolve().parents[1] / ".tmp"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="v2rayn-sync-test-", dir=scratch) as directory:
            root = Path(directory)

            def git(*args, check=True):
                return subprocess.run(
                    ["git", *args], cwd=root, check=check, capture_output=True
                )

            def put(path, content):
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")

            git("init", "--initial-branch=master")
            git("config", "user.name", "Sync test")
            git("config", "user.email", "test@example.invalid")
            git("config", "core.autocrlf", "false")
            put("README.md", "base\n")
            put("source.cs", "base\n")
            git("add", ".")
            git("commit", "-m", "base")
            git("checkout", "-b", "upstream")
            put("README.md", "upstream\n")
            put("source.cs", "upstream with spaces   \n")
            put(".github/workflows/new.yml", "upstream workflow\n")
            put("package-debian-x86.sh", "upstream package\n")
            git("add", ".")
            git("commit", "-m", "upstream")
            git("checkout", "master")
            put("README.md", "Russian documentation\n")
            if conflict:
                put("source.cs", "fork code\n")
            git("add", ".")
            git("commit", "-m", "fork")
            before = git("rev-parse", "HEAD").stdout
            native_git = sync.git

            def fetch_local(*args, **kwargs):
                if args[0] == "fetch":
                    (root / ".git" / "FETCH_HEAD").write_bytes(
                        git("rev-parse", "upstream").stdout
                    )
                    return subprocess.CompletedProcess(args, 0)
                return native_git(*args, **kwargs)

            with patch.object(sync, "ROOT", root), patch.object(sync, "git", fetch_local):
                result = sync.main()
                if not conflict:
                    self.assertEqual(sync.main(), 0)  # repeat is a no-op
            self.assertEqual(result, 1 if conflict else 0)
            self.assertEqual((root / "README.md").read_text(), "Russian documentation\n")
            self.assertFalse((root / ".github/workflows/new.yml").exists())
            self.assertFalse((root / "package-debian-x86.sh").exists())
            self.assertFalse(git("status", "--porcelain").stdout)
            if conflict:
                self.assertEqual(git("rev-parse", "HEAD").stdout, before)
            else:
                self.assertEqual((root / "source.cs").read_text(), "upstream with spaces   \n")
                self.assertEqual(len(git("rev-list", "--parents", "-n", "1", "HEAD").stdout.split()), 3)


if __name__ == "__main__":
    unittest.main()
