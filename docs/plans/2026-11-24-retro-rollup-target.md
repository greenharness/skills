---
canonical: blue-factory:docs/programmes/blue-factory/t34-build-greenbelay-firing-rollup.md
phases: [1]
status: done
branch: feat/retro-rollup-target
repos: [greenharness-skills]
plan-id: p-01M86TN3VMCNH01B0011J62RSB
---
# Retro's Target line reads the greenbelay roll-up (t34 Phase 6)

## Review panel

none — approve if one paragraph of retro's SKILL.md is the whole change.
📍 greenharness-skills · 1 phase · 1 PR · next: Phase 1. Panel: backend (opus).
**Changed by review:** jq binds the week (`$w`); dated facts dropped; fixture named.
**Verdicts:** 2 approve-with-changes; 4 carried (calls>0, neutral reason, drop the "two days" note, real-output check); words 367 → 397; remove 0, merge 0.

📄 Full reviews: [retro-rollup-target.reviews.md](2026-11-24-retro-rollup-target.reviews.md)

## Picture

```
retro step 4, greenbelay-rule Target
  backtest recount ──prints a row──▶ <firings>/<calls> Bash calls
        │ prints nothing (replay none / old greenbelay)
        ▼
  rollup recount ───prints a row──▶ <firings>/<calls> <tool> calls
        │ prints nothing (no closed week, no tool, greenbelay < 6.12.0)
        ▼
  Target: uncounted; count by: no closed roll-up week for <rule>
```

The picture shows retro trying the backtest first, then the roll-up, and
writing `uncounted` only when both print nothing.

## Context

t34 shipped `greenbelay rollup [--json]` (6.12.0). Retro's Target line still
writes `Target: uncounted; count by: no weekly source for <rule>` for every
greenbelay rule whose backtest `replay` is `none`. The roll-up carries
firings and calls per week for those rules. Outcome: retro uses it, so a
`replay: none` rule gets a count.

## Phase 1: Target line reads the roll-up

Edit `parts/workflow/skills/retro/SKILL.md`, the greenbelay-rule bullet of
step 4 (lines ~139–148), only:

- Keep the backtest recount first. When it prints nothing (`replay` is
  `none`, or greenbelay is older than the label), try the roll-up before
  `uncounted`.
- Roll-up recount (`<rule>`, `<from>` = the last complete week's Monday):
  `greenbelay rollup --json | jq -r '.weeks[] | select(.week=="<from>" and (.partial|not)) | .week as $w | .rules[] | select(.rule=="<rule>" and .calls!=null and .calls>0) | "\($w) \(.rule) \(.firings) \(.calls) \(.rate) \(.tool)"'`
  Target reads `<firings>/<calls> <tool> calls, week of <Monday>` (tool from
  the row: `Bash`, `Read` …; `any` reads `tool calls`).
- Still `uncounted` when the roll-up prints nothing: no closed week yet, the
  rule has no tool (`calls` null: a hook on another event), or greenbelay is
  older than the roll-up (the skill text carries no date and no version). Reason text (as shipped, per the panel's carried item): `no roll-up row for <rule> (no closed week, no tool, or an older greenbelay)`.
- The skill works with the tool absent: it names no version beyond
  "older than the roll-up".

## Code review

- greenharness-skills: none — markdown only

## Verification

- `scripts/check.sh` → expected exit 0 → actual rc 0; `python3 -I -m unittest discover -s tests` → expected OK → actual 140 tests OK.
- Fixture jq (calls 412, `<from>`=2026-11-23) → expected `2026-11-23 r 3 412 7.28 Bash` → actual that line; a `calls: 0` row → expected no row → actual none.
- Live `greenbelay rollup --json` (6.12.0), same jq shape → keys match: `2026-11-23 pipe-to-tail 56 9041 6.2 Bash`. Week 2026-11-23 is still partial today, so the closed-week filter prints nothing and the `uncounted` branch is what holds.
- The ticket stays open until a real retro Target line shows a roll-up
  count (first closed week 2026-11-23, readable from 2026-11-30).

## Implementation review

- Round 1, implementation-review (opus): approve-with-changes; reason text deliberate (panel's carried item), week and recount fixed in 2e82e8b, actuals recorded here. 27k, 40 s.
- Delta (opus): approve; sync the plan's jq and record actuals, both done here. 25k, 16 s.

<!-- panel: repos=greenharness-skills adds= reviewers=backend body-sha=0354404374ba -->
