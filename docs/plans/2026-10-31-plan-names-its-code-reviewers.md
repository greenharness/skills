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
- 2026-11-01 — The Agents section's check (a declared ui-design launch on a diff over 60 KB: full UI supplement, readable verdict, profile binding) needs the agents installed, and a repository that declares `ui-design`. The Phase 6 dogfood in amont-agent declares none. So the check stays open: `holds-until:` the first plan that declares `ui-design` with a UI diff over 60 KB, whose F4b records it.

## Verification

- Phase 4: `scripts/check.sh` on the changed files under `parts/` → no ADR numbers, rule ids or machine paths → exit 0.
- The unittest run and `py_compile` are a regression run only: they cover the sweep script, which this diff does not touch.
- `skill-trigger-test` does not apply: this repository has none, and its CI runs only `check.sh` and the tests.
- Not measured here: whether amont-agent 3.11 counts a profile launch made as these files describe. That is the Phase 6 dogfood's check, which needs the agents installed.
- The ui-design launch over 60 KB: open (Decision log).

## Open follow-ups

- A profile's Delta (step 6) inlines "the diff since". A diff line that starts with `Profile:` once trimmed would give the prompt a second Profile line, and the hook would count the round for nothing. `holds-until:` the first profile Delta that the hook refuses this way, or a change that sends profile Deltas the diff by path.

## Implementation review

- Phase 4: approve-with-changes twice (65k + 74k tokens, 74 s + 32 s).
- Fixed: a profile's brief goes by path, so the prompt has one `Profile:` line; interface-review names its gated mode; step 1 names the declared-review line.
- Kept open: the ui-design 60 KB check and the inline Delta diff (above).
