# Plans

An approved plan is the first commit of its task branch. This directory is history, read on demand,
and never loaded into every session. What is
true now lives in the rest of `docs/`; what was decided lives in
`docs/adr/`.

**File name.** `YYYY-MM-DD-<slug>.md`. The date is the approval date. The
slug is the plan's H1 in kebab-case, five words at most.

## Template

```markdown
---
status: active            # active | done | abandoned | imported
branch: feat/<name>
repos: [<this-repo>]      # every repository the plan touches
adrs: []                  # records this plan adds or relies on
---
# <Title>

## Goal
What changes for whom, in two or three sentences.

## Non-goals
What this deliberately leaves alone.

## Code review
The expert profiles that review the code at the close, beside
implementation-review: one line per repository, from
`amont-agent plan-panel --code-review`.
- <repo>: backend, lang:<language>, unix (tui left out: <reason>)
- <other-repo>: none — <reason>

## Behaviour
The observable behaviour after the change. This is the spec. Link a picked
artboard here when one exists (handoff.prove-fidelity).

## Preview
evidence: <why the person will have nothing left to judge: the visible change
is one this plan decides, and the screenshot comparison will show nothing else>

Optional, for an interface change; delete the section to have the
person preview the commit as usual. The `evidence:` line must stay the first
line under the heading.

## Phases
- [ ] Phase 1 — <one line>; becomes one or more commits
- [ ] 🧑 decision: <question the person answers, with 2–4 options>
- [ ] Phase 2 — …

## Decision log
- YYYY-MM-DD — <decision>, because <reason>. (A scope change is recorded
  here, never as a silent rewrite of the sections above. A lasting decision
  becomes an ADR and is linked from here.)

## Verification
Per phase: what is driven → what should be observed → what was observed.
- Phase 1: open `/settings`, toggle "Compact" → list density changes and
  survives a reload → <result, screenshot path>
- "Tests pass" is not a check.

## Outcome
Filled when the plan closes: what shipped, what did not, and what surprised.
```

## Status

| status | meaning | editable |
|---|---|---|
| `active` | phases open | tick phases; append Decision log, Verification, Outcome |
| `done` | every phase implemented and verified | frozen; a follow-up is a new plan |
| `abandoned` | stopped, with the reason in Outcome | frozen |
| `imported` | a legacy plan moved here, completion not established | frozen |

Merge state is never written here; git records it.

## Pointer files

A plan that spans repositories lives in the one that owns its decision.
Each other repository carries a pointer with the same file name:

```markdown
---
canonical: decisions:docs/plans/2026-09-28-plans-and-preview.md
phases: [2]               # the phases this repository carries
status: active            # this repository's slice only
---
Part of [<title>](<link to the canonical plan>).

## Code review

- <this repository>: <its line from the canonical plan, verbatim>
```

The `## Code review` section holds only this repository's line, copied
verbatim from the canonical plan's section. The push gate reads it from the
branch (amont-agent 3.14.0), so the declaration is versioned with the commit
and an approval from the session carries. The section must declare this
repository, either profiles or `none — <reason>`; an empty one, or one that
names only other repositories, holds the push. A pointer without the section
falls back to its canonical plan, read from the checkout, and gets no session
carry.
