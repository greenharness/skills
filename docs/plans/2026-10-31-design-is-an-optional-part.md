---
canonical: fredericrous/decisions docs/plans/2026-10-31-design-is-an-optional-part.md
phases: [3]
status: active
branch: feat/design-lookup-slot
---
# Design is an optional part: the generic reviewers and the lookup slot (pointer)

This repository's slice of the ADR-0048 plan is section 3: generic
`plan-review-ui-design` and `plan-review-react` agents in the workflow part,
the design-lookup slot in `plan-review` (an installed `design-system-lookup`
agent fills a `design-lookup` block), the remaining Duro mentions generalised,
the "every part is optional" fallbacks, and release **0.4.0** (the canonical
body says 0.2.0; its Decision log renumbers it).

## Implementation review

- Round 1: approve-with-changes (38k, 22 s). Deliberate: the ui-design "Look for" list ends on `;` (cosmetic, fixed with the next edit of the file). Re-recorded: `grep -rni duro parts/` prints only `diagnosing-bugs/trigger-prompts.tsv` and `interface/NOTICE.md`.
- Verification: `scripts/check.sh` exit 0. Next: release 0.4.0, then grh pins it.
