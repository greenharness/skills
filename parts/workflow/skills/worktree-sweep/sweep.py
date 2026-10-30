#!/usr/bin/env python3
"""Sweep git worktrees whose work is implemented, pushed, merged and released.

Verdicts, and what each means:

  SWEEP    every gate passed -- safe to remove. Nothing is lost: the branch is
           still on the forge and the worktree is one `git worktree add` away.
  HOLD     a gate said "not yet" and we trust that answer (open PR, dirty tree,
           unpushed commits, merged but not yet in a release tag).
  UNKNOWN  a gate could not be evaluated (forge unreachable, ambiguous state).
           Treated exactly like HOLD for removal purposes.

The distinction between HOLD and UNKNOWN is the whole point of this tool. Both
forges in use here fail in ways that are indistinguishable from a negative
answer if you are careless: `gh` prints nothing and exits 0-ish on an API
timeout, and Forgejo's /pulls endpoint returns the bare *repo* object (a dict,
not a list) when handed an unsupported `state=all`. Either one, read naively,
says "no merged PR" -- which for a *keep* decision is harmless and for a
*delete* decision is data loss. So every forge call that does not return a
positively-parsed PR yields UNKNOWN, and UNKNOWN never removes anything.

Two false HOLDs fixed 2026-09-11 (both erred safe, both gave the wrong reason):

  * The ahead-count ran on cached refs. GitHub deletes a branch on merge, so
    the stale origin/<branch> sat at the pre-squash commit and a finished
    branch read "1 unpushed commit". Now: one `fetch --prune` per repo first,
    and a branch with no surviving remote ref is proven pushed by ancestry of
    origin/<base> or by the merged PR's head sha equalling HEAD.
  * Forgejo lookups used /pulls/{base}/{head} with base=<default branch>, so a
    PR stacked on another feature branch 404'd into "no pull request found".
    Now a 404 consults the open-PR list (one request per repo) by head.

Content gate added 2026-10-14 (the person's rule: "if the changes are on
origin main, it's safe to delete"). The gates above trace a *branch* to a
merged PR, so a detached checkout, or a branch that never needed a PR, was
held forever even when its HEAD sat on origin/<base> and it held nothing
else: ten such worktrees, 2.9 GB, on the day. Now a worktree whose HEAD is an
ancestor of origin/<base>, with a clean tree, is SWEEP by content -- removing
it loses nothing. Uncommitted edits to CLAUDE.md / AGENTS.md (generated agent
guidance) do not count as work; they are discarded at removal. A worktree
whose HEAD moved within MIN_IDLE_HOURS is still held: an agent that just ran
`worktree add -b feat/x origin/main` has a HEAD on base and no edits yet.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

HOME = Path.home()
STATE_DIR = HOME / ".claude" / "worktree-sweep"
STATE_FILE = STATE_DIR / "state.json"
LOG_FILE = STATE_DIR / "sweep.log"
DEFAULT_ROOTS = [HOME / "Developer"]

# A self-hosted Forgejo is opt-in: set SWEEP_FORGEJO_HOST to its host name.
# Its token is read from the netrc file; a client certificate, when the host asks
# for one, comes from SWEEP_FORGEJO_CERT and SWEEP_FORGEJO_KEY.
FORGEJO_HOST = os.environ.get("SWEEP_FORGEJO_HOST", "")
_cert = os.environ.get("SWEEP_FORGEJO_CERT", "")
_key = os.environ.get("SWEEP_FORGEJO_KEY", "")
FORGEJO_CERT = Path(_cert).expanduser() if _cert else None
FORGEJO_KEY = Path(_key).expanduser() if _key else None
NETRC = HOME / ".netrc"  # check: allow (the standard netrc file; the host is configured)

# The forge is slow over this path -- a single PR lookup measured 13-17s.
FORGE_TIMEOUT = 60
GIT_TIMEOUT = 120

SWEEP, HOLD, UNKNOWN = "SWEEP", "HOLD", "UNKNOWN"

# Content gate (see the module docstring). Uncommitted edits to these files
# are generated agent guidance, not work; they are discarded at removal.
DROPPABLE_DIRTY = {"CLAUDE.md", "AGENTS.md"}
# A HEAD that moved more recently than this may be a task that just started
# from origin/<base> and has not committed yet; the content gate holds it.
MIN_IDLE_HOURS = 24

# A forge that is down costs FORGE_TIMEOUT * retries *per branch*. With seven
# worktrees on one host that is minutes of dead waiting for an answer already
# known to be UNKNOWN. After this many consecutive failures, stop asking.
CIRCUIT_TRIP = 3
_circuit: dict[str, int] = {}
_circuit_lock = threading.Lock()


def circuit_open(forge: str) -> bool:
    with _circuit_lock:
        return _circuit.get(forge, 0) >= CIRCUIT_TRIP


def circuit_record(forge: str, ok: bool):
    with _circuit_lock:
        _circuit[forge] = 0 if ok else _circuit.get(forge, 0) + 1


# process helpers


def run(args, cwd=None, timeout=GIT_TIMEOUT, env=None):
    """Run a command. Returns (ok, stdout). ok is False on ANY failure path."""
    try:
        p = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False, ""
    return p.returncode == 0, p.stdout.strip()


def git(repo, *args, timeout=GIT_TIMEOUT):
    return run(["git", "-C", str(repo), *args], timeout=timeout)


# model


@dataclass
class Worktree:
    path: Path
    primary: Path
    branch: str | None          # None => detached HEAD
    head: str
    locked: bool = False
    prunable: bool = False

    verdict: str = UNKNOWN
    reason: str = ""
    pr: str = ""
    release: str = ""
    size_kb: int = 0
    # How "nothing unpushed" was established. "remote-ref": compared against the
    # branch's own origin ref. "on-base": HEAD is an ancestor of origin/<base>.
    # "pr-head": no remote ref survives, so the merged PR's head sha must equal
    # HEAD -- that is proven only after the forge lookup, in classify().
    pushed: str = ""
    # Tracked guidance files (DROPPABLE_DIRTY) with uncommitted edits, restored
    # by remove() before `git worktree remove`, which refuses a modified tree.
    drop: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        try:
            return str(self.path.relative_to(HOME / "Developer"))
        except ValueError:
            return f"{self.primary.name}:{self.path.name}"


@dataclass
class Repo:
    path: Path
    forge: str = "none"         # github | forgejo | none
    owner: str = ""
    name: str = ""
    base: str = "main"
    has_vtags: bool = False
    worktrees: list[Worktree] = field(default_factory=list)
    # Per-repo, once-only work shared by every worktree's classification.
    # None = not attempted yet; the lock keeps 4 workers from racing it.
    fetched: bool | None = None
    open_prs: list | None = None            # forgejo: cached open-PR list
    open_prs_failed: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


def ensure_fetched(repo: Repo) -> bool:
    """`git fetch --prune` once per repo, before any ahead/behind arithmetic.

    Without it the ahead-count compares against whatever remote-tracking ref
    happens to be cached. GitHub deletes the branch on merge, so the stale
    `origin/<branch>` lingers at the pre-squash commit and a finished branch
    reads "1 unpushed commit" (seen on amont-agent chore/release-2.12.0, whose
    HEAD *was* the squash commit already on main). Prune makes that ref
    disappear; the pr-head proof in classify() then takes over.

    A failed fetch is not fatal -- the gates still run on cached refs -- but
    every verdict that leans on them says so.
    """
    with repo.lock:
        if repo.fetched is None:
            ok, _ = git(repo.path, "fetch", "origin", "--prune", "-q", timeout=FORGE_TIMEOUT)
            repo.fetched = ok
        return repo.fetched


def stale_note(repo: Repo) -> str:
    return "" if repo.fetched else " (fetch failed -- refs may be stale)"


# discovery


def parse_remote(url: str):
    """git@host:owner/repo.git or https://host/owner/repo(.git) -> (forge, owner, repo)."""
    if not url:
        return "none", "", ""
    host = path = ""
    if url.startswith(("http://", "https://")):
        u = urllib.parse.urlparse(url)
        host, path = u.hostname or "", u.path.lstrip("/")
    elif "@" in url and ":" in url:
        hostpart, _, path = url.partition(":")
        host = hostpart.rpartition("@")[2]
    if path.endswith(".git"):
        path = path[:-4]
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        return "none", "", ""
    owner, name = parts[-2], parts[-1]
    if host == "github.com":
        return "github", owner, name
    if FORGEJO_HOST and host == FORGEJO_HOST:
        return "forgejo", owner, name
    return "none", owner, name


def find_primaries(roots, max_depth=3) -> set[Path]:
    """Primary checkouts (a real .git *directory*) under roots. No subprocess."""
    primaries: set[Path] = set()
    for root in roots:
        root = Path(root).expanduser()
        if not root.is_dir():
            continue
        for dirpath, dirnames, _ in os.walk(root):
            depth = len(Path(dirpath).relative_to(root).parts)
            if depth >= max_depth:
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in dirnames if d not in {"node_modules", ".venv", "target", "dist"}]
            if ".git" in dirnames:
                # A linked worktree has .git as a *file*; only directories are primaries.
                if (Path(dirpath) / ".git").is_dir():
                    primaries.add(Path(dirpath).resolve())
                dirnames.remove(".git")
    return primaries


