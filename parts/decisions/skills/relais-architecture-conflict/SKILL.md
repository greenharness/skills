---
name: relais-architecture-conflict
description: Resolve an architecture decision key and handle every outcome aval can return, including a corpus that contradicts itself.
---

# /relais-architecture-conflict

`aval resolve <key> --json` has a stable exit-code contract; read the
code, not just stdout, before deciding what happened.

## Exit codes

| exit | meaning |
|---|---|
| 0 | active — a decision exists and holds |
| 4 | undecided — no record answers this key |
| 5 | contradiction — the corpus disagrees with itself |
| 6 | retired — a decision existed and was withdrawn |
| 7 | unknown — the key is not one aval recognises |
| 1 | tool failure |
| 2 | usage error |
| 3 | corpus unreadable |

## On exit 5 (contradiction)

Do not pick a side. aval is read-only and deciding between two
contradicting records is not this skill's call, or the caller's model's
call, to make silently. Instead:

1. Write an inspect contract (`"kind": "inspect"`) capturing the
   evidence: the key, the scope, and both records aval's contradiction
   names.
2. Hand back a decision that names BOTH readings the corpus supports,
   with their evidence, and says explicitly that the corpus contradicts
   itself here.
3. Let a person or an explicit decision step choose; never resolve the
   contradiction by preferring one record over the other on your own
   initiative.

## Rules

- Exit 1/2/3 are tool or corpus failures, not decisions — retry or
  report the failure, never treat them as "undecided".
- A `suggestion` field in aval's output is advisory: it resolves
  nothing and is never a substitute for calling `aval resolve` again.
