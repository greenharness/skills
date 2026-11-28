"""The content gate recognises a squash-merged branch by its content.

A squash merge puts the branch's changes on base without making its
commits ancestors of base. `content_on_base` asks git whether merging the
branch into origin/<base> would change anything; when it would not, the
branch's work is already there and the worktree can go.
"""
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from test_sweep_loads import load_sweep

sweep = load_sweep()


def sh(cwd, *args):
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
        "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
    }
    return subprocess.run(["git", "-C", str(cwd), *args], check=True,
                          capture_output=True, text=True, env=env).stdout.strip()


def write(repo, name, text):
    (repo / name).write_text(text)
    sh(repo, "add", name)


class ContentOnBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "r"
        self.repo.mkdir()
        sh(self.repo, "init", "-q", "-b", "main")
        write(self.repo, "a.txt", "one\n")
        sh(self.repo, "commit", "-qm", "base")
        self.base = sh(self.repo, "rev-parse", "HEAD")
        # The branch: two logical commits.
        sh(self.repo, "switch", "-qc", "feat/x")
        write(self.repo, "b.txt", "two\n")
        sh(self.repo, "commit", "-qm", "add b")
        write(self.repo, "a.txt", "one\nmore\n")
        sh(self.repo, "commit", "-qm", "grow a")
        self.wt = sweep.Worktree(path=self.repo, primary=self.repo,
                                 branch="feat/x", head=sh(self.repo, "rev-parse", "HEAD"))
        self.r = sweep.Repo(path=self.repo, base="main")

    def tearDown(self):
        self.tmp.cleanup()

    def squash_onto_main(self, *then):
        """Squash feat/x onto main and point origin/main at the result, plus
        any further commits `then` makes on main."""
        sh(self.repo, "switch", "-q", "main")
        sh(self.repo, "merge", "-q", "--squash", "feat/x")
        sh(self.repo, "commit", "-qm", "feat: x (#1)")
        for step in then:
            step()
        sh(self.repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        sh(self.repo, "switch", "-q", "feat/x")

    def test_a_squash_merged_branch_is_on_base(self):
        self.squash_onto_main()
        self.assertFalse(subprocess.run(
            ["git", "-C", str(self.repo), "merge-base", "--is-ancestor", "HEAD", "origin/main"]
        ).returncode == 0, "a squash merge must not make the branch an ancestor")
        self.assertTrue(sweep.content_on_base(self.wt, self.r))

    def test_base_that_moved_on_elsewhere_still_holds_the_content(self):
        def unrelated():
            write(self.repo, "c.txt", "three\n")
            sh(self.repo, "commit", "-qm", "unrelated")
        self.squash_onto_main(unrelated)
        self.assertTrue(sweep.content_on_base(self.wt, self.r))

    def test_an_unmerged_branch_is_not_on_base(self):
        sh(self.repo, "update-ref", "refs/remotes/origin/main", self.base)
        self.assertFalse(sweep.content_on_base(self.wt, self.r))

    def test_a_change_reverted_on_base_is_not_on_base(self):
        def revert():
            sh(self.repo, "revert", "--no-edit", "HEAD")
        self.squash_onto_main(revert)
        self.assertFalse(sweep.content_on_base(self.wt, self.r))

    def test_the_content_gate_sweeps_an_idle_squash_merged_branch(self):
        self.squash_onto_main()
        old = time.time() - 48 * 3600
        for name in ("logs/HEAD", "HEAD"):
            p = self.repo / ".git" / name
            if p.exists():
                os.utime(p, (old, old))
        self.assertTrue(sweep.content_gate(self.wt, self.r))
        self.assertEqual(self.wt.verdict, sweep.SWEEP)
        self.assertIn("content already on origin/main", self.wt.reason)


if __name__ == "__main__":
    unittest.main()