def discover(roots, max_depth=3, keep_empty=False) -> list[Repo]:
    """Find primary checkouts and their linked worktrees -- wherever those live
    (/tmp, $TMPDIR, a scratchpad): `git worktree list` knows them all. A
    checkout with no linked worktree is kept only with keep_empty: process
    ownership still needs it for its `<repo>-wt-*` siblings."""
    repos: list[Repo] = []
    for primary in sorted(find_primaries(roots, max_depth)):
        ok, out = git(primary, "worktree", "list", "--porcelain")
        if not ok:
            continue
        repo = Repo(path=primary)
        ok_r, url = git(primary, "remote", "get-url", "origin")
        if ok_r:
            repo.forge, repo.owner, repo.name = parse_remote(url)
        ok_b, ref = git(primary, "symbolic-ref", "refs/remotes/origin/HEAD")
        if ok_b and ref:
            repo.base = ref.rsplit("/", 1)[-1]
        ok_t, tags = git(primary, "tag", "-l", "v*")
        repo.has_vtags = ok_t and bool(tags.strip())

        cur = {}
        entries = []
        for line in out.splitlines() + [""]:
            if not line.strip():
                if cur:
                    entries.append(cur)
                cur = {}
                continue
            key, _, val = line.partition(" ")
            cur[key] = val
        for e in entries:
            wt_path = Path(e.get("worktree", "")).resolve()
            if wt_path == primary:
                continue                       # the primary checkout is never swept
            branch = e.get("branch")
            if branch:
                branch = branch.replace("refs/heads/", "")
            repo.worktrees.append(
                Worktree(
                    path=wt_path,
                    primary=primary,
                    branch=None if "detached" in e else branch,
                    head=e.get("HEAD", ""),
                    locked="locked" in e,
                    prunable="prunable" in e,
                )
            )
        if repo.worktrees or keep_empty:
            repos.append(repo)
    return repos


# forge adapters -- every failure path returns None (=> UNKNOWN)


def forgejo_token():
    try:
        for line in NETRC.read_text().splitlines():
            f = line.split()
            if len(f) >= 6 and f[0] == "machine" and f[1] == FORGEJO_HOST:
                return f[5]
    except OSError:
        pass
    return None


def pr_github(repo: Repo, branch: str):
    ok, out = run(
        [
            "gh", "pr", "list",
            "--repo", f"{repo.owner}/{repo.name}",
            "--head", branch,
            "--state", "all",
            "--limit", "10",
            "--json", "number,state,mergedAt,mergeCommit,headRefOid,baseRefName",
        ],
        timeout=FORGE_TIMEOUT,
    )
    if not ok or not out:
        return None                            # timeout / auth / rate limit -> UNKNOWN
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list):
        return None
    if not data:
        return {"state": "NO-PR"}
    merged = [p for p in data if p.get("state") == "MERGED"]
    p = merged[0] if merged else data[0]
    return {
        "number": p.get("number"),
        "state": p.get("state", ""),
        "merge_sha": ((p.get("mergeCommit") or {}) or {}).get("oid", "") or "",
        "head_sha": p.get("headRefOid") or "",
        "base": p.get("baseRefName") or "",
    }


def forgejo_get(repo: Repo, path: str):
    """GET one Forgejo API path. Returns (http_code, parsed_json) or (None, None)
    on any transport failure -- callers must map that to UNKNOWN, never NO-PR."""
    tok = forgejo_token()
    if not tok:
        return None, None
    cert = []
    if FORGEJO_CERT or FORGEJO_KEY:
        if not (FORGEJO_CERT and FORGEJO_KEY and FORGEJO_CERT.exists() and FORGEJO_KEY.exists()):
            return None, None
        cert = ["--cert", str(FORGEJO_CERT), "--key", str(FORGEJO_KEY)]
    ok, out = run(
        [
            "curl", "-sS", "--max-time", str(FORGE_TIMEOUT),
            *cert,
            "-H", f"Authorization: token {tok}",
            "-w", "\n%{http_code}",
            f"https://{FORGEJO_HOST}/api/v1/repos/{repo.owner}/{repo.name}{path}",
        ],
        timeout=FORGE_TIMEOUT + 10,
    )
    if not ok or not out:
        return None, None
    body, _, code = out.rpartition("\n")
    code = code.strip()
    try:
        return code, json.loads(body) if body.strip() else None
    except json.JSONDecodeError:
        return code, None


def forgejo_open_prs(repo: Repo):
    """The repo's open PRs, fetched once and shared by every branch lookup.

    `state=open` is the one listing that answers quickly on this forge (the
    closed listing is what times out). Returns None if it could not be read --
    and that is sticky, so a dead forge costs one request, not one per branch.
    """
    with repo.lock:
        if repo.open_prs is not None or repo.open_prs_failed:
            return repo.open_prs
        prs: list = []
        page = 1
        while True:
            code, data = forgejo_get(repo, f"/pulls?state=open&limit=50&page={page}")
            if code != "200" or not isinstance(data, list):
                repo.open_prs_failed = True
                return None
            prs.extend(p for p in data if isinstance(p, dict) and "number" in p and "head" in p)
            if len(data) < 50:
                break
            page += 1
        repo.open_prs = prs
        return prs


def pr_forgejo(repo: Repo, branch: str):
    # /pulls/{base}/{head} answers in one request. Paging /pulls?state=closed
    # instead takes many requests against a slow forge and times out.
    code, p = forgejo_get(
        repo,
        f"/pulls/{urllib.parse.quote(repo.base, safe='')}/{urllib.parse.quote(branch, safe='')}",
    )
    if code is None:
        return None
    if code == "404":
        # Not "no PR" yet: this endpoint is keyed on the base branch, so a PR
        # stacked on another feature branch (#688 -> #687's branch) is
        # invisible to it. Ask the open-PR list by head before concluding.
        prs = forgejo_open_prs(repo)
        if prs is None:
            return None                        # could not check -> UNKNOWN
        for o in prs:
            if (o.get("head") or {}).get("ref") == branch:
                return {
                    "number": o.get("number"),
                    "state": "OPEN",
                    "merge_sha": "",
                    "head_sha": (o.get("head") or {}).get("sha") or "",
                    "base": (o.get("base") or {}).get("ref") or "",
                }
        return {"state": "NO-PR"}
    if code != "200":
        return None
    # Guard the documented trap: an unsupported query makes this endpoint hand
    # back the repo object. A PR always carries an integer "number" and a "head".
    if not isinstance(p, dict) or "number" not in p or "head" not in p:
        return None
    return {
        "number": p.get("number"),
        "state": "MERGED" if p.get("merged_at") else p.get("state", "").upper(),
        "merge_sha": p.get("merge_commit_sha") or "",
        "head_sha": (p.get("head") or {}).get("sha") or "",
        "base": (p.get("base") or {}).get("ref") or "",
    }


def lookup_pr(repo: Repo, branch: str):
    fn = {"github": pr_github, "forgejo": pr_forgejo}.get(repo.forge)
    if fn is None:
        return None
    for attempt in range(2):
        # Re-checked every attempt, not just once up front: with N workers all
        # blocked on the same dead host, the breaker has to be able to open
        # *underneath* an in-flight wave, or every worker pays the full retry.
        if circuit_open(repo.forge):
            return None
        res = fn(repo, branch)
        if res is not None:
            circuit_record(repo.forge, True)
            return res
        circuit_record(repo.forge, False)   # per attempt, so the breaker trips inside wave 1
        if attempt == 0 and not circuit_open(repo.forge):
            time.sleep(2)
    return None


# classification


# amont's push rehearsal checks the pushed tip out at
# $TMPDIR/amont-push-<pid>-<16 hex> (`worktree add --detach`, pushed_tree.rs)
# and removes it on Drop. One still registered means that process died before
# Drop -- or is alive right now: two seen 2026-10-07 had vanished minutes later,
# rehearsals in flight. So the owning pid must be dead.
AMONT_PUSH_RE = re.compile(r"^amont-push-(\d+)-[0-9a-f]{16}$")

# relais checks a run's candidate out under its own state directory
# (<state>/worktrees/<run>/task, <state>/verify/<run>/verify-base) and owns
# its lifecycle: only relais can tell a dead run from a live one, so the
# sweep never removes these -- it names the run and the command that does.
RELAIS_STATE = Path(os.environ.get("RELAIS_STATE_DIR") or HOME / ".local" / "state" / "relais")
RELAIS_RUN_RE = re.compile(r"^run-[0-9a-f]+-[0-9a-f]+$")


def relais_run_of(path: Path) -> str | None:
    """The relais run a worktree belongs to, if it lives in relais's state."""
    try:
        rel = path.resolve().relative_to(RELAIS_STATE.resolve())
    except (ValueError, OSError):
        return None
    parts = rel.parts
    if len(parts) >= 2 and parts[0] in {"worktrees", "verify"} and RELAIS_RUN_RE.match(parts[1]):
        return parts[1]
    return None
AMONT_PUSH_MIN_AGE = 3600


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True                        # EPERM: exists, someone else's
    return True


def amont_push_leftover(wt: Worktree, repo: Repo):
    """SWEEP a dead rehearsal's snapshot. It is amont's, never edited by hand,
    and HEAD is the pushed tip -- but each of these is checked, not assumed:
    owner pid dead, older than an hour (pid reuse aside, a slow prepare is
    still a live one), clean tree, HEAD still on some ref of the repo."""
    pid = int(AMONT_PUSH_RE.match(wt.path.name).group(1))
    if pid_alive(pid):
        wt.verdict, wt.reason = HOLD, f"amont push rehearsal in flight (pid {pid} alive)"
        return
    try:
        age = time.time() - (wt.path / ".git").stat().st_mtime
    except OSError:
        wt.verdict, wt.reason = UNKNOWN, "amont snapshot: cannot stat .git"
        return
    if age < AMONT_PUSH_MIN_AGE:
        wt.verdict, wt.reason = HOLD, f"amont snapshot only {int(age // 60)}m old"
        return
    ok, dirty = git(wt.path, "status", "--porcelain")
    if not ok:
        wt.verdict, wt.reason = UNKNOWN, "git status failed"
        return
    if dirty:
        wt.verdict, wt.reason = HOLD, f"amont snapshot has {len(dirty.splitlines())} uncommitted change(s)"
        return
    ok, refs = git(repo.path, "for-each-ref", "--count=1", "--contains", wt.head, "--format=%(refname)")
    if not ok:
        wt.verdict, wt.reason = UNKNOWN, "could not check which refs contain HEAD"
        return
    if not refs:
        wt.verdict, wt.reason = HOLD, f"amont snapshot HEAD {wt.head[:12]} is on no ref"
        return
    wt.verdict, wt.reason = SWEEP, f"dead amont push rehearsal (pid {pid}), HEAD on {refs}"


