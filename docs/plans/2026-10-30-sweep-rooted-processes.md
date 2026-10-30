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

(filled when the branch closes)
