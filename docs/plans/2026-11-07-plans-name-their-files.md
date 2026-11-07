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

## Verification

Rows are in the canonical plan; results are recorded here.
