"""Processes rooted in a worktree: classification, protection, selection,
stopping. Constructed process tables only; no real process is read or signalled
and nothing touches the real home."""
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

SWEEP = Path(__file__).resolve().parent.parent / "parts/workflow/skills/worktree-sweep/sweep.py"


def load():
    spec = importlib.util.spec_from_file_location("sweep_procs_under_test", SWEEP)
    module = importlib.util.module_from_spec(spec)
    sys.modules["sweep_procs_under_test"] = module
    spec.loader.exec_module(module)
    return module


sweep = load()
START = "Thu Oct 30 10:00:00 2026"


def make_proc(pid, ppid, comm, args=None, cwd=None):
    return sweep.Proc(pid, ppid, START, comm, args if args is not None else comm,
                  Path(cwd) if cwd else None)


def make_table(*procs):
    return {proc.pid: proc for proc in procs}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(os.path.realpath(self.tmp.name))
        state = self.root / "state"
        for name, value in (("STATE_DIR", state), ("STATE_FILE", state / "state.json"),
                            ("LOG_FILE", state / "sweep.log"),
                            ("REMOVED_FILE", state / "removed.jsonl")):
            patcher = mock.patch.object(sweep, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)


class Classify(Base):
    def test_kinds(self):
        table = make_table(make_proc(1, 0, "launchd"), make_proc(10, 1, "/bin/fleet-lsp", "fleet-lsp serve rust"),
              make_proc(11, 10, "rust-analyzer"),
              make_proc(20, 1, "/x/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
                "/x/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing --remote-debugging-pipe"),
              make_proc(21, 1, "chrome-headless-", "/o/chrome-headless-shell --headless"),
              make_proc(30, 1, "node", "node /n/chrome-devtools-mcp/build/index.js"),
              make_proc(40, 1, "sleep", "sleep 100"),
              make_proc(50, 1, "chrome", "/o/chrome --no-sandbox"))
        kind_of = lambda pid: sweep.classify_proc(table[pid], table)
        self.assertEqual(kind_of(11), "lsp")
        self.assertEqual(kind_of(20), "browser")
        self.assertEqual(kind_of(21), "browser")
        self.assertEqual(kind_of(30), "mcp")
        self.assertEqual(kind_of(40), "process")
        self.assertEqual(kind_of(50), "process")      # Chrome without automation flags
        self.assertEqual(kind_of(10), "process")      # fleet-lsp itself

    def test_worktree_classifier_kept(self):
        repo = sweep.Repo(path=self.root / "r", forge="github", owner="o", name="r")
        wt = sweep.Worktree(path=self.root / "gone", primary=repo.path, branch="x", head="h",
                        prunable=True)
        sweep.classify(wt, repo)
        self.assertEqual((wt.verdict, wt.reason), (sweep.SWEEP, "prunable (path gone)"))
        live_wt = sweep.Worktree(path=self.root, primary=repo.path, branch="main", head="h")
        with mock.patch.object(sweep, "lookup_pr", side_effect=AssertionError("no forge call")):
            sweep.classify(live_wt, repo)
        self.assertEqual(live_wt.verdict, sweep.HOLD)


class Parsing(Base):
    def test_padded_first_row_and_comm_with_spaces(self):
        chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        out = (f"  1     0 Thu Oct 30 10:00:00 2026 /sbin/launchd\n"
               f"  99    1 Thu Oct  3 09:01:02 2026 {chrome}\n"
               f"  junk row\n"
               f"  77    1 Notadate at all here xxxxx /bin/x\n")
        args = f"  1 /sbin/launchd\n 99 {chrome} --headless\n"
        table = sweep.parse_ps(out.strip(), args)
        self.assertEqual(sorted(table), [1, 99])
        self.assertEqual(table[99].comm, chrome)
        self.assertEqual(table[99].start, "Thu Oct  3 09:01:02 2026")
        self.assertEqual(sweep.pname(table[99]), "Google Chrome")
        self.assertTrue(sweep._is_browser(table[99]))

    def test_deleted_suffix_stripped(self):
        cwds = sweep.parse_lsof("p12\nfcwd\nn/a/b (deleted)\np13\nn/c")
        self.assertEqual(cwds, {12: Path("/a/b"), 13: Path("/c")})

    def test_deleted_cwd_matches(self):
        gone = self.root / "r-wt-a"
        cwds = sweep.parse_lsof(f"p5\nn{gone} (deleted)")
        proc = make_proc(5, 1, "sleep")
        proc.cwd = cwds[5]
        owners = sweep.Owners(set(), {self.root / "r"})
        self.assertEqual([found.pid for found in sweep.orphans(make_table(proc), owners, set())], [5])

    def test_env_keeps_path(self):
        env = sweep.c_locale_env()
        self.assertEqual(env["LC_ALL"], "C")
        self.assertEqual(env.get("PATH"), os.environ.get("PATH"))


