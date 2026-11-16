---
canonical: greenharness/greenpiste docs/plans/2026-11-16-plan-steps-block.md
plan-id: p-01M7HWWH16M0B7ATHHZQ7MKSDM
phases: [2]
status: active
---
# B7: the "🧑 Your steps" block, with a steps count

Pointer to the canonical plan in greenpiste. This repository carries Phase 2:
the template block, the finish report, and the `plan-review` counts line.

## Code review
- greenharness-skills: backend

## Verification
- Template: a plan extracted from the edited template → greenpiste 5.1.0
  `plan-panel` gives `phases:2`, `person:1`, `steps:1`.
- Finish: a plan with steps `a`, `b` → the report's last lines are the two
  numbered steps; a plan with no block → `Your steps: none.`; a pointer plan
  → the steps of the plan its `canonical:` names.
