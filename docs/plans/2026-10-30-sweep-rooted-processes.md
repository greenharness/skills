---
canonical: github:fredericrous/decisions/docs/plans/2026-10-30-sweep-rooted-processes.md
phases: [1, 2]
status: active
branch: feat/sweep-rooted-processes
---
# worktree-sweep stops what still runs in a deleted worktree

Pointer. The plan and its review panel live in decisions. This repository
carries the change to `worktree-sweep` and the v0.1.1 release:

- every run lists the processes still running from a deleted worktree, and
  stops them with `--apply`: test browsers, servers and shells;
- a removal stops what runs in the worktree it removes;
- orphaned `chrome-devtools-mcp` servers are stopped too;
- a live Claude session, its own tools, and anything above the sweep are
  never touched.

## Verification

Observed on macOS, 2026-10-30, on tree 463d4c8.

| Check | Input | Expected | Actual |
|---|---|---|---|
| leak and NOTICE check | `scripts/check.sh` | exit 0 | exit 0 |
| compiles | `python3 -m py_compile sweep.py` | exit 0 | exit 0 |
| unit tests | `python3 -m unittest discover -s tests` | all pass | 45 tests OK |
| orphans in a deleted worktree | scratch home; a `sleep` and a fake `chrome-headless-shell --remote-debugging-pipe --user-data-dir=$TMPDIR/playwright_*` in `demo-wt-browser`, then `rm -rf`; `--procs`, then `--procs --apply` | both listed, then stopped; profile removed | `ORPHAN-PROC process` and `ORPHAN-PROC browser`; `PROC-STOPPED kind=process`, `kind=browser`; `PROFILE-REMOVED` |
| a live session in a deleted worktree | a fake `claude` with a fake `chrome-devtools-mcp` child, cwd in a deleted worktree | not listed, both alive | `No processes of deleted checkouts.`; both alive |
| removal path | `--repo demo --apply`: a merged worktree, idle over 24 h, with a `sleep` inside | removed, `sleep` stopped, recorded | `REMOVED`, `PROC-STOPPED kind=process`, a `removed.jsonl` line with its primary |
| held while a session works there | a worktree that is a fake `claude`'s cwd | HOLD | `hold … a live session works here`; session alive |
| an unowned gone cwd on the real machine | a `relais` test process whose temp cwd is gone | listed, never stopped | `ORPHAN-UNOWNED`, still running |
| cost | `lsof -a -d cwd -Fpn` and a full process read, 892 processes, load 16 | recorded | `lsof` 1.2–1.4 s; full read 2.7 s |

Fakes are symlinks to `/bin/bash`: macOS SIGKILLs a system binary copied
elsewhere. Every running Claude Code session showed `comm=claude` (9 of 9),
which the protection matches on.

## Implementation review

- Round 1: approve-with-changes, 77k tokens, 111 s. Six findings, five of them fixed in 463d4c8:
  - ownership follows `--repo` and `--root`;
  - the session check runs in the dry run;
  - failed stops are logged;
  - a kept profile is logged;
  - a forge-path test was added.
- Delta: approve-with-changes, 95k tokens, 49 s. The verification gaps (the session in a deleted worktree, the removal path, the cost) are recorded above.
- deliberate: the audit's process snapshot stays a module-level cache that each audit resets. Passing it through `classify` and `local_gates` would change several signatures and nothing in behaviour. A machine where `lsof` fails holds every worktree UNKNOWN, which is the plan's safe direction.