class Protected(Base):
    def test_protection(self):
        table = make_table(make_proc(1, 0, "launchd"), make_proc(2, 1, "zsh"), make_proc(3, 2, "sweep.py", "python3 sweep.py"),
              make_proc(4, 1, "claude"), make_proc(5, 4, "zsh"), make_proc(6, 5, "pnpm"), make_proc(7, 6, "node"),
              make_proc(8, 7, "chrome", "/o/chrome --headless"),
              make_proc(9, 4, "node", "npm exec chrome-devtools-mcp@latest"),
              make_proc(10, 9, "node", "node /n/chrome-devtools-mcp/index.js"),
              make_proc(11, 10, "chrome", "/o/chrome --remote-debugging-pipe"),
              make_proc(12, 4, "fleet-lsp", "fleet-lsp serve rust"), make_proc(13, 12, "rust-analyzer"))
        prot = sweep.protected(table, 3)
        self.assertTrue({1, 2, 3, 4, 9, 10, 11} <= prot)
        for pid in (5, 6, 7, 8, 12, 13):
            self.assertNotIn(pid, prot)

    def test_claude_ancestors_protected(self):
        table = make_table(make_proc(1, 0, "launchd"), make_proc(2, 1, "tmux"), make_proc(3, 2, "claude"), make_proc(4, 1, "other"))
        self.assertEqual(sweep.protected(table, 4), {1, 2, 3, 4})


class Selections(Base):
    def setUp(self):
        super().setUp()
        self.primary = self.root / "repo"
        self.primary.mkdir()
        (self.primary / "build").mkdir()
        self.owners = sweep.Owners(set(), {self.primary})

    def test_lsp_under_claude_with_gone_cwd(self):
        gone = self.root / "repo-wt-x"
        table = make_table(make_proc(1, 0, "launchd"), make_proc(4, 1, "claude"), make_proc(12, 4, "fleet-lsp"),
              make_proc(13, 12, "rust-analyzer", cwd=gone), make_proc(14, 13, "child", cwd=gone))
        got = sweep.orphans(table, self.owners, sweep.protected(table, 1))
        self.assertEqual([proc.pid for proc in got], [13])
        self.assertEqual(sweep.classify_proc(got[0], table), "lsp")

    def test_deleted_subdir_of_live_checkout(self):
        sub = self.primary / "build" / "gone"
        table = make_table(make_proc(1, 0, "launchd"), make_proc(2, 1, "sleep", cwd=sub))
        self.assertEqual(sweep.orphans(table, self.owners, {1}), [])
        self.assertEqual(sweep.unowned_orphans(table, self.owners, {1}), [])

    def test_registered_removed_sibling_unowned(self):
        registered, removed, sibling, unknown = (self.root / name for name in ("reg", "rem", "repo-wt-s", "unk"))
        table = make_table(make_proc(1, 0, "launchd"), make_proc(2, 1, "a", cwd=registered), make_proc(3, 1, "b", cwd=removed),
              make_proc(4, 1, "c", cwd=sibling), make_proc(5, 1, "d", cwd=unknown))
        owners = sweep.Owners({registered, removed}, {self.primary})
        self.assertEqual(sorted(proc.pid for proc in sweep.orphans(table, owners, {1})), [2, 3, 4])
        self.assertEqual([proc.pid for proc in sweep.unowned_orphans(table, owners, {1})], [5])

    def test_only_top_level(self):
        wt = self.root / "wt"
        table = make_table(make_proc(1, 0, "launchd"), make_proc(2, 1, "zsh", cwd=wt), make_proc(3, 2, "sleep", cwd=wt))
        owners = sweep.Owners({wt}, {self.primary})
        self.assertEqual([proc.pid for proc in sweep.orphans(table, owners, {1})], [2])
        live = self.root / "live"
        live.mkdir()
        live_table = make_table(make_proc(1, 0, "launchd"), make_proc(2, 1, "zsh", cwd=live), make_proc(3, 2, "sleep", cwd=live))
        self.assertEqual([proc.pid for proc in sweep.rooted(live_table, live, {1})], [2])

    def test_rooted_skips_protected(self):
        live = self.root / "live"
        live.mkdir()
        table = make_table(make_proc(1, 0, "launchd"), make_proc(2, 1, "claude", cwd=live), make_proc(3, 2, "sleep", cwd=live))
        self.assertEqual([proc.pid for proc in sweep.rooted(table, live, sweep.protected(table, 1))], [3])