def head_idle_hours(wt: Worktree) -> float | None:
    """Hours since this worktree's HEAD last moved (its reflog, else HEAD).
    Not the index: `git status` rewrites it, so this tool would reset it."""
    ok, gitdir = git(wt.path, "rev-parse", "--absolute-git-dir")
    if not ok or not gitdir:
        return None
    for name in ("logs/HEAD", "HEAD"):
        p = Path(gitdir) / name
        if p.exists():
            return (time.time() - p.stat().st_mtime) / 3600
    return None


def content_gate(wt: Worktree, repo: Repo) -> bool:
    """Decide by content alone: HEAD on origin/<base> and nothing else held.
    Returns True when it set a final verdict. Runs after the dirty check, so
    the tree is already clean save for DROPPABLE_DIRTY files."""
    ok, _ = git(wt.path, "merge-base", "--is-ancestor", "HEAD", f"origin/{repo.base}")
    if not ok:
        # Not on base (or git failed -- the safe reading). A branch goes on to
        # the PR gates; a detached HEAD has nothing else to be traced by.
        if wt.branch is None:
            wt.verdict, wt.reason = HOLD, f"detached HEAD {wt.head[:12]} not on origin/{repo.base}"
            return True
        return False
    idle = head_idle_hours(wt)
    if idle is None:
        wt.verdict, wt.reason = UNKNOWN, "could not read the HEAD reflog age"
        return True
    if idle < MIN_IDLE_HOURS:
        if wt.branch is None:
            wt.verdict = HOLD
            wt.reason = f"on origin/{repo.base}, but HEAD moved {idle:.0f}h ago (< {MIN_IDLE_HOURS}h)"
            return True
        return False  # a fresh task branch: let the PR gates speak
    wt.verdict = SWEEP
    dropped = f", drops edits to {', '.join(wt.drop)}" if wt.drop else ""
    wt.reason = f"HEAD on origin/{repo.base}, nothing else held{dropped}"
    return True


def local_gates(wt: Worktree, repo: Repo) -> bool:
    """Cheap, offline gates. Returns True only if still a candidate."""
    cwd = START_CWD
    if cwd is not None and (wt.path == cwd or wt.path in cwd.parents):
        wt.verdict, wt.reason = HOLD, "in use (current working directory)"
        return False
    if wt.locked:
        wt.verdict, wt.reason = HOLD, "worktree is locked"
        return False
    if (wt.path / ".no-sweep").exists():
        wt.verdict, wt.reason = HOLD, "opted out (.no-sweep)"
        return False
    if wt.prunable or not wt.path.exists():
        wt.verdict, wt.reason = SWEEP, "prunable (path gone)"
        return False
    if wt.branch is None:
        if AMONT_PUSH_RE.match(wt.path.name):
            amont_push_leftover(wt, repo)
            return False
        run = relais_run_of(wt.path)
        if run is not None:
            wt.verdict, wt.reason = HOLD, f"relais run {run} owns it -- relais resume --retire {run}"
            return False
        # No branch to trace to a PR; the content gate below is the only way
        # a detached checkout is ever swept.
    elif wt.branch in {repo.base, "main", "master"}:
        wt.verdict, wt.reason = HOLD, f"checked out on {wt.branch}"
        return False

    # The first snapshot already shows a live session, so a dry run says HOLD;
    # remove() looks again right before the removal.
    table, why = session_verdict(audit_snapshot(), wt.path)
    if table is None:
        wt.verdict, wt.reason = (HOLD if why.startswith("a live") else UNKNOWN), why
        return False

    # Two lists rather than `status --porcelain`: run() strips stdout, which
    # eats the leading space of a ` M path` first line and shifts its path.
    ok, tracked = git(wt.path, "diff", "--name-only", "HEAD")
    ok2, untracked = git(wt.path, "ls-files", "--others", "--exclude-standard")
    if not (ok and ok2):
        wt.verdict, wt.reason = UNKNOWN, "git status failed"
        return False
    work = untracked.splitlines()
    for path in tracked.splitlines():
        (wt.drop if Path(path).name in DROPPABLE_DIRTY else work).append(path)
    if work:
        wt.verdict, wt.reason = HOLD, f"{len(work)} uncommitted change(s)"
        return False

    # Everything below is ref arithmetic, so refresh the refs first -- and
    # prune, so a branch the forge deleted on merge stops masquerading as a
    # remote ref frozen at its pre-squash commit.
    ensure_fetched(repo)

    if content_gate(wt, repo):
        return False
    if wt.branch is None:
        return False

    # Compare against the branch's OWN remote ref when there is one, not
    # whatever `@{upstream}` happens to be. A branch created with
    # `git switch -c <name> origin/main` tracks origin/main, so once it is
    # squash-merged its commit is in no upstream and the branch reads as
    # "1 unpushed commit" — a false HOLD on work that is finished. Observed
    # on this tool's own release branch.
    upstream = None
    if git(wt.path, "rev-parse", "--verify", "-q", f"refs/remotes/origin/{wt.branch}")[0]:
        upstream = f"origin/{wt.branch}"
    else:
        ok, tracked = git(wt.path, "rev-parse", "--abbrev-ref", "@{upstream}")
        if ok and tracked and tracked != f"origin/{repo.base}":
            upstream = tracked
    if upstream:
        ok, ahead = git(wt.path, "rev-list", "--count", f"{upstream}..HEAD")
        if not ok:
            wt.verdict, wt.reason = UNKNOWN, "could not compare against upstream"
            return False
        if ahead != "0":
            wt.verdict, wt.reason = HOLD, f"{ahead} unpushed commit(s){stale_note(repo)}"
            return False
        wt.pushed = "remote-ref"
        return True

    # No remote ref of its own. After --prune that is what every merged GitHub
    # branch looks like, so it is NOT "never pushed" yet. Two proofs remain:
    # HEAD already sits on origin/<base> (fast-forward, or the branch was reset
    # to the squash commit), or -- decided later, with the forge's answer --
    # the merged PR's head sha IS this HEAD.
    ok, _ = git(wt.path, "merge-base", "--is-ancestor", "HEAD", f"origin/{repo.base}")
    wt.pushed = "on-base" if ok else "pr-head"
    return True


def classify(wt: Worktree, repo: Repo):
    if not local_gates(wt, repo):
        return

    pr = lookup_pr(repo, wt.branch)
    if pr is None:
        wt.verdict, wt.reason = UNKNOWN, f"{repo.forge} unreachable -- refusing to guess"
        return
    if pr.get("state") == "NO-PR":
        if wt.pushed == "pr-head":
            wt.verdict, wt.reason = HOLD, "no remote ref and no pull request -- never pushed"
        else:
            wt.verdict, wt.reason = HOLD, f"no pull request found (none open, none merged into {repo.base})"
        return

    wt.pr = f"#{pr.get('number')}:{pr.get('state')}"
    # A PR whose base is another feature branch is stacked: merging it lands
    # nothing on <base>, so say so -- the reader otherwise assumes main.
    into = f" into {pr['base']}" if pr.get("base") and pr["base"] != repo.base else ""
    if pr.get("state") != "MERGED":
        wt.verdict, wt.reason = HOLD, f"PR #{pr.get('number')} is {pr.get('state').lower()}{into}"
        return
    if into:
        wt.verdict, wt.reason = HOLD, f"PR #{pr.get('number')} merged{into}, not {repo.base}"
        return

    if wt.pushed == "pr-head":
        # The only remaining proof that this HEAD ever left the machine.
        head_sha = pr.get("head_sha", "")
        if not head_sha:
            wt.verdict, wt.reason = UNKNOWN, "no remote ref, and forge gave no PR head to compare"
            return
        if head_sha != wt.head:
            wt.verdict = HOLD
            wt.reason = (f"PR #{pr.get('number')} merged at {head_sha[:12]} but HEAD is "
                         f"{wt.head[:12]} -- local commits after the merge?")
            return

    sha = pr.get("merge_sha", "")
    if not repo.has_vtags:
        # a repo with zero v* tags ships on merge (Flux, say), so a release
        # gate there would mean nothing is ever swept. Merge is the release.
        wt.verdict = SWEEP
        wt.reason = f"PR #{pr.get('number')} merged (repo has no release tags)"
        return

    if not sha:
        wt.verdict, wt.reason = UNKNOWN, "merged, but forge returned no merge commit"
        return
    ok, _ = git(repo.path, "cat-file", "-e", sha + "^{commit}")
    if not ok:
        git(repo.path, "fetch", "origin", "--tags", "-q")
        ok, _ = git(repo.path, "cat-file", "-e", sha + "^{commit}")
        if not ok:
            wt.verdict, wt.reason = UNKNOWN, f"merge commit {sha[:12]} not present locally"
            return
    ok, tags = git(repo.path, "tag", "--contains", sha)
    if not ok:
        wt.verdict, wt.reason = UNKNOWN, "could not read tags"
        return
    vtags = [t for t in tags.splitlines() if t.startswith("v")]
    if not vtags:
        wt.verdict = HOLD
        wt.reason = f"PR #{pr.get('number')} merged, awaiting a release tag"
        return
    wt.release = sorted(vtags)[-1]
    wt.verdict = SWEEP
    wt.reason = f"PR #{pr.get('number')} merged, released in {wt.release}"


# actions


def du_kb(path: Path) -> int:
    ok, out = run(["du", "-sk", str(path)], timeout=180)
    if ok and out:
        try:
            return int(out.split()[0])
        except (ValueError, IndexError):
            pass
    return 0


def measure(wt: Worktree):
    wt.size_kb = du_kb(wt.path)


