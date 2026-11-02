---
canonical: decisions:docs/plans/2026-11-02-preview-stale-base-unchanged-screen.md
phases: [2]
status: done
---
# The preview guard ignores a stale remote branch, and an unchanged screen needs no approval (pointer)

Canonical plan: [decisions/docs/plans/2026-11-02-preview-stale-base-unchanged-screen.md](https://github.com/fredericrous/decisions/blob/main/docs/plans/2026-11-02-preview-stale-base-unchanged-screen.md).

This repository carries Phase 2. worktree-task F7 says two things:
- a `register` that prints `"unchanged": true` needs no question;
- the pair must be the real before and after.

## Code review

- greenharness-skills: none — markdown only

## Verification

- Phase 2: `scripts/check.sh` → exit 0 on the reviewed tree.

## Implementation review

- **Verdict:** approve after one Delta (31k + 34k tokens, 27 s + 11 s).
- **Fixed:**
  - a fallback when the hook skips (`unchanged-skipped`, or the push is still held);
  - the guide and both shots go in the PR body (ADR-0057);
  - `before` from the base build only;
  - rewrapped.