class OrphanMcp(Base):
    def chain(self, *middle, parent=make_proc(1, 0, "launchd")):
        table = make_table(parent, *middle)
        return sweep.orphan_mcp(table, table, sweep.protected(table, 999))

    def test_orphan_selected_from_npm(self):
        npm = make_proc(2, 1, "node", "npm exec chrome-devtools-mcp@latest")
        got = self.chain(npm, make_proc(3, 2, "node", "node /n/chrome-devtools-mcp/i.js"),
                         make_proc(4, 3, "chrome", "/o/chrome --remote-debugging-pipe"))
        self.assertEqual([proc.pid for proc in got], [2])

    def test_under_live_claude(self):
        got = self.chain(make_proc(4, 1, "claude"), make_proc(2, 4, "node", "npm exec chrome-devtools-mcp"),
                         make_proc(3, 2, "node", "node /n/chrome-devtools-mcp/i.js"))
        self.assertEqual(got, [])

    def test_other_client(self):
        got = self.chain(make_proc(5, 1, "Code"), make_proc(2, 5, "node", "npm exec chrome-devtools-mcp"),
                         make_proc(3, 2, "node", "node /n/chrome-devtools-mcp/i.js"))
        self.assertEqual(got, [])

    def test_systemd_never_stopped(self):
        got = self.chain(make_proc(6, 1, "systemd", "systemd --user"),
                         make_proc(2, 6, "node", "npm exec chrome-devtools-mcp"),
                         make_proc(3, 2, "node", "node /n/chrome-devtools-mcp/i.js"))
        self.assertEqual([proc.pid for proc in got], [2])


class Profiles(Base):
    def browser(self, directory):
        return make_proc(9, 1, "chrome", f"/o/chrome --headless --user-data-dir={directory}")

    def test_profile_dir(self):
        tmpdir = self.root / "tmp"
        tmpdir.mkdir()
        for name in ("playwright_a", "puppeteer_b", "other_c"):
            (tmpdir / name).mkdir()
        self.assertEqual(sweep.profile_dir(self.browser(tmpdir / "playwright_a"), tmpdir), tmpdir / "playwright_a")
        self.assertEqual(sweep.profile_dir(self.browser(tmpdir / "puppeteer_b"), tmpdir), tmpdir / "puppeteer_b")
        self.assertIsNone(sweep.profile_dir(self.browser(tmpdir / "other_c"), tmpdir))
        self.assertIsNone(sweep.profile_dir(self.browser(self.root / "playwright_x"), tmpdir))
        (self.root / "victim").mkdir()
        (tmpdir / "playwright_link").symlink_to(self.root / "victim")
        self.assertIsNone(sweep.profile_dir(self.browser(tmpdir / "playwright_link"), tmpdir))
        self.assertIsNone(sweep.profile_dir(make_proc(9, 1, "sleep", f"sleep --user-data-dir={tmpdir}/playwright_a"), tmpdir))


