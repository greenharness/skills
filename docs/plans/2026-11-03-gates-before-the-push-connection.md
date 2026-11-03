---
canonical: amont:docs/plans/2026-11-03-gates-before-the-push-connection.md
phases: [2]
status: active
---
# Gates run before the push connection (pointer)

Canonical plan: [amont/docs/plans/2026-11-03-gates-before-the-push-connection.md](https://github.com/fredericrous/amont/blob/main/docs/plans/2026-11-03-gates-before-the-push-connection.md) (amont ADR-0018, key `hooks.gates-before-connection`).

This repository carries Phase 2. From amont 2.0, `amont land` runs the push gates before git connects, and a bare `git push` whose heavy gates are unstamped is refused ("push gate(s) have not run on"). Each skill detects the amont it has and falls back, because every Green Harness part is optional:
- `relais-verified-push`: amont ≥ 2.0 lands without a separate rehearsal; older amont rehearses, then lands; no amont pushes bare and verifies with `git ls-remote`. It says what to do after the refusal.
- `worktree-task` F6: the same, for the task finish.
- `tag-release`: where amont ≥ 2.0 is installed, the tagged commit is stamped (`amont run --stamp` in a worktree of it) before the tag push.

## Code review
- greenharness-skills: none — markdown skills only; their behaviour is checked by the Phase 2 runs
