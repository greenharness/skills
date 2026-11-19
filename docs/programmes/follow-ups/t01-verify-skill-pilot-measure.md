+++
type = "task"
mode = "afk"
status = "open"
blocked_by = []
repos = ["greenharness-skills", "sre-agent", "duro-app"]
due = "2026-12-19"
+++
# Do the verify-skill pilots widen, get a --check, or drop

## Question

Phase 4 of `docs/plans/2026-11-19-create-verify-skill.md`: after 5 real
F2 runs per pilot (`verify-sre-agent`, `verify-duro-app`) or on
2026-12-19, whichever comes first, do repairs per run, F2 wall time and
blockers beat the plan's baselines? Decide widen, build `--check`, or
drop, by the plan's Verification rule.

## Look at

- The plan's `## Baseline` sections (sre-agent: median 1 repair, 10 min;
  duro-app: 0 of 2 measurable plans ever started the app, so it decides
  on wall time and blockers alone).
- Session transcripts since 2026-11-19 of every worktree-task F2 in
  sre-agent and duro-app: did it use the verify skill, how many
  repairs, minutes from the first F2 command to the verdict, and any
  step that failed because a `generated-from` file moved (a stale step).
- `git log` of `.claude/skills/verify-*` in both repos: fixes to a
  stale step land there.

## Answer looks like

A table per pilot (run, repairs, wall min, stale steps), the run count,
and one decision with the rule it met, written into the plan's Outcome
in one docs PR. Widening follows the plan's order (application-landscape,
social-planner, website-builder, customer-vision).