class Removed(Base):
    def wt(self, name, **fields):
        return sweep.Worktree(path=self.root / name, primary=self.root / "repo", branch="b", head="h", **fields)

    def test_repo_run_without_state_file(self):
        sweep.record_removed(self.wt("w1"))
        self.assertFalse(sweep.STATE_FILE.exists())
        self.assertEqual(sweep.collect_owners([]).roots, {self.root / "w1"})
        table = make_table(make_proc(1, 0, "launchd"), make_proc(2, 1, "sleep", cwd=self.root / "w1"))
        self.assertEqual([proc.pid for proc in sweep.orphans(table, sweep.collect_owners([]), {1})], [2])
        self.assertEqual(oct(sweep.REMOVED_FILE.stat().st_mode & 0o777), "0o600")

    def test_corrupt_and_old_entries(self):
        sweep.record_removed(self.wt("fresh"))
        old = {"path": str(self.root / "old"), "primary": "x", "time": time.time() - 15 * 86400}
        with sweep.REMOVED_FILE.open("a") as handle:
            handle.write("not json\n[1]\n" + json.dumps({"path": 3, "time": 1}) + "\n" + json.dumps(old) + "\n")
        self.assertEqual(sweep.read_removed(), {self.root / "fresh": self.root / "repo"})

    def test_save_state_leaves_it(self):
        sweep.record_removed(self.wt("w"))
        before = sweep.REMOVED_FILE.read_text()
        sweep.save_state([])
        self.assertEqual(sweep.REMOVED_FILE.read_text(), before)


class RemoveFlow(Base):
    def setUp(self):
        super().setUp()
        self.primary = self.root / "repo"
        self.primary.mkdir()
        self.path = self.root / "wt"
        self.path.mkdir()
        self.wt = sweep.Worktree(path=self.path, primary=self.primary, branch="b", head="h")
        self.events = []

        def fake_run(args, **_kwargs):
            self.events.append(tuple(args))
            return True, ""
        for target, new in (("run", fake_run),
                            ("stop_tree", lambda proc, kind, why: self.events.append(("stop", proc.pid, kind)) or True)):
            patcher = mock.patch.object(sweep, target, new)
            patcher.start()
            self.addCleanup(patcher.stop)

    def table(self, *extra):
        return make_table(make_proc(1, 0, "launchd"), *extra)

    def test_claude_appearing_holds(self):
        table = self.table(make_proc(2, 1, "claude", cwd=self.path), make_proc(3, 2, "sleep", cwd=self.path))
        with mock.patch.object(sweep, "read_procs", return_value=table):
            ok, what = sweep.remove(self.wt)
        self.assertFalse(ok)
        self.assertEqual(what, "a live session works here")
        self.assertEqual(self.wt.verdict, sweep.HOLD)
        self.assertFalse(any("remove" in event for event in self.events))

    def test_unevaluable_refuses(self):
        with mock.patch.object(sweep, "read_procs", return_value=None):
            ok, what = sweep.remove(self.wt)
        self.assertFalse(ok)
        self.assertEqual(self.wt.verdict, sweep.UNKNOWN)
        self.assertFalse(any("remove" in event for event in self.events))

    def test_sleep_appearing_removed_and_stopped(self):
        table = self.table(make_proc(3, 1, "sleep", cwd=self.path))
        with mock.patch.object(sweep, "read_procs", return_value=table):
            ok, what = sweep.remove(self.wt)
        self.assertEqual((ok, what), (True, "removed"))
        kinds = [event[0] for event in self.events]
        self.assertLess(next(index for index, event in enumerate(self.events) if "remove" in event),
                        kinds.index("stop"))
        self.assertIn(("stop", 3, "process"), self.events)
        self.assertEqual(sweep.read_removed(), {self.path: self.primary})

    def test_stale_registration_stops_before_prune(self):
        self.wt.prunable = True
        self.path.rmdir()
        table = self.table(make_proc(3, 1, "sleep", cwd=self.path))
        with mock.patch.object(sweep, "read_procs", return_value=table):
            ok, what = sweep.remove(self.wt)
        self.assertEqual((ok, what), (True, "pruned"))
        self.assertEqual(self.events[0][0], "stop")
        self.assertIn("prune", self.events[1])
        self.assertEqual(sweep.read_removed(), {self.path: self.primary})

    def test_prunable_with_existing_directory_leaves_processes(self):
        self.wt.prunable = True
        table = self.table(make_proc(3, 1, "sleep", cwd=self.path))
        with mock.patch.object(sweep, "read_procs", return_value=table):
            ok, what = sweep.remove(self.wt)
        self.assertEqual((ok, what), (True, "pruned"))
        self.assertFalse(any(event[0] == "stop" for event in self.events))
        self.assertIn("prune", self.events[0])

    def test_unrecorded_removal_is_refused(self):
        table = self.table(make_proc(3, 1, "sleep", cwd=self.path))
        with mock.patch.object(sweep, "read_procs", return_value=table), \
                mock.patch.object(sweep.os, "open", side_effect=OSError("disk full")), \
                mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr:
            ok, what = sweep.remove(self.wt)
        self.assertFalse(ok)
        self.assertIn("removed.jsonl", what)
        self.assertIn("removed.jsonl", stderr.getvalue())
        self.assertIn("REMOVAL-REFUSED", sweep.LOG_FILE.read_text())
        self.assertEqual(self.events, [])

    def test_unrecorded_stale_registration_is_refused(self):
        self.wt.prunable = True
        with mock.patch.object(sweep.os, "open", side_effect=OSError("disk full")), \
                mock.patch.object(sys, "stderr", new_callable=io.StringIO):
            ok, _ = sweep.remove(self.wt)
        self.assertFalse(ok)
        self.assertEqual(self.events, [])


