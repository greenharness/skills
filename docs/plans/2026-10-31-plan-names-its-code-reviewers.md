---
canonical: decisions:docs/plans/2026-10-31-plan-names-its-code-reviewers.md
phases: [4]
status: active
---
# The plan names its code reviewers (pointer)

Canonical plan: [decisions/docs/plans/2026-10-31-plan-names-its-code-reviewers.md](https://github.com/fredericrous/decisions/blob/main/docs/plans/2026-10-31-plan-names-its-code-reviewers.md) (ADR-0052).

This repository carries Phase 4: the `code-review-<role>` agent files, interface-review's gated verdict, plan-review writing the `## Code review` section, worktree-task F4b launching the declared profiles, and the plan template's new section.

## Decision log

- 2026-11-01 — Phase 4 was written by hand. Two relais runs each waited out their 30-minute admission budget, because the host was at load 22 on 12 cores with its slots cut to 1, and launched nothing.
- 2026-11-01 — A profile's brief goes by path only. `review-brief --profile` prints its own `Profile:` line, and the hook counts a prompt only when it holds exactly one.
- 2026-11-01 — The Agents section's check (a declared ui-design launch on a diff over 60 KB: full UI supplement, readable verdict, profile binding) needs the agents installed, so it runs after Phase 5 and is recorded with Phase 6.

## Verification

- Phase 4: `scripts/check.sh` → no machine-specific content → exit 0. `python3 -m py_compile` on the sweep script, and `python3 -m unittest discover -s tests` → OK. The behaviour the files describe was checked against amont-agent 3.11 by the implementation review: the agent map, the `Profile:` rule, the marker, the carry rule, no candidates in a profile brief.
- The ui-design launch over 60 KB: deferred to Phase 6 (Decision log).
