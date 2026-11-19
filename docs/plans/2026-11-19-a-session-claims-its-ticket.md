---
canonical: greenharness/relais docs/plans/2026-11-19-a-session-claims-its-ticket.md
plan-id: p-01M7SH79WA5FGSCQK2F7K609NZ
phases: [2]
status: done
---
# A session claims its ticket, and a handoff names only an unheld one

Pointer to the canonical plan in relais (session-boundaries t26). This
repository carries Phase 2: in a programme, the Handoff step's prompt names
one ticket that `relais programme next --claim` chose and reserved, or the
session parks with `safe to /clear; parked: next due <date>`. worktree-task
§ Handoff step 4 says it; merge-when-green step 7 and tag-release step 7
point to it.

## Code review
- greenharness-skills: none — no language area (skill text)

## Verification (Phase 2, 2026-11-19)

Skill text, checked against the relais behaviour it describes (relais #497,
piloted on the real binary): `next --claim` prints `<repo> <slug> <id>`, a
tab and the name, exit 0; parks with one `parked: next due <date>` (or
`parked: nothing due`) line on stdout, exit 22; other exits are errors. The
three texts tell the session to resume that one ticket, or to end with
`safe to /clear; ` and the parked line, or to report the error with no clear
line. `scripts/check.sh` exits 0. The first live parked handoff is checked
after relais v0.71.0 installs (the canonical plan's live proof).

## Implementation review

- implementation-review: approve-with-changes, then approve; fixed: the park line relais prints, the mirrors' missing cases; deliberate: the mirrors do not repeat "never an open-ended prompt" (print no clear line already rules it out). 39k + 42k, 156 + 53 s.
