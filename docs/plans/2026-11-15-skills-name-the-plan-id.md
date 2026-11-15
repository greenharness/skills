---
canonical: amont-agent:docs/plans/2026-11-15-every-plan-gets-an-id.md
phases: [5]
status: active
branch: feat/plan-id-skills
repos: [greenharness-skills]
---
# Skills name the plan id and the counts

Pointer: Phase 5 of the plan "Every plan gets an id, and the panel counts", which lives in amont-agent.

- `plan-review` §0: `plan-panel` owns `plan-id:`, so it is never written by hand, and the file is re-read after `plan-panel`.
- §1: line 1 ends with the `counts=` token.
- §7: the 📍 line carries the counts in words, with a drop order that keeps it to about 20 words.
- `plan-template.md` gains `plan-id:`.
- The backend seat rules on `merge-candidates`.

## Verification
- `scripts/check.sh` exits 0; `python3 -m unittest discover -s tests` passes.

## Implementation review
- implementation-review (opus), round 1: approve-with-changes. Fixed: `plan-id` at worktree-task landing, with the §0 exception named; the `words:A/B` and `-` forms; the PR drop explained. Delta: approve-with-changes, wording only. Deliberate: the `-` sentence reads close to `words`.

<!-- panel: repos=greenharness-skills body-sha=f1267bf8ce83 -->
