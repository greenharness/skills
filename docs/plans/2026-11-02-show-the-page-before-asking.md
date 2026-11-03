---
canonical: decisions:docs/plans/2026-11-02-show-the-page-before-asking.md
phases: [3]
status: active
---
# Show the page before asking about it (pointer)

Canonical plan: [decisions/docs/plans/2026-11-02-show-the-page-before-asking.md](https://github.com/fredericrous/decisions/blob/main/docs/plans/2026-11-02-show-the-page-before-asking.md) (ADR-0058, rule `work.page-shown-before-asked`).

This repository carries Phase 3. worktree-task F7 step 5 opens the app through `amont-agent open '<url>'` (amont-agent 3.16.0) instead of `open '<url>'`, and says that the `ask-unopened-page` hook refuses the step-6 question until that open ran. The `plan-review` skill asks the person to pick between no pages, so it is unchanged.

## Code review

- greenharness-skills: none — one line in a skill's markdown

## Implementation review

- implementation-review: round 1 approve-with-changes, 1 fixed (the hook sentence is conditional on step 6 naming the URL); Phase 3 is ticked in the canonical plan with the merge and release. Delta approve. 32k+33k.

## Verification

Rows are in the canonical plan; results are recorded here.