class Reporting(Base):
    def test_report_procs_returns_count(self):
        primary = self.root / "repo"
        primary.mkdir()
        gone = self.root / "repo-wt-x"
        repo = sweep.Repo(path=primary)
        table = make_table(make_proc(1, 0, "launchd"), make_proc(2, 1, "sleep", cwd=gone))
        with mock.patch.object(sweep, "read_procs", return_value=table), \
                mock.patch.object(sys, "stdout", new_callable=io.StringIO) as stdout:
            self.assertEqual(sweep.report_procs(False, [repo]), 1)
        self.assertIn("ORPHAN-PROC", stdout.getvalue())
        with mock.patch.object(sweep, "read_procs", return_value=make_table(make_proc(1, 0, "launchd"))), \
                mock.patch.object(sys, "stdout", new_callable=io.StringIO) as stdout:
            self.assertEqual(sweep.report_procs(False, [repo]), 0)
        self.assertEqual(stdout.getvalue(), "")

    def test_sibling_of_repo_without_worktrees_is_owned(self):
        primary = self.root / "repo"
        primary.mkdir()
        subprocess.run(["git", "init", "-q", str(primary)], check=True)
        self.assertEqual(sweep.discover([self.root]), [])
        repos = sweep.discover([self.root], keep_empty=True)
        self.assertEqual([repo.path for repo in repos], [primary])
        self.assertEqual(repos[0].worktrees, [])
        gone = self.root / "repo-wt-x"
        table = make_table(make_proc(1, 0, "launchd"), make_proc(2, 1, "sleep", cwd=gone))
        owners = sweep.collect_owners(repos)
        self.assertEqual([proc.pid for proc in sweep.orphans(table, owners, {1})], [2])
        self.assertEqual(sweep.unowned_orphans(table, owners, {1}), [])

    def test_repo_scope_limits_ownership(self):
        for name in ("one", "two"):
            subprocess.run(["git", "init", "-q", str(self.root / name)], check=True)
        table = make_table(make_proc(1, 0, "launchd"), make_proc(2, 1, "sleep", cwd=self.root / "two-wt-x"))
        every = sweep.discover([self.root], keep_empty=True)
        scoped = [r for r in every if r.path.name == "one"]
        with mock.patch.object(sweep, "read_procs", return_value=table), \
                mock.patch.object(sys, "stdout", new_callable=io.StringIO) as stdout:
            sweep.report_procs(False, scoped)
        self.assertNotIn("ORPHAN-PROC", stdout.getvalue())
        self.assertEqual(sweep.orphans(table, sweep.collect_owners(scoped), {1}), [])
        self.assertEqual([p.pid for p in sweep.orphans(table, sweep.collect_owners(every), {1})], [2])

    def test_removed_entry_scoped_by_its_primary(self):
        for name in ("one", "two"):
            subprocess.run(["git", "init", "-q", str(self.root / name)], check=True)
        gone = self.root / "two-wt-x"
        sweep.REMOVED_FILE.parent.mkdir(parents=True, exist_ok=True)
        sweep.REMOVED_FILE.write_text(json.dumps(
            {"path": str(gone), "primary": str(self.root / "two"), "time": time.time()}) + "\n")
        table = make_table(make_proc(1, 0, "launchd"), make_proc(2, 1, "sleep", cwd=gone))
        every = sweep.discover([self.root], keep_empty=True)
        for name, expect in (("one", False), ("two", True), (None, True)):
            with mock.patch.object(sweep, "read_procs", return_value=table), \
                    mock.patch.object(sweep, "protected", return_value={1}), \
                    mock.patch.object(sys, "stdout", new_callable=io.StringIO) as stdout:
                sweep.report_procs(False, every, name)
            self.assertEqual("ORPHAN-PROC" in stdout.getvalue(), expect, name)
            if not expect:
                self.assertNotIn("ORPHAN-UNOWNED", stdout.getvalue(), name)

    def test_removed_entry_without_primary_only_without_scope(self):
        for name in ("one", "two"):
            subprocess.run(["git", "init", "-q", str(self.root / name)], check=True)
        gone = self.root / "elsewhere"
        sweep.REMOVED_FILE.parent.mkdir(parents=True, exist_ok=True)
        sweep.REMOVED_FILE.write_text(json.dumps({"path": str(gone), "time": time.time()}) + "\n")
        self.assertEqual(sweep.read_removed(), {gone: None})
        table = make_table(make_proc(1, 0, "launchd"), make_proc(2, 1, "sleep", cwd=gone))
        every = sweep.discover([self.root], keep_empty=True)
        for name, expect in (("one", False), (None, True)):
            with mock.patch.object(sweep, "read_procs", return_value=table), \
                    mock.patch.object(sweep, "protected", return_value={1}), \
                    mock.patch.object(sys, "stdout", new_callable=io.StringIO) as stdout:
                sweep.report_procs(False, every, name)
            self.assertEqual("ORPHAN-PROC" in stdout.getvalue(), expect, name)

    def test_main_procs_honours_repo(self):
        for name in ("one", "two"):
            subprocess.run(["git", "init", "-q", str(self.root / name)], check=True)
        table = make_table(make_proc(1, 0, "launchd"), make_proc(2, 1, "sleep", cwd=self.root / "two-wt-x"))
        argv = ["sweep.py", "--procs", "--root", str(self.root)]
        for extra, expect in (([], True), (["--repo", "one"], False), (["--repo", "two"], True)):
            with mock.patch.object(sys, "argv", argv + extra), \
                    mock.patch.object(sweep, "read_procs", return_value=table), \
                    mock.patch.object(sweep, "protected", return_value={1}), \
                    mock.patch.object(sys, "stdout", new_callable=io.StringIO) as stdout:
                sweep.main()
            self.assertEqual("ORPHAN-PROC" in stdout.getvalue(), expect, extra)
            if not expect:
                self.assertNotIn("ORPHAN-UNOWNED", stdout.getvalue(), extra)
                self.assertIn("No processes of deleted checkouts.", stdout.getvalue(), extra)

    def test_root_scope_selects_scratch_repo_sibling(self):
        scratch = self.root / "scratch"
        scratch.mkdir()
        subprocess.run(["git", "init", "-q", str(scratch / "repo")], check=True)
        table = make_table(make_proc(1, 0, "launchd"), make_proc(2, 1, "sleep", cwd=scratch / "repo-wt-x"))
        owners = sweep.collect_owners(sweep.discover([scratch], keep_empty=True))
        self.assertEqual([p.pid for p in sweep.orphans(table, owners, {1})], [2])


