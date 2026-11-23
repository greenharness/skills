---
canonical: greenbelay:docs/plans/2026-11-23-hand-off-mid-phase-400k.md
phases: [2]
status: done
---
Part of [Hand off mid-phase at about 400k context](greenbelay:docs/plans/2026-11-23-hand-off-mid-phase-400k.md).
This repository carries Phase 2: the worktree-task `## Handoff` gains a
size boundary and its mid-phase steps.

## Code review

- greenharness-skills: none — markdown only

## Outcome

- [x] Phase 2: `parts/workflow/skills/worktree-task/SKILL.md` `## Handoff`
  gains boundary 5 (a size boundary, past about 400k mid-phase, when a hook
  or the person says so), its narrower in-flight list (only background
  work, polls, relais runs and questions hold), and `### Steps at a size
  boundary (mid-phase)`: no inbox, edits kept with no WIP commit, the
  handoff in the ticket's own `## Handoff` or the plan's, first line
  `<date> mid-phase at <N>k`, committed alone as `docs(plan): handoff
  <phase>` unpushed, both prompt forms with no `next --claim`, and a resume
  that stops on a `git status` mismatch.
- Carried from Phase 1: no inbox at a size boundary, and the
  `mid-phase at <N>k` literal, are both in the steps.
- The skill names no tool for the notice ("the notice that asked for the
  handoff"), so it holds without greenbelay.

## Verification

- `scripts/check.sh` → expected exit 0 (no ADR number, `work.*` key or
  machine path in published text) → actual exit 0 on HEAD.
- `python3 -I -m unittest discover -s tests` → expected OK → actual 140
  tests OK on HEAD.
- Heading anchor `#steps-at-a-size-boundary-mid-phase` → expected to match
  the new heading → actual matches (reviewer checked).
- Skill-trigger tests: no such tool on this machine; the change does not
  touch the skill's description, which is what triggers it.

## Implementation review

- Round 1, implementation-review (opus): approve. One low finding, a resume
  with a mismatched `git status`: fixed in 2ad7c6f. 39k, 24 s.
- Delta, implementation-review (opus): approve; finding resolved, nothing
  new. 21k, 15 s.