def human(kb: int) -> str:
    if kb <= 0:
        return "-"
    for unit, div in (("G", 1024 * 1024), ("M", 1024)):
        if kb >= div:
            return f"{kb / div:.1f}{unit}"
    return f"{kb}K"


def log(msg: str):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as fh:
        fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {msg}\n")


# processes rooted in a worktree
#
# Nothing stops a process when its checkout goes away. Claude Code's LSP tool
# runs `fleet-lsp serve <language>`, which starts one server per worktree it is
# asked about (rust-analyzer, gopls, pyright, the TypeScript server): on
# 2026-10-29 twelve rust-analyzers of deleted worktrees held enough memory that
# swap was 20 of 21.5 GB. Test browsers, dev servers and shells started from a
# worktree outlive it the same way, and so do chrome-devtools-mcp servers whose
# session ended. So a removal stops what runs in the worktree it removes, and
# every run lists -- with --apply, stops -- what runs from a deleted worktree
# this sweep owns. A live Claude session, its MCP tools, and anything above the
# sweep are never touched.

# How long a SIGTERMed tree gets to exit before SIGKILL.
GRACE_SECONDS = 3
# removed.jsonl: worktrees this tool removed, kept beside state.json so a
# process left in one is still known to be ours after git forgot the worktree.
REMOVED_FILE = STATE_DIR / "removed.jsonl"
REMOVED_DAYS = 14
LSP_PARENT = "fleet-lsp"
BROWSER_NAMES = {"chrome-headless-shell", "chrome", "Chromium", "Google Chrome",
                 "Google Chrome for Testing"}
BROWSER_FLAGS = ("--remote-debugging-pipe", "--remote-debugging-port", "--headless")
MCP_NAME = "chrome-devtools-mcp"
MCP_WRAPPERS = {"node", "npm", "npx"}
REAPERS = {"launchd", "systemd"}
PROFILE_PREFIXES = ("playwright_", "puppeteer_")
LSTART_FORMAT = "%a %b %d %H:%M:%S %Y"


def c_locale_env() -> dict:
    """The environment with LC_ALL=C (never a bare dict, which drops PATH):
    ps prints lstart in the locale's language otherwise."""
    return {**os.environ, "LC_ALL": "C"}


@dataclass
class Proc:
    pid: int
    ppid: int
    start: str
    comm: str
    args: str
    cwd: Path | None = None


def argv0(proc: Proc) -> str:
    """argv[0]. macOS reports comm as the full path, spaces included, and args
    starts with it; Linux truncates comm to 15 bytes, so args is read instead."""
    args, comm = proc.args or proc.comm, proc.comm
    if comm and args.startswith(comm) and (len(args) == len(comm) or args[len(comm)] in " \t"):
        return comm
    first = args.split(None, 1)
    return first[0] if first else comm


def pname(proc: Proc) -> str:
    """The basename of argv[0]."""
    return os.path.basename(argv0(proc))


def _parse_start_comm(rest: str):
    """'<24-char lstart><comm>' -> (start, comm), or None when lstart is not a
    date (a row shifted by an odd comm is dropped, never guessed at)."""
    rest = rest.lstrip()
    start, comm = rest[:24], rest[24:].strip()
    try:
        time.strptime(start, LSTART_FORMAT)
    except ValueError:
        return None
    return start, comm


def parse_ps(table_out: str, args_out: str) -> dict[int, Proc]:
    """`ps -Ao pid=,ppid=,lstart=,comm=` joined by pid with `ps -Aww -o pid=,args=`."""
    args_by_pid: dict[int, str] = {}
    for line in args_out.splitlines():
        parts = line.split(None, 1)
        if parts and parts[0].isdigit():
            args_by_pid[int(parts[0])] = parts[1].strip() if len(parts) > 1 else ""
    table: dict[int, Proc] = {}
    for line in table_out.splitlines():
        parts = line.split(None, 2)
        if len(parts) < 3 or not parts[0].isdigit() or not parts[1].isdigit():
            continue
        parsed = _parse_start_comm(parts[2])
        if parsed is None:
            continue
        pid = int(parts[0])
        table[pid] = Proc(pid, int(parts[1]), parsed[0], parsed[1], args_by_pid.get(pid) or parsed[1])
    return table


def parse_lsof(out: str) -> dict[int, Path]:
    cwds: dict[int, Path] = {}
    current = None
    for line in out.splitlines():
        if line.startswith("p") and line[1:].isdigit():
            current = int(line[1:])
        elif line.startswith("n") and current is not None:
            name = line[1:]
            if name.endswith(" (deleted)"):       # Linux marks a removed cwd
                name = name[:-len(" (deleted)")]
            cwds[current] = Path(name)
    return cwds


def read_procs() -> dict[int, Proc] | None:
    """The process table with each working directory, or None when it cannot
    be read (callers that gate a removal then refuse)."""
    env = c_locale_env()
    ok, table_out = run(["ps", "-Ao", "pid=,ppid=,lstart=,comm="], timeout=30, env=env)
    args_ok, args_out = run(["ps", "-Aww", "-o", "pid=,args="], timeout=30, env=env)
    if not (ok and args_ok):
        return None
    table = parse_ps(table_out, args_out)
    if not table:
        return None
    _, lsof_out = run(["lsof", "-a", "-d", "cwd", "-Fpn"], timeout=60)  # exits 1 on partial output
    if not lsof_out:
        return None
    for pid, cwd in parse_lsof(lsof_out).items():
        if pid in table:
            table[pid].cwd = cwd
    return table


def reread(pid: int):
    """(start, comm) of one pid right now, or None when it is gone."""
    ok, out = run(["ps", "-o", "lstart=,comm=", "-p", str(pid)], timeout=30, env=c_locale_env())
    return _parse_start_comm(out) if ok and out else None


def _table(procs) -> dict[int, Proc]:
    return procs if isinstance(procs, dict) else {proc.pid: proc for proc in procs}


def _children(table: dict[int, Proc]) -> dict[int, list[int]]:
    kids: dict[int, list[int]] = {}
    for proc in table.values():
        kids.setdefault(proc.ppid, []).append(proc.pid)
    return kids


def _ancestors(pid: int, table: dict[int, Proc]) -> list[int]:
    out, seen = [], {pid}
    cur = table.get(pid)
    while cur is not None and cur.ppid not in seen and cur.ppid in table:
        out.append(cur.ppid)
        seen.add(cur.ppid)
        cur = table[cur.ppid]
    return out


def _descendants(pid: int, table: dict[int, Proc]) -> list[int]:
    kids = _children(table)
    out, frontier, seen = [], [pid], {pid}
    while frontier:
        nxt = [child for node in frontier for child in kids.get(node, []) if child not in seen]
        seen.update(nxt)
        out.extend(nxt)
        frontier = nxt
    return out


def _is_browser(proc: Proc) -> bool:
    return pname(proc) in BROWSER_NAMES and any(flag in proc.args for flag in BROWSER_FLAGS)


def _is_mcp_wrapper(proc: Proc) -> bool:
    return MCP_NAME in proc.args and pname(proc) in MCP_WRAPPERS


def classify_proc(proc: Proc, table) -> str:
    """lsp | browser | mcp | process. Pure."""
    table = _table(table)
    parent = table.get(proc.ppid)
    if parent is not None and pname(parent) == LSP_PARENT:
        return "lsp"
    if _is_browser(proc):
        return "browser"
    if MCP_NAME in proc.args:
        return "mcp"
    return "process"


def _wrapper_top(proc: Proc, table: dict[int, Proc]) -> Proc:
    cur, seen = proc, {proc.pid}
    while True:
        parent = table.get(cur.ppid)
        if parent is None or parent.pid in seen or not _is_mcp_wrapper(parent):
            return cur
        seen.add(parent.pid)
        cur = parent


def protected(procs, self_pid: int) -> set[int]:
    """What a sweep never signals: itself and everything above it, every claude
    and everything above it, and the chrome-devtools-mcp servers of a live
    claude with their npm wrapper and Chrome. fleet-lsp and its children are
    not protected, nor is a test runner under claude."""
    table = _table(procs)
    out = {self_pid, *_ancestors(self_pid, table)}
    claudes = {proc.pid for proc in table.values() if pname(proc) == "claude"}
    for pid in claudes:
        out.add(pid)
        out.update(_ancestors(pid, table))
    for proc in table.values():
        if _is_mcp_wrapper(proc) and claudes.intersection(_ancestors(proc.pid, table)):
            top = _wrapper_top(proc, table)
            out.add(top.pid)
            out.update(_descendants(top.pid, table))
    return out


# removed.jsonl

def _real(path) -> Path:
    return Path(os.path.realpath(str(path)))


