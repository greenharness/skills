---
canonical: decisions:docs/plans/2026-11-07-plans-name-their-files.md
phases: [2]
status: active
---
# Plans name their files and declare what files cannot show (pointer)

Canonical plan: [decisions/docs/plans/2026-11-07-plans-name-their-files.md](https://github.com/fredericrous/decisions/blob/main/docs/plans/2026-11-07-plans-name-their-files.md) (ADR-0063, rule `work.review-seats-follow-file-types`).

This repository carries Phase 2. The plan template asks each phase to name, in backticks, every file it touches, and asks for `adds=screen` / `adds=contract` for what files cannot show. The plan-review skill seats by file type with the area fallback, and states what holds with an amont-agent older than 3.22.0. The plan-review-backend agent holds a plan seated from paths to both declarations. Released as v0.3.9; grh pins it in Phase 3.

## Code review

- greenharness-skills: none — markdown only

## Implementation review

- implementation-review: round 1 approve-with-changes, 3 low fixed (`large` named only for an older amont-agent in the backend bullet and the ledger areas; the older-tool case opens the skill), 1 deliberate (Phase 2 is ticked in the canonical plan with the v0.3.9 tag). Delta approve. 40k+23k.

## Verification

Rows are in the canonical plan; results are recorded here.
- `./scripts/check.sh` → exit 0, no decision or rule id in `parts/`.
- `python3 -m unittest discover -s tests` → OK.
- The skill's `--code-review` line shapes match amont-agent 3.22.0's output on the canonical plan (`decisions\tnone\tno reviewed file type`).
- The installed backend reviewer on four fixture plans (only an exact `adds=` blocking finding counts):
  - 0.3.9's text: a crate with no `adds=` → `adds=contract` 1 of 3 (one run named a value that does not exist, `adds=interface`, one asked for `adds=ops`). A settings-screen fixture was void: that screen already exists in the repository, so nothing was added.
  - The declarations moved to a first step, with the only valid values and the finding's exact wording (v0.3.10): crate, no `adds=` → `adds=contract` 3 of 3; a new Insights screen, no `adds=` → `adds=screen` 3 of 3; the crate with `adds=contract` → no `adds=` finding, 2 of 2; two phases naming no file → a finding asking for their files, 2 of 2.
  - Implementation review: the first step must key on the brief's `areas=`, not on `seats=paths` (a plan seated from a small repository's areas gets no architect either). Final text, v0.3.10: crate, paths, no `adds=` → `adds=contract` 3 of 3; new screen, paths, no `adds=` → `adds=screen` 3 of 3; crate with `adds=contract` → no `adds=` finding 0 of 3; crate seated from areas without `contract` → `adds=contract` 2 of 2, with the no-file finding; crate seated from a large repository's areas (which hold `contract`) → no `adds=` finding 0 of 2 (one run's patch for a missing repository also wrote a redundant `adds=contract`).