class StopTree(Base):
    def test_skips_changed_and_protected(self):
        top = make_proc(2, 1, "zsh")
        child = make_proc(3, 2, "sleep")
        fresh = make_table(make_proc(1, 0, "launchd"), top, child)
        killed = []
        rereads = {2: (START, "zsh"), 3: ("Fri Oct 31 00:00:00 2026", "sleep")}
        with mock.patch.object(sweep, "read_procs", return_value=fresh), \
                mock.patch.object(sweep, "reread", side_effect=lambda pid: rereads.get(pid)), \
                mock.patch.object(sweep.os, "kill", side_effect=lambda pid, sig: killed.append((pid, sig))), \
                mock.patch.object(sweep, "pid_alive", return_value=False):
            self.assertTrue(sweep.stop_tree(top, "process", "test"))
        self.assertEqual([call[0] for call in killed], [2])
        self.assertIn("PROC-STOPPED kind=process pid=2", sweep.LOG_FILE.read_text())

    def test_browser_profile_removed_after_exit(self):
        tmpdir = self.root / "tmp"
        tmpdir.mkdir()
        profile = tmpdir / "playwright_p"
        profile.mkdir()
        browser_proc = make_proc(2, 1, "chrome", f"/o/chrome --headless --user-data-dir={profile}")
        with mock.patch.object(sweep, "read_procs", return_value=make_table(make_proc(1, 0, "launchd"), browser_proc)), \
                mock.patch.object(sweep, "reread", return_value=(START, "chrome")), \
                mock.patch.object(sweep.os, "kill"), mock.patch.object(sweep, "pid_alive", return_value=False), \
                mock.patch.dict(os.environ, {"TMPDIR": str(tmpdir)}):
            sweep.stop_tree(browser_proc, "browser", "test")
        self.assertFalse(profile.exists())
        self.assertIn("PROFILE-REMOVED", sweep.LOG_FILE.read_text())

    def test_browser_profile_kept_when_rmtree_fails(self):
        tmpdir = self.root / "tmp"
        tmpdir.mkdir()
        profile = tmpdir / "playwright_p"
        profile.mkdir()
        browser_proc = make_proc(2, 1, "chrome", f"/o/chrome --headless --user-data-dir={profile}")
        with mock.patch.object(sweep, "read_procs", return_value=make_table(make_proc(1, 0, "launchd"), browser_proc)), \
                mock.patch.object(sweep, "reread", return_value=(START, "chrome")), \
                mock.patch.object(sweep.os, "kill"), mock.patch.object(sweep, "pid_alive", return_value=False), \
                mock.patch.object(sweep.shutil, "rmtree", side_effect=OSError("busy")), \
                mock.patch.dict(os.environ, {"TMPDIR": str(tmpdir)}):
            sweep.stop_tree(browser_proc, "browser", "test")
        self.assertIn(f"PROFILE-KEPT {profile}: busy", sweep.LOG_FILE.read_text())

    def test_permission_error_is_logged(self):
        top = make_proc(2, 1, "zsh")
        child = make_proc(3, 2, "sleep")
        fresh = make_table(make_proc(1, 0, "launchd"), top, child)

        def kill(pid, sig):
            if pid == 3:
                raise PermissionError
        with mock.patch.object(sweep, "read_procs", return_value=fresh), \
                mock.patch.object(sweep, "reread", return_value=None) as reread:
            reread.side_effect = lambda pid: (START, {2: "zsh", 3: "sleep"}[pid])
            with mock.patch.object(sweep.os, "kill", side_effect=kill):
                self.assertFalse(sweep.stop_tree(top, "process", "test"))
        self.assertIn("PROC-NOT-STOPPED pid=2 comm=zsh (", sweep.LOG_FILE.read_text())

    def test_profile_kept_when_browser_still_running(self):
        tmpdir = self.root / "tmp"
        tmpdir.mkdir()
        profile = tmpdir / "playwright_p"
        profile.mkdir()
        browser_proc = make_proc(2, 1, "chrome", f"/o/chrome --headless --user-data-dir={profile}")
        with mock.patch.object(sweep, "read_procs", return_value=make_table(make_proc(1, 0, "launchd"), browser_proc)), \
                mock.patch.object(sweep, "reread", return_value=(START, "chrome")), \
                mock.patch.object(sweep.os, "kill"), mock.patch.object(sweep, "pid_alive", return_value=True), \
                mock.patch.object(sweep, "GRACE_SECONDS", 0), \
                mock.patch.object(sweep, "KILL_WAIT_SECONDS", 0.1), \
                mock.patch.dict(os.environ, {"TMPDIR": str(tmpdir)}):
            stopped = sweep.stop_tree(browser_proc, "browser", "test")
        self.assertTrue(profile.exists())
        self.assertFalse(stopped)
        log = sweep.LOG_FILE.read_text()
        self.assertIn(f"PROFILE-KEPT {profile}: still running", log)
        self.assertIn("PROC-NOT-STOPPED pid=2 comm=chrome (still alive after SIGKILL)", log)
        self.assertNotIn("PROC-STOPPED", log)


