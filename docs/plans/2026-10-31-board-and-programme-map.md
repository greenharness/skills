---
canonical: github:fredericrous/decisions/docs/plans/2026-10-31-board-and-programme-map.md
phases: [3]
status: active
branch: feat/in-flight-steps
---
# Board and programme map

Pointer. The plan and its review panel live in decisions, with ADR-0051
(`work.check-in-flight-before-starting`). This repository carries phase 3:
an in-flight check in `worktree-task`, `diagnosing-bugs` and
`tag-release`, released as skills v0.2.0.

## Verification

- `sh scripts/check.sh` (no machine-specific content) → expected exit 0 → actual exit 0, after dropping two `work.*` rule ids the check rejects in published skills.
- The step's command on a real repository, `amont-agent board --repo greenharness-skills --fetch` with amont-agent 3.10.0 installed → expected the in-flight worktrees, their plans and what landed → actual: this branch's worktree with plan "Board and programme map", two unmerged branches (one with its plan), three commits landed in 2 days; 16.2 s with the fetch.
- The 10-14 replay for tag-release step 0: a scratch repository with two worktrees, both on a `chore/release-1.1.0-*` branch bumping `VERSION`, and a live session's activity on the first. From the second worktree, `amont-agent board --repo rel` → expected the first worktree with its live session → actual `rel-wt-a [chore/release-1.1.0-a]` with `session sess-a (seen 0s ago)`; `git ls-remote --tags origin v1.1.0` → empty (tag absent); `git diff --stat origin/main...chore/release-1.1.0-a -- VERSION` → `VERSION | 2 +-`. So step 0 stops and names the session to message.
- Fallback: `amont-agent board --help` exits 0 on 3.10.0, so the board part applies; on an older amont-agent the steps say to run the `git log` part alone.

## Implementation review
