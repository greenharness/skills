---
status: active
branch: feat/plan-picture
repos: [greenharness-skills]
adrs: []
---
# Plans carry a picture

## Picture

```
 today                            after this plan
 -----                            ---------------
 plan --> panel --> person        plan --> [draw] --> [check.py] --> panel
          (text only)                         |            |
                                              |            `--red--> redraw
                                              `--big--> SVG page, opened
```

A plan now gets one drawing of the mechanism it builds, checked by a script
before the panel reads it, with an SVG page beside it when ASCII is too small.

## Goal

Every plan and programme map carries one picture that explains what will be
built, so the person gets the mechanism before reading the phases. ASCII in
the plan by default; an SVG page linked from it, and opened for the person
as mockups are, when the picture outgrows ASCII. The method borrows from
ian-xiaohei-illustrations (anchors, one idea, an actor, a check), without
raster generation.

## Non-goals

- No image generation, no mascot, no per-plan metaphor.
- No hook gate: the checker runs from the skills; an amont-agent gate is a
  later decision.
- The `relais:programme` skill (relais repository) is not changed here.

## Code review

- greenharness-skills: none — markdown and a stdlib checker script reviewed
  in two rounds by architect, backend and Codex (see Decision log)

## Behaviour

- `plan-picture` skill: pick the anchor and actor, draw ASCII in
  `## Picture` (after `## Review panel`), move to a dated `<date>-<slug>.svg`
  beside the plan with a short-hash link when it does not fit, open it,
  check, hand over. `none: <why>` (three words or more, alone) for a plan
  that changes no mechanism.
- `check.py <plan.md>`: exit 0 holds, 1 findings, 2 usage; `--hash <file>`
  prints the hash a linked picture carries.
- `plan-review` runs the checker before seating the panel when it is
  installed; `plan-review-backend` holds the picture to the phases;
  `worktree-task` copies a linked picture beside the landed plan.

## Phases

- [x] Phase 1 — the skill and its checker:
  `parts/workflow/skills/plan-picture/SKILL.md`,
  `parts/workflow/skills/plan-picture/check.py`,
  `parts/workflow/skills/plan-picture/trigger-prompts.tsv`,
  `tests/test_plan_picture.py`, `README.md`
- [x] Phase 2 — the wiring: `parts/workflow/skills/plan-review/SKILL.md`,
  `parts/workflow/agents/plan-review-backend.md`,
  `parts/workflow/skills/worktree-task/SKILL.md`
- [ ] Phase 3 — release and grh pin bump

## Decision log

- 2026-11-07 — Asked for in conversation, not through plan mode: the person
  chose ASCII first, an SVG page as the second tier, the workflow part, the
  `none:` opt-out and wiring in the same branch. No `## Review panel`: the
  architect and backend code-review profiles and Codex reviewed the branch
  instead, in two rounds (round 1: 6 + 10 + 14 findings; round 2: 4 + 6 + 5),
  all fixed.
- 2026-11-08 — The SVG is named by date and slug, not by the plan file's
  stem, so its link reads the same in plan mode and landed and `body-sha`
  holds; its short hash sits in the body so a redraw is reviewed.

## Verification

- `python3 -m unittest tests.test_plan_picture` → all pass → observed:
  "Ran 47 tests … OK"; whole suite `discover -s tests` → "Ran 109 tests … OK".
- `./scripts/check.sh` → exit 0 → observed: exit 0.
- The skill's ASCII example, copied out of its ````markdown fence into a
  scratch plan, through `check.py` → exit 0 → observed: exit 0 (the first
  draft failed at 82 columns and was narrowed).
- The `none: a version bump only` example in a scratch plan → exit 0 →
  observed: exit 0.
- SVG tier on a scratch plan: fresh `--hash` link → exit 0; one line added
  to the SVG → exit 1 "is stale" → observed: both.
- `check.py docs/plans/2026-11-08-plans-carry-a-picture.md` → exit 0 →
  observed: exit 0, no output.
