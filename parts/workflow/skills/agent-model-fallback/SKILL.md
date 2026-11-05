---
name: agent-model-fallback
description: The one policy for a named agent whose preferred model is unavailable: retry the same agent once on the root session model. Read by plan-review and worktree-task; not invoked on its own.
disable-model-invocation: true
---

# agent-model-fallback

A named agent (a reviewer, an applier) has a **preferred model** and a
**root fallback**. The preference is never an availability dependency.

## Mechanism

1. Every first-party agent definition says `model: inherit`. An agent with
   a pinned `model:` cannot fall back: omitting the override would still
   run the pinned model.
2. The launcher passes the preferred model on the first attempt as the
   `model` parameter of `Agent`. Preferred model of every first-party
   reviewer: `opus`. Of the plan-apply helper: `sonnet`.
3. On a failure `fallback.py classify` calls `unavailable`, launch the
   **same agent type** once more with **no `model` parameter**. It inherits
   the root session model, including a custom provider id that the
   parameter cannot name.
4. Keep the prompt, the review block, the language or profile line and the
   tree or plan sha exactly as in the first launch. A generic or fork agent
   is never a substitute: the hook counts the named role.

```sh
printf '%s' "<error text>" | ~/.claude/skills/agent-model-fallback/fallback.py classify
printf '%s' "<error text>" | ~/.claude/skills/agent-model-fallback/fallback.py decide \
  --failed opus --root "<root model id>" --task "<role>"
```

`decide` exits 0 for `fallback` and 1 for `report`.

## What counts

- **Fall back:** model not found, unsupported or unavailable; provider
  cooldown; transient rate limit, overload or capacity.
- **Report, never fall back:** context overflow or an invalid request;
  authentication or permission; billing or quota exhaustion; a policy
  denial; a reviewer's own findings; completed work. An error that matches
  neither list is ambiguous, and an ambiguous error is an error.

## Bounds

- One fallback launch per task. If the root model is the failed model, is
  unknown, or also fails, report the blocker (a 👉 decision for the person).
  There is no Opus → Sonnet → Haiku ladder, and completed side effects are
  never replayed.
- Within one skill invocation, once a failure names a model as cooling down,
  later seats of that model launch on the fallback straight away. Another
  model is not suppressed, because one model's error says nothing of the
  others. A new invocation tries the preference again. Nothing is stored.
- Never change the root session's model, the global `fallbackModel`, or any
  credential. Claude Code's own fallback chain excludes rate limits, which
  is why this policy exists.
- An optional review by another vendor stays distinct and is never counted
  as a panel seat.

## Report the model honestly

Record, per seat, the requested and the effective model and the reason for
the fallback, for example `backend (opus → root: provider cooldown)`. A
seat that fell back is named so in the plan's review section and in the
implementation review line. Only a completed review bound to the plan or
tree counts.
