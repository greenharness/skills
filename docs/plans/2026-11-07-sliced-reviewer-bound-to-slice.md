---
canonical: amont-agent:docs/plans/2026-11-07-sliced-reviewer-bound-to-slice.md
phases: [4]
status: active
---
# A sliced reviewer is bound to the part of the plan it reviews (pointer)

Canonical plan: [amont-agent/docs/plans/2026-11-07-sliced-reviewer-bound-to-slice.md](https://github.com/fredericrous/amont-agent/blob/main/docs/plans/2026-11-07-sliced-reviewer-bound-to-slice.md) (ADR-0061, rule `work.review-slices`).

This repository carries Phase 4. The plan-review skill runs `plan-sha --block` with the `--slice <role>` that `plan-panel` prints on a sliced seat's line, pastes both stdout lines, and re-runs in round 2 and in a delta every seat the hook names as stale, a sliced seat when its slice moved. With an amont-agent older than 3.23.0, `plan-panel` prints no `--slice` and the skill runs the plain block. Released before amont-agent 3.23.0 is installed.

## Code review

- greenharness-skills: none — markdown only