def _exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return True                        # unknown is treated as present


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def record_removed(wt: "Worktree") -> bool:
    """One append-only line per removal, written BEFORE git forgets the
    worktree. A single O_APPEND write, so concurrent sweeps cannot interleave.
    Returns whether the line was written."""
    line = json.dumps({"path": str(wt.path), "primary": str(wt.primary), "time": time.time()}) + "\n"
    try:
        REMOVED_FILE.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(REMOVED_FILE, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(descriptor, line.encode())
        finally:
            os.close(descriptor)
    except OSError:
        return False
    return True


def read_removed(now: float | None = None) -> dict[Path, Path | None]:
    """Recent removed worktrees, each with the primary it was recorded under
    (None for an older line that has no primary)."""
    now = time.time() if now is None else now
    out: dict[Path, Path | None] = {}
    try:
        text = REMOVED_FILE.read_text()
    except OSError:
        return out
    for line in text.splitlines():
        try:
            rec = json.loads(line)
            path, ts = rec["path"], float(rec["time"])
        except (ValueError, KeyError, TypeError):
            continue
        if isinstance(path, str) and path and now - ts <= REMOVED_DAYS * 86400:
            primary = rec.get("primary") if isinstance(rec, dict) else None
            key = _real(path)
            if isinstance(primary, str) and primary:
                out[key] = _real(primary)
            else:
                out.setdefault(key, None)
    return out


@dataclass
class Owners:
    """Which paths this sweep may call its own: worktrees git registers, ones
    it removed (removed.jsonl), and `<repo>-wt-*` siblings of a scanned repo."""
    roots: set[Path] = field(default_factory=set)
    primaries: set[Path] = field(default_factory=set)

    def root_of(self, cwd: Path) -> Path | None:
        """The deepest owned root (or primary checkout) containing cwd."""
        found = [root for root in (*self.roots, *self.primaries) if _within_real(cwd, root)]
        for prim in self.primaries:
            if _within_real(cwd, prim.parent) and cwd != prim.parent:
                top = cwd.relative_to(prim.parent).parts[0]
                if top.startswith(f"{prim.name}-wt-"):
                    found.append(prim.parent / top)
        return max(found, key=lambda root: len(root.parts)) if found else None


def _within_real(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _owners(repos: list["Repo"], removed: dict[Path, Path | None]) -> Owners:
    primaries = {_real(repo.path) for repo in repos}
    roots = {_real(worktree.path) for repo in repos for worktree in repo.worktrees} | set(removed)
    return Owners(roots, primaries)


def collect_owners(repos: list["Repo"]) -> Owners:
    """Owners of the given repos, and every removed.jsonl entry."""
    return _owners(repos, read_removed())


def collect_scoped_owners(repos: list["Repo"]) -> Owners:
    """Owners of the given repos only: a removed.jsonl entry counts when its
    recorded primary is one of them, so an entry with no primary belongs to
    none of them."""
    primaries = {_real(repo.path) for repo in repos}
    removed = {path: prim for path, prim in read_removed().items() if prim in primaries}
    return _owners(repos, removed)


# selections (pure)

def _top_level(cands: list[Proc], table: dict[int, Proc]) -> list[Proc]:
    pids = {proc.pid for proc in cands}
    return [proc for proc in cands if not pids.intersection(_ancestors(proc.pid, table))]


def rooted(procs, root: Path, prot: set[int] | None = None) -> list[Proc]:
    """Top-level unprotected processes whose cwd is inside root."""
    table = _table(procs)
    prot = protected(table, os.getpid()) if prot is None else prot
    cands = [proc for proc in table.values()
             if proc.pid not in prot and proc.cwd is not None and _within(proc.cwd, root)]
    return _top_level(cands, table)


def _gone(procs, owners: Owners, prot: set[int] | None):
    """(table, [(proc, owning root or None)]) for unprotected processes whose
    cwd is gone and is not a missing subdirectory of a checkout that exists."""
    table = _table(procs)
    prot = protected(table, os.getpid()) if prot is None else prot
    out = []
    for proc in table.values():
        if proc.pid in prot or proc.cwd is None:
            continue
        cwd = _real(proc.cwd)
        if _exists(cwd):
            continue
        root = owners.root_of(cwd)
        if root is not None and _exists(root):
            continue                       # a deleted build/ in a live checkout
        out.append((proc, root))
    return table, out


def orphans(procs, owners: Owners, prot: set[int] | None = None) -> list[Proc]:
    """Top-level unprotected processes inside an owned worktree that is gone."""
    table, gone = _gone(procs, owners, prot)
    return _top_level([proc for proc, root in gone if root is not None], table)


def unowned_orphans(procs, owners: Owners, prot: set[int] | None = None) -> list[Proc]:
    """Gone cwd of unknown ownership: reported, never stopped."""
    table, gone = _gone(procs, owners, prot)
    return _top_level([proc for proc, root in gone if root is None], table)


def orphan_mcp(procs, table=None, prot: set[int] | None = None) -> list[Proc]:
    """chrome-devtools-mcp servers whose session is gone: the chain above them,
    walked only through wrappers naming the server, ends at the reaper. Each is
    returned as its highest wrapper, never the reaper. A parent that is some
    other live program (claude, an editor) leaves the server alone."""
    table = _table(table if table is not None else procs)
    prot = set() if prot is None else prot
    out: dict[int, Proc] = {}
    for proc in _table(procs).values():
        if MCP_NAME not in proc.args or proc.pid in prot:
            continue
        top = _wrapper_top(proc, table)
        parent = table.get(top.ppid)
        if top.pid in prot or parent is None:
            continue
        if parent.pid == 1 or top.ppid == 1 or pname(parent) in REAPERS:
            out[top.pid] = top
    return _top_level(list(out.values()), table)


# stopping

def profile_dir(proc: Proc, tmpdir: Path) -> Path | None:
    """The throwaway profile of a test browser (--user-data-dir): a real
    directory, not a symlink, named playwright_* or puppeteer_*, directly under
    the resolved $TMPDIR. Anything else is not ours to delete."""
    if not _is_browser(proc):
        return None
    match = re.search(r"--user-data-dir(?:=|\s+)(\S+)", proc.args)
    if not match:
        return None
    raw = Path(match.group(1))
    try:
        if raw.is_symlink() or not raw.is_dir():
            return None
        real, tmp = raw.resolve(), Path(tmpdir).resolve()
    except OSError:
        return None
    if real.parent != tmp or not real.name.startswith(PROFILE_PREFIXES):
        return None
    return real


def _tmpdir() -> Path:
    return Path(os.environ.get("TMPDIR") or tempfile.gettempdir())


KILL_WAIT_SECONDS = 1.0


def stop_tree(top: Proc, kind: str, why: str) -> bool:
    """SIGTERM the process and what it started, then SIGKILL what is still
    there after GRACE_SECONDS. Each pid is re-read just before it is signalled:
    one whose comm or start time changed (a reused pid) or that is protected
    is skipped. fleet-lsp starts a fresh server if the checkout is asked about
    again."""
    import signal

    def not_stopped(why_not: str) -> bool:
        log(f"PROC-NOT-STOPPED pid={top.pid} comm={os.path.basename(top.comm)} ({why_not})")
        return False

    fresh = read_procs()
    if fresh is None:
        return not_stopped("could not read the process table")
    prot = protected(fresh, os.getpid())
    members = [top]
    members += [fresh[pid] for pid in _descendants(top.pid, fresh) if pid in fresh]

    def unchanged(proc: Proc) -> bool:
        now = reread(proc.pid)
        return now is not None and now == (proc.start, proc.comm)

    if top.pid in prot:
        return not_stopped("protected")
    if not unchanged(top):
        return not_stopped("pid gone or reused")
    live = [proc for proc in members if proc.pid not in prot and unchanged(proc)]
    profiles = [profile for proc in live if (profile := profile_dir(proc, _tmpdir())) is not None]
    for proc in live:
        try:
            os.kill(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError:
            return not_stopped(f"permission denied signalling pid {proc.pid}")
    deadline = time.time() + GRACE_SECONDS
    while time.time() < deadline and any(pid_alive(proc.pid) for proc in live):
        time.sleep(0.1)
    for proc in live:
        if pid_alive(proc.pid) and unchanged(proc):
            try:
                os.kill(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    deadline = time.time() + KILL_WAIT_SECONDS
    while time.time() < deadline and any(pid_alive(proc.pid) for proc in live):
        time.sleep(0.05)
    cwd = top.cwd
    if any(pid_alive(proc.pid) for proc in live):
        for profile in dict.fromkeys(profiles):
            log(f"PROFILE-KEPT {profile}: still running")
        return not_stopped("still alive after SIGKILL")
    log(f"PROC-STOPPED kind={kind} pid={top.pid} comm={os.path.basename(top.comm)} cwd={cwd} ({why})")
    for profile in dict.fromkeys(profiles):
        try:
            shutil.rmtree(profile)
            log(f"PROFILE-REMOVED {profile}")
        except OSError as error:
            log(f"PROFILE-KEPT {profile}: {error}")
    return True


_SNAPSHOT: list | None = None          # [table] once an audit has begun
_SNAPSHOT_LOCK = threading.Lock()


def begin_audit():
    """Share one process-table read among the audit's gates."""
    global _SNAPSHOT
    with _SNAPSHOT_LOCK:
        _SNAPSHOT = []


def audit_snapshot():
    """The table for the gates: read once per audit after begin_audit(), else
    read each time. The removal re-reads its own."""
    with _SNAPSHOT_LOCK:
        if _SNAPSHOT is None:
            return read_procs()
        if not _SNAPSHOT:
            _SNAPSHOT.append(read_procs())
        return _SNAPSHOT[0]


def session_gate(path: Path):
    """The gate `a live session works here`, run on a fresh table right before
    a removal. Returns (table, "") when clear, else (None, reason): HOLD when a
    claude process sits in path, and a refusal when that cannot be evaluated."""
    return session_verdict(read_procs(), path)


def session_verdict(table, path: Path):
    """session_gate evaluated against a given table."""
    if table is None:
        return None, "could not evaluate whether a live session works here"
    for proc in table.values():
        if pname(proc) != "claude":
            continue
        if proc.cwd is None:
            return None, "could not evaluate whether a live session works here"
        if _within(proc.cwd, path):
            return None, "a live session works here"
    return table, ""


def in_scope(repos: list["Repo"], name: str | None) -> list["Repo"]:
    """The repositories --repo selects (all of them without it)."""
    return [r for r in repos if r.path.name == name] if name else repos


def report_procs(apply: bool, repos: list["Repo"], name: str | None = None) -> int:
    """Print and (with apply) stop processes of deleted checkouts. Ownership is
    computed over every repo given; name keeps only orphans owned by that repo,
    and an orphan owned by an out-of-scope repo is neither printed nor counted.
    Returns how many it reported, or -1 when the process table cannot be read."""
    table = read_procs()
    if table is None:
        print("[worktree-sweep] could not read the process table; skipping processes.",
              file=sys.stderr)
        return -1
    prot = protected(table, os.getpid())
    owners = collect_owners(repos)
    scoped = collect_scoped_owners(in_scope(repos, name)) if name else owners

    def in_scope_proc(proc: Proc) -> bool:
        return proc.cwd is not None and scoped.root_of(_real(proc.cwd)) is not None
    found = {proc.pid: (proc, "checkout gone")
             for proc in orphans(table, owners, prot) if in_scope_proc(proc)}
    for proc in orphan_mcp(table, table, prot):
        found.setdefault(proc.pid, (proc, "orphaned chrome-devtools-mcp"))
    keep = {proc.pid for proc in _top_level([proc for proc, _ in found.values()], table)}
    found = {pid: entry for pid, entry in found.items() if pid in keep}
    unowned = unowned_orphans(table, owners, prot)
    if not found and not unowned:
        return 0
    print()
    for proc, _ in found.values():
        print(f"ORPHAN-PROC {classify_proc(proc, table)} pid {proc.pid} {os.path.basename(proc.comm)} {proc.cwd}")
    for proc in unowned:
        print(f"ORPHAN-UNOWNED pid {proc.pid} {os.path.basename(proc.comm)} {proc.cwd}")
    if not found:
        return len(unowned)
    if not apply:
        print(f"{len(found)} process(es) of deleted checkouts — re-run with --apply to stop them.")
        return len(found) + len(unowned)
    stopped = sum(stop_tree(proc, classify_proc(proc, table), why) for proc, why in found.values())
    print(f"Stopped {stopped} process(es) of deleted checkouts.")
    return len(found) + len(unowned)


def refuse_unrecorded(wt: Worktree) -> tuple[bool, str]:
    """Without the removed.jsonl line, a process left in the worktree could
    never be told apart from a stranger's after git forgets it: refuse."""
    reason = "could not record the removal in removed.jsonl"
    print(f"[worktree-sweep] {wt.path}: {reason}; not removed.", file=sys.stderr)
    try:
        log(f"REMOVAL-REFUSED {wt.path}: {reason}")
    except OSError:
        pass  # stderr already has it; the log shares the disk that just failed
    return False, reason


def remove(wt: Worktree, prune_branch: bool = False) -> tuple[bool, str]:
    """Remove a SWEEP worktree. Never --force: an unexpected untracked file
    must abort the removal, not be bulldozed."""
    if wt.prunable or not wt.path.exists():
        # Owned processes are stopped BEFORE the prune: once git forgets the
        # registration, only removed.jsonl still says the path was ours.
        if not record_removed(wt):
            return refuse_unrecorded(wt)
        # git can mark a worktree prunable while its directory remains: that
        # directory is not deleted, so what runs in it is left alone.
        table = read_procs() if not wt.path.exists() else None
        if table is not None:
            for proc in rooted(table, wt.path):
                if not stop_tree(proc, classify_proc(proc, table), f"worktree {wt.path} registration pruned"):
                    log(f"PROC-NOT-STOPPED pid={proc.pid} left after pruning {wt.path}")
        ok, _ = git(wt.primary, "worktree", "prune")
        if ok:
            log(f"PRUNED {wt.path} (stale registration)")
            return True, "pruned"
        return False, "prune failed"

    # A fresh look right before the removal: a session may have started in this
    # worktree since the audit began (a forge lookup can take minutes).
    table, why = session_gate(wt.path)
    if table is None:
        wt.verdict, wt.reason = (HOLD if why.startswith("a live") else UNKNOWN), why
        return False, why

    if wt.drop:
        # Generated guidance edits (DROPPABLE_DIRTY), the only dirt the gates
        # let through. Restore them, never --force the removal.
        ok, _ = git(wt.path, "restore", "--staged", "--worktree", "--source=HEAD", "--", *wt.drop)
        if not ok:
            return False, f"could not discard edits to {', '.join(wt.drop)}"
        log(f"DROPPED {wt.path} uncommitted {' '.join(wt.drop)}")

    # Read before removal: once the directory is gone, a process's cwd can no
    # longer be resolved against it.
    rooted_here = rooted(table, wt.path)
    if not record_removed(wt):
        return refuse_unrecorded(wt)
    ok, out = run(["git", "-C", str(wt.primary), "worktree", "remove", str(wt.path)])
    if not ok:
        return False, "git worktree remove refused"
    for proc in rooted_here:
        if not stop_tree(proc, classify_proc(proc, table), f"worktree {wt.path} removed"):
            log(f"PROC-NOT-STOPPED pid={proc.pid} left after removing {wt.path}")
    detail = f"released={wt.release}" if wt.release else "no-release-tag-gate"
    if wt.pushed == "" and wt.reason.startswith("HEAD on origin/"):
        detail = "content-gate"
    log(f"REMOVED {wt.path} branch={wt.branch} pr={wt.pr} {detail}")
    if wt.branch and prune_branch:
        # `-D`, not `-d`: both forges squash-merge, so `-d` always refuses.
        # Off by default -- GitHub deletes the remote branch on merge (verified:
        # amont fix/trust-per-worktree 404s), so the local ref can be the last
        # named handle on the pre-squash commits. They stay reachable via
        # refs/pull/<n>/head and the object store, but a branch ref is free and
        # a worktree is not: the disk win is the worktree, so keep the ref.
        git(wt.primary, "branch", "-D", wt.branch)
        log(f"BRANCH-DELETED {wt.branch} in {wt.primary}")
    return True, "removed"


# reporting


def save_state(repos: list[Repo]):
    """Persist the audit for --nudge to read.

    A run in which every forge lookup failed (forge down, laptop offline) carries
    no information -- it says UNKNOWN about everything. Writing that over a good
    snapshot would make --nudge go quiet for a week and hide real accumulation,
    so a wholly-degraded run leaves the previous state alone.
    """
    live = [w for r in repos for w in r.worktrees if w.path.exists()]
    forge_answered = [w for w in live if w.pr or "unreachable" not in w.reason]
    if live and not forge_answered and STATE_FILE.exists():
        print("[worktree-sweep] every forge lookup failed — keeping the previous "
              "snapshot rather than recording a blind one.", file=sys.stderr)
        return
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    fresh = [
        {
            "path": str(w.path), "repo": r.path.name, "branch": w.branch,
            "verdict": w.verdict, "reason": w.reason, "pr": w.pr,
            "release": w.release, "size_kb": w.size_kb,
        }
        for r in repos for w in r.worktrees
        if w.path.exists()
    ]
    ts = time.time()
    if REPO_SCOPE is not None:
        # A `--repo X` run (worktree-task's finish step) audited one repo. It
        # used to overwrite the whole snapshot with that repo alone -- 3 of 60
        # worktrees seen 2026-10-07 -- blinding --nudge to every other repo.
        # Replace only X's entries, and keep the previous timestamp: the
        # other repos were not re-audited, so the snapshot is no fresher.
        try:
            old = json.loads(STATE_FILE.read_text())
        except (OSError, json.JSONDecodeError):
            old = None
        if old is None:
            return                         # no full audit to amend; a partial one is not a snapshot
        kept = [w for w in old.get("worktrees", []) if w.get("repo") != REPO_SCOPE]
        fresh = kept + fresh
        ts = old.get("ts", ts)
    STATE_FILE.write_text(json.dumps({"ts": ts, "worktrees": fresh}, indent=2))


def count_linked_worktrees(roots) -> int:
    """Linked worktrees of every primary under roots, wherever they live.

    Reads each primary's .git/worktrees/ registrations instead of globbing for
    .git files under the roots: a worktree made in /tmp or a scratchpad is
    registered there but sits nowhere under ~/Developer. A stale registration
    (path gone) counts too -- it is exactly what the sweep prunes."""
    n = 0
    for primary in find_primaries(roots):
        reg = primary / ".git" / "worktrees"
        try:
            n += sum(1 for d in reg.iterdir() if (d / "gitdir").is_file())
        except OSError:
            pass
    return n


def nudge():
    """Fast, offline, silent-unless-actionable. Runs as a SessionStart hook, so
    it must never make a network call and must never delete anything."""
    scratch_nudge()
    n_wt = count_linked_worktrees(DEFAULT_ROOTS)
    if n_wt == 0:
        return 0
    stale_days = None
    if STATE_FILE.exists():
        try:
            ts = json.loads(STATE_FILE.read_text()).get("ts", 0)
            stale_days = int((time.time() - ts) / 86400)
        except (json.JSONDecodeError, OSError):
            pass
    if stale_days is not None and stale_days < 7:
        try:
            data = json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            data = {"worktrees": []}
        sweepable = [w for w in data.get("worktrees", []) if w.get("verdict") == SWEEP]
        if not sweepable:
            return 0
        kb = sum(w.get("size_kb", 0) for w in sweepable)
        print(f"[worktree-sweep] {len(sweepable)} worktree(s) sweepable, {human(kb)} — run /worktree-sweep")
        return 0
    when = "never" if stale_days is None else f"{stale_days}d ago"
    print(f"[worktree-sweep] {n_wt} linked worktree(s); last swept {when} — run /worktree-sweep")
    return 0


# Claude Code scratch session directories
#
# Claude Code keeps per-session temp state at
#   <tmp root>/<project slug>/<session id>/{scratchpad,tasks}
# where <tmp root> is $CLAUDE_CODE_TMPDIR/claude-<uid>, defaulting to
# /tmp/claude-<uid> (deliberately not $TMPDIR -- on macOS that is
# /var/folders/...; the override is named in the binary's own messages).
# The matching transcript is ~/.claude/projects/<slug>/<session id>.jsonl,
# and its mtime is the best "last active" signal: it is written on every turn,
# including on a resume, while the scratch dir may sit untouched for hours.

SCRATCH_DAYS = 7
PROJECTS_DIR = HOME / ".claude" / "projects"
SESSION_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def scratch_root() -> Path:
    base = os.environ.get("CLAUDE_CODE_TMPDIR") or "/tmp"
    return Path(base) / f"claude-{os.getuid()}"


@dataclass
class ScratchDir:
    path: Path
    slug: str
    session: str
    last_active: float = 0.0
    size_kb: int = 0
    verdict: str = HOLD
    reason: str = ""

    @property
    def name(self) -> str:
        slug = self.slug if len(self.slug) <= 48 else "…" + self.slug[-47:]
        return f"{slug}/{self.session[:8]}"

    @property
    def idle_days(self) -> int:
        return int((time.time() - self.last_active) / 86400)


def list_scratch(root: Path) -> list[ScratchDir]:
    out: list[ScratchDir] = []
    try:
        slugs = [p for p in root.iterdir() if p.is_dir() and not p.is_symlink()]
    except OSError:
        return out
    for slug_dir in slugs:
        try:
            # Session ids are UUIDs; anything else is Claude Code's own state
            # (e.g. bundled-skills/<version>), not a session to judge.
            sessions = [p for p in slug_dir.iterdir()
                        if p.is_dir() and not p.is_symlink() and SESSION_ID_RE.match(p.name)]
        except OSError:
            continue
        for s in sessions:
            sd = ScratchDir(path=s, slug=slug_dir.name, session=s.name)
            # Directory mtimes are NOT activity: something prunes these dirs
            # nightly (observed: scratchpad/ and tasks/ of a 3-day-idle session
            # all stamped 00:00 today), and every deletion bumps the parent's
            # mtime. Trust the transcript; fall back to the dir only without one.
            try:
                sd.last_active = (PROJECTS_DIR / sd.slug / f"{sd.session}.jsonl").stat().st_mtime
            except OSError:
                try:
                    sd.last_active = s.stat().st_mtime
                except OSError:
                    continue
            out.append(sd)
    return out


def newest_file_mtime(top: Path) -> float:
    """Newest mtime of any non-directory under top, skipping .git internals.
    Directories are excluded for the reason given in list_scratch."""
    newest = 0.0
    for dirpath, dirnames, filenames in os.walk(top):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for n in filenames:
            try:
                newest = max(newest, os.lstat(os.path.join(dirpath, n)).st_mtime)
            except OSError:
                pass
    return newest


def git_checkouts(top: Path) -> list[tuple[Path, bool]]:
    """(checkout dir, is_linked_worktree) for every .git found under top."""
    found = []
    for dirpath, dirnames, filenames in os.walk(top):
        if ".git" in dirnames:
            found.append((Path(dirpath), False))
            dirnames.remove(".git")
        elif ".git" in filenames:
            found.append((Path(dirpath), True))
        dirnames[:] = [d for d in dirnames if d != "node_modules"]
    return found


def classify_scratch(sd: ScratchDir, days: int):
    """SWEEP only when idle past the threshold and nothing inside could be the
    last copy of real work. Gates, in order:

      1. not the session running this command ($CLAUDE_CODE_SESSION_ID);
      2. idle >= days, judged by the transcript AND the newest file inside;
      3. no linked worktree inside -- that belongs to a real repo and the
         worktree sweep's merge/release gates, not to a blind rmtree;
      4. every standalone repo inside that HAS a remote is clean and has no
         commit absent from its remotes. A repo with no remote was born in
         the scratchpad and is scratch by construction.
    Any git command that fails -> UNKNOWN, which is never removed."""
    if sd.session == os.environ.get("CLAUDE_CODE_SESSION_ID"):
        sd.verdict, sd.reason = HOLD, "current session"
        return
    if sd.idle_days >= days:               # only walk what the transcript calls idle
        sd.last_active = max(sd.last_active, newest_file_mtime(sd.path))
    if sd.idle_days < days:
        sd.verdict, sd.reason = HOLD, f"active {sd.idle_days}d ago (< {days}d)"
        return
    throwaway = 0
    for co, linked in git_checkouts(sd.path):
        rel = co.relative_to(sd.path)
        if linked:
            sd.verdict, sd.reason = HOLD, f"linked worktree at {rel} — leave it to the worktree sweep"
            return
        gitdir = co / ".git"
        if not (gitdir / "HEAD").exists() and not (gitdir / "config").exists():
            # Gutted by the nightly pruner (seen: only empty ci/ hooks/ refs/
            # dirs left). No config means no remote ever recorded here, and git
            # no longer opens it -- nothing reachable to lose.
            throwaway += 1
            continue
        # A primary whose linked worktree lives elsewhere: deleting it would
        # orphan that worktree (its .git file would point at nothing).
        for reg in (gitdir / "worktrees").glob("*/gitdir"):
            try:
                target = Path(reg.read_text().strip()).parent
            except OSError:
                continue
            if target.exists() and not target.resolve().is_relative_to(sd.path.resolve()):
                sd.verdict, sd.reason = HOLD, f"{rel} is the primary of live worktree {target}"
                return
        ok, remotes = git(co, "remote")
        if not ok:
            sd.verdict, sd.reason = UNKNOWN, f"git failed in {rel}"
            return
        if not remotes.strip():
            throwaway += 1
            continue
        ok_s, st = git(co, "status", "--porcelain")
        ok_u, unpushed = git(co, "rev-list", "--branches", "--tags", "--not", "--remotes")
        if not (ok_s and ok_u):
            sd.verdict, sd.reason = UNKNOWN, f"git failed in {rel}"
            return
        if st.strip():
            sd.verdict, sd.reason = HOLD, f"uncommitted changes in {rel} (has a remote)"
            return
        if unpushed.strip():
            n = len(unpushed.split())
            sd.verdict, sd.reason = HOLD, f"{n} commit(s) in {rel} not on any remote"
            return
    extra = f", {throwaway} remote-less scratch repo(s)" if throwaway else ""
    sd.verdict, sd.reason = SWEEP, f"idle {sd.idle_days}d{extra}"


def remove_scratch(sd: ScratchDir) -> tuple[bool, str]:
    try:
        shutil.rmtree(sd.path)
    except OSError as e:
        return False, f"rmtree failed: {e.strerror or e}"
    try:
        sd.path.parent.rmdir()             # the slug dir, only if now empty
    except OSError:
        pass
    log(f"SCRATCH-REMOVED {sd.path} idle={sd.idle_days}d size_kb={sd.size_kb}")
    return True, "removed"


def scratch_sweep(root: Path, days: int, apply: bool, as_json: bool) -> int:
    dirs = list_scratch(root)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda sd: classify_scratch(sd, days), dirs))
        sizes = list(pool.map(lambda sd: du_kb(sd.path), dirs))
    for sd, kb in zip(dirs, sizes):
        sd.size_kb = kb
    if as_json:
        print(json.dumps({"root": str(root), "days": days, "dirs": [
            {"path": str(sd.path), "verdict": sd.verdict, "reason": sd.reason,
             "idle_days": sd.idle_days, "size_kb": sd.size_kb} for sd in dirs]}, indent=2))
        return 0
    print(f"scratch root: {root}  (idle threshold {days}d)")
    if not dirs:
        print("No scratch session directories.")
        return 0
    order = {SWEEP: 0, UNKNOWN: 1, HOLD: 2}
    dirs.sort(key=lambda sd: (order[sd.verdict], -sd.size_kb))
    # Recently-active sessions are the bulk and need no reading: one line for all.
    active = [sd for sd in dirs if sd.verdict == HOLD and sd.reason.startswith("active ")]
    shown = [sd for sd in dirs if sd not in active]
    width = max((len(sd.name) for sd in shown), default=10)
    for sd in shown:
        mark = {SWEEP: "SWEEP  ", HOLD: "hold   ", UNKNOWN: "UNKNOWN"}[sd.verdict]
        print(f"{mark} {sd.name:<{width}}  {human(sd.size_kb):>6}  {sd.reason}")
    if active:
        print(f"hold    {len(active)} session dir(s) active within {days}d, "
              f"{human(sum(sd.size_kb for sd in active))}")
    sweepable = [sd for sd in dirs if sd.verdict == SWEEP]
    total = sum(sd.size_kb for sd in sweepable)
    print()
    if not sweepable:
        print("Nothing to sweep.")
        return 0
    if not apply:
        print(f"{len(sweepable)} sweepable, {human(total)} — re-run with --scratch --apply to remove.")
        return 0
    freed = 0
    for sd in sweepable:
        ok, what = remove_scratch(sd)
        print(f"  {'✓' if ok else '✗'} {sd.name}: {what}")
        if ok:
            freed += sd.size_kb
    print(f"\nFreed {human(freed)}. Log: {LOG_FILE}")
    return 0


def scratch_nudge():
    """Offline and stat-only: transcript + top-level mtimes, no git, no du.
    A hint, not a verdict -- the real gates run under --scratch."""
    me = os.environ.get("CLAUDE_CODE_SESSION_ID")
    idle = [sd for sd in list_scratch(scratch_root())
            if sd.session != me and sd.idle_days >= SCRATCH_DAYS]
    if idle:
        print(f"[worktree-sweep] {len(idle)} Claude scratch session dir(s) idle ≥{SCRATCH_DAYS}d "
              f"— run /worktree-sweep --scratch")


PRUNE_BRANCHES = False
# Set by --repo: the one repo this run audited, so save_state amends rather
# than replaces the snapshot.
REPO_SCOPE: str | None = None
# Every discovered repo (--root), worktree-less primaries included, even under
# --repo: ownership of a deleted worktree is judged against all of them, and
# report_procs does the --repo narrowing.
OWNER_REPOS: list | None = None
# The caller's directory, or None when it no longer exists — typically the
# worktree that `git worktree remove` deleted just before this sweep ran.
START_CWD: Path | None = None


def settle_cwd() -> Path | None:
    """Return the working directory; move to $HOME if it was deleted.

    A deleted cwd makes Path.cwd() raise and can make git refuse to start,
    and no worktree can contain a directory that no longer exists.
    """
    try:
        return Path.cwd().resolve()
    except FileNotFoundError:
        os.chdir(Path.home())
        return None


def report(repos: list[Repo], apply: bool):
    rows = [(r, w) for r in repos for w in r.worktrees]
    order = {SWEEP: 0, UNKNOWN: 1, HOLD: 2}
    rows.sort(key=lambda rw: (order[rw[1].verdict], rw[1].name))

    width = max((len(w.name) for _, w in rows), default=10)
    for _, w in rows:
        mark = {SWEEP: "SWEEP  ", HOLD: "hold   ", UNKNOWN: "UNKNOWN"}[w.verdict]
        print(f"{mark} {w.name:<{width}}  {human(w.size_kb):>6}  {w.reason}")

    sweepable = [(r, w) for r, w in rows if w.verdict == SWEEP]
    total = sum(w.size_kb for _, w in sweepable)
    print()
    if not sweepable:
        print("Nothing to sweep.")
        report_procs(apply, OWNER_REPOS or repos, REPO_SCOPE)
        return 0
    if not apply:
        print(f"{len(sweepable)} sweepable, {human(total)} — re-run with --apply to remove "
              f"(and stop what still runs in them).")
        report_procs(apply, OWNER_REPOS or repos, REPO_SCOPE)
        return 0

    freed = 0
    for _, w in sweepable:
        ok, what = remove(w, prune_branch=PRUNE_BRANCHES)
        print(f"  {'✓' if ok else '✗'} {w.name}: {what}")
        if ok:
            freed += w.size_kb
            w.verdict, w.reason, w.size_kb = HOLD, "removed by sweep", 0
    # Re-save: the pre-apply snapshot still lists everything just removed, and
    # --nudge reads that file. A stale cache here nags about work already done.
    save_state(repos)
    print(f"\nFreed {human(freed)}. Log: {LOG_FILE}")
    report_procs(apply, OWNER_REPOS or repos, REPO_SCOPE)
    return 0


# --prune-deps: regenerable dependency dirs in idle worktrees

# Directories a package manager or build tool recreates from the lockfile.
# Pruning one loses no work: `npm ci` / `pnpm install` / `cargo build` /
# `uv sync` put it back. Matched by name at any depth below the worktree,
# except under .git and except nested inside another match (node_modules
# inside node_modules is counted once, with its parent).
DEP_DIRS = {"node_modules", "target", ".venv", ".turbo", ".next", "dist", "build"}
# `target`, `dist` and `build` are also legitimate source dir names; only
# treat them as dependency output when the marker beside them says so.
DEP_MARKERS = {
    "target": ("Cargo.toml",),
    "dist": ("package.json",),
    "build": ("package.json",),
}
PRUNE_DEPS_DAYS = 3


@dataclass
class DepDir:
    wt: Worktree
    path: Path
    kind: str
    size_kb: int = 0


def find_dep_dirs(wt: Worktree) -> list[DepDir]:
    found: list[DepDir] = []
    for dirpath, dirnames, _ in os.walk(wt.path):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        hits = [d for d in dirnames if d in DEP_DIRS]
        for d in hits:
            markers = DEP_MARKERS.get(d)
            if markers and not any((Path(dirpath) / m).exists() for m in markers):
                continue
            found.append(DepDir(wt, Path(dirpath) / d, d))
        # don't descend into a matched dir: its contents belong to it
        dirnames[:] = [d for d in dirnames if d not in hits]
    return found


def worktree_idle_days(wt: Worktree) -> float:
    """Idle time from the newest *source* file, dependency dirs excluded --
    a fresh `npm install` must not make an untouched worktree look active."""
    newest = 0.0
    for dirpath, dirnames, filenames in os.walk(wt.path):
        dirnames[:] = [d for d in dirnames if d != ".git" and d not in DEP_DIRS]
        for n in filenames:
            try:
                newest = max(newest, os.lstat(os.path.join(dirpath, n)).st_mtime)
            except OSError:
                pass
    return (time.time() - newest) / 86400 if newest else 0.0


def prune_deps(repos: list[Repo], days: int, apply: bool) -> int:
    """Delete regenerable dependency dirs in worktrees idle >= days.
    Independent of the merge/release verdict: a HOLD worktree with open work
    keeps its source untouched; only what a lockfile recreates goes."""
    wts = [w for r in repos for w in r.worktrees if w.path.exists()]
    if START_CWD is not None:
        # Skip only the worktree the caller stands IN (cwd equals it or is
        # below it). A cwd *above* worktrees -- a directory that holds them
        # all -- must not exclude everything.
        wts = [w for w in wts if START_CWD != w.path and w.path not in START_CWD.parents]
    primaries = {r.path for r in repos}
    wts = [w for w in wts if w.path not in primaries]

    rows: list[tuple[DepDir, float]] = []
    for w in wts:
        deps = find_dep_dirs(w)
        if not deps:
            continue
        idle = worktree_idle_days(w)
        for d in deps:
            d.size_kb = du_kb(d.path)
            rows.append((d, idle))
    rows.sort(key=lambda r: -r[0].size_kb)

    def short(p: Path) -> str:
        try:
            return "~/" + str(p.relative_to(HOME))
        except ValueError:
            return str(p)

    width = max((len(short(d.path)) for d, _ in rows), default=10)
    prunable: list[DepDir] = []
    for d, idle in rows:
        if idle >= days:
            mark, note = "PRUNE  ", f"idle {idle:.1f}d"
            prunable.append(d)
        else:
            mark, note = "keep   ", f"active {idle:.1f}d ago"
        print(f"{mark} {short(d.path):<{width}}  {human(d.size_kb):>6}  {note}")

    total = sum(d.size_kb for d in prunable)
    print()
    if not prunable:
        print("Nothing to prune.")
        return 0
    if not apply:
        print(f"{len(prunable)} prunable, {human(total)} — re-run with --apply to delete "
              f"(regenerated by the package manager from the lockfile).")
        return 0

    freed = 0
    for d in prunable:
        try:
            shutil.rmtree(d.path)
        except OSError as e:
            print(f"  ✗ {d.path}: {e}")
            continue
        log(f"DEPS-PRUNED {d.path} kind={d.kind} size_kb={d.size_kb} worktree={d.wt.path}")
        print(f"  ✓ {short(d.path)}: {human(d.size_kb)}")
        freed += d.size_kb
    print(f"\nFreed {human(freed)}. Log: {LOG_FILE}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Sweep merged-and-released git worktrees.")
    ap.add_argument("--apply", action="store_true", help="remove SWEEP-verdict worktrees")
    ap.add_argument("--nudge", action="store_true", help="fast offline one-liner for a SessionStart hook")
    ap.add_argument("--prune-branches", action="store_true",
                    help="also delete the local branch ref after removing a worktree")
    ap.add_argument("--repo", help="limit to one repo (directory name)")
    ap.add_argument("--json", action="store_true", help="emit machine-readable state")
    ap.add_argument("--root", action="append", help="search root (default ~/Developer)")
    ap.add_argument("--lookup", nargs=2, metavar=("REPO", "BRANCH"),
                    help="debug: print the raw forge answer for one branch and exit")
    ap.add_argument("--scratch", action="store_true",
                    help="sweep idle Claude Code scratch session dirs instead of worktrees")
    ap.add_argument("--scratch-days", type=int, default=SCRATCH_DAYS,
                    help=f"idle threshold for --scratch (default {SCRATCH_DAYS})")
    ap.add_argument("--scratch-root", type=Path,
                    help="override the scratch root (default $CLAUDE_CODE_TMPDIR or /tmp, + /claude-<uid>)")
    ap.add_argument("--prune-deps", action="store_true",
                    help="delete regenerable dependency dirs (node_modules, target, .venv…) "
                         "in worktrees idle >= --deps-days; source is never touched")
    ap.add_argument("--deps-days", type=int, default=PRUNE_DEPS_DAYS,
                    help=f"idle threshold for --prune-deps (default {PRUNE_DEPS_DAYS})")
    ap.add_argument("--procs", "--lsp", dest="procs", action="store_true",
                    help="only list (with --apply, stop) processes still running from a deleted "
                         "worktree, and orphaned chrome-devtools-mcp servers; no forge lookups "
                         "(--lsp is the old name)")
    args = ap.parse_args()

    global PRUNE_BRANCHES, START_CWD, REPO_SCOPE, OWNER_REPOS
    PRUNE_BRANCHES = args.prune_branches
    START_CWD = settle_cwd()

    if args.nudge:
        return nudge()

    if not shutil.which("git"):
        print("git not found", file=sys.stderr)
        return 1

    if args.procs:
        if report_procs(args.apply, discover(args.root or DEFAULT_ROOTS, keep_empty=True),
                        args.repo) == 0:
            print("No processes of deleted checkouts.")
        return 0

    if args.scratch:
        return scratch_sweep(args.scratch_root or scratch_root(),
                             args.scratch_days, args.apply, args.json)

    every_repo = discover(args.root or DEFAULT_ROOTS, keep_empty=True)
    repos = [repo for repo in every_repo if repo.worktrees]
    if args.lookup:
        name, branch = args.lookup
        repo = next((r for r in repos if r.path.name == name), None)
        if repo is None:
            print(f"no repo with worktrees named {name!r}", file=sys.stderr)
            return 1
        print(json.dumps({"forge": repo.forge, "base": repo.base,
                          "pr": lookup_pr(repo, branch)}, indent=2))
        return 0
    OWNER_REPOS = every_repo
    if args.repo:
        REPO_SCOPE = args.repo
        repos = [r for r in repos if r.path.name == args.repo]

    if args.prune_deps:
        # No forge lookups: the verdict is irrelevant, only idleness matters.
        return prune_deps(repos, args.deps_days, args.apply)

    jobs = [(r, w) for r in repos for w in r.worktrees]
    begin_audit()
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda rw: classify(rw[1], rw[0]), jobs))
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda rw: measure(rw[1]), jobs))

    save_state(repos)
    if args.json:
        print(STATE_FILE.read_text())
        return 0
    return report(repos, args.apply)


if __name__ == "__main__":
    sys.exit(main())
