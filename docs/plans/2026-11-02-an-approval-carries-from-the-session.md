---
canonical: amont-agent:docs/plans/2026-11-02-an-approval-carries-from-the-session.md
phases: [2]
status: active
---
# An approval carries from the session (pointer)

Canonical plan: [amont-agent/docs/plans/2026-11-02-an-approval-carries-from-the-session.md](https://github.com/fredericrous/amont-agent/blob/main/docs/plans/2026-11-02-an-approval-carries-from-the-session.md).

This repository carries Phase 2: the reason worktree-task step 2c and the seven `code-review-*` agents give for passing a brief by path. Since amont-agent 3.11.1, only the prompt's header counts, so the reason is now that the brief is long.

## Verification

- Phase 2: `scripts/check.sh` → exit 0. `grep -rn "counts for nothing" parts` → 0 lines. Step 3 of worktree-task puts the TREE line first → yes (SKILL.md:272).