class ClassifyForge(Base):
    def setUp(self):
        super().setUp()
        self.repo = sweep.Repo(path=self.root / "r", forge="github", owner="o", name="r")
        self.wt_path = self.root / "wt"
        self.wt_path.mkdir()

    def test_merged_released_pr_sweeps(self):
        wt = sweep.Worktree(path=self.wt_path, primary=self.repo.path, branch="feat", head="h")
        self.repo.has_vtags = True
        pr = {"state": "MERGED", "number": 7, "merge_sha": "abc123", "base": self.repo.base}

        def fake_git(_repo, *args, **_kw):
            return (True, "v1.2.0\nv1.3.0") if args[0] == "tag" else (True, "")
        with mock.patch.object(sweep, "local_gates", return_value=True), \
                mock.patch.object(sweep, "lookup_pr", return_value=pr), \
                mock.patch.object(sweep, "git", side_effect=fake_git):
            sweep.classify(wt, self.repo)
        self.assertEqual(wt.verdict, sweep.SWEEP)
        self.assertEqual(wt.release, "v1.3.0")

    def test_gates_share_one_snapshot(self):
        table = make_table(make_proc(1, 0, "launchd"))
        wts = []
        for name in ("a", "b", "c"):
            path = self.root / name
            path.mkdir()
            wts.append(sweep.Worktree(path=path, primary=self.repo.path, branch="feat", head="h"))
        sweep.begin_audit()
        self.addCleanup(setattr, sweep, "_SNAPSHOT", None)
        with mock.patch.object(sweep, "read_procs", return_value=table) as reader:
            for wt in wts:
                sweep.classify(wt, self.repo)
        self.assertEqual(reader.call_count, 1)

    def test_unreadable_process_table_is_unknown(self):
        wt = sweep.Worktree(path=self.wt_path, primary=self.repo.path, branch="feat", head="h")
        sweep.begin_audit()
        self.addCleanup(setattr, sweep, "_SNAPSHOT", None)
        with mock.patch.object(sweep, "read_procs", return_value=None), \
                mock.patch.object(sweep, "lookup_pr", side_effect=AssertionError("no forge call")), \
                mock.patch.object(sweep, "remove", side_effect=AssertionError("no removal")):
            sweep.classify(wt, self.repo)
        self.assertEqual((wt.verdict, wt.reason),
                         (sweep.UNKNOWN, "could not evaluate whether a live session works here"))

    def test_dry_run_holds_live_session(self):
        wt = sweep.Worktree(path=self.wt_path, primary=self.repo.path, branch="feat", head="h")
        table = make_table(make_proc(1, 0, "launchd"), make_proc(2, 1, "claude", cwd=self.wt_path))
        with mock.patch.object(sweep, "read_procs", return_value=table), \
                mock.patch.object(sweep, "lookup_pr", side_effect=AssertionError("no forge call")), \
                mock.patch.object(sweep, "remove", side_effect=AssertionError("no removal")):
            sweep.classify(wt, self.repo)
        self.assertEqual((wt.verdict, wt.reason), (sweep.HOLD, "a live session works here"))


if __name__ == "__main__":
    unittest.main()
