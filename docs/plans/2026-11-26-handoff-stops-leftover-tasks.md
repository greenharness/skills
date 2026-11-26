---
status: active
plan-id: p-01M8CP6S552TRP639ZKT1NTVF5
branch: docs/handoff-stops-leftovers
repos: [skills]
adrs: []
---
# The handoff stops leftover tasks before /clear

## Review panel

👉 **Decide:** none — approve if the model sweeping its own tasks at the handoff is enough until the Stop-hook follow-up.
📍 skills · 1 phase · 1 release (v0.24.0) · next: Phase 1. Panel: backend (opus-5-5); codex not run.
**Changed by review:** fallback branches sweep too; a second sweep before the clear line; the size boundary sweeps.
**Verdicts:** delta approve-with-changes, then all 5 resolved; 2 low carried; replaces a plugin plan reviewed twice (/tmp/plan-plugin-version.md).
📄 Full reviews: [2026-11-26-handoff-stops-leftover-tasks.reviews.md](2026-11-26-handoff-stops-leftover-tasks.reviews.md)

## Picture

```
answer about to end at a boundary
   │
   ▼
Handoff step 0: list this session's own tasks
   (agents, background shells, Monitors it started,
    no completion notification yet)
   │
   ├─ result still needed ─────────▶ in flight: say it, no clear line
   │
   ├─ not needed, safe to cut ─────▶ TaskStop it, note it in the answer
   │
   └─ stop refused / unsure ───────▶ in flight: say it, no clear line
   │ all stopped or done
   ▼
steps 1–4 as today ─▶ safe to /clear; next: `…`
   │
   ▼
clear-relay clears: nothing of this session is left running
```

The picture shows one new step before the handoff: the session stops its own leftover tasks, or
keeps the clear line back while one still matters.

## Context

The clear-relay plugin runs `/clear` by itself after a `safe to /clear; next: …` line. A `/clear`
leaves the session's tasks running with nothing watching them. The person has had to kill agents
by hand after a relay (a stop from the UI leaves no transcript marker, which is why transcripts
undercount it). The engine reports the same for background shells: a session after a clear opens
with "Background shell command didn't finish before the previous session ended … marked stopped"
(sessions 863ddf2b and 3a8f93df, 2026-11).

The Handoff rule already says a running background task blocks the line. It does not tell the
session to look: it relies on the model remembering what it started, and nothing stops a task
whose result is no longer needed (a superseded poll, a Monitor still streaming, an agent idle
after its answer). The session prints the line with leftovers behind it.

## Decisions (the person's, 2026-11-26)

- Stop leftovers when it is safe to; otherwise hold. All subagents and teammates count, and so do
  background shells and Monitors.
- The handoff rule carries it, not the clear-relay plugin: a mod can list agents
  (`$.agent.list()`) but no mod API lists background shells, and the model knows every task it
  started. A plugin check for agents was planned and reviewed first (two panel rounds); it is
  dropped in favour of this rule.

## Non-goals

- No change to the clear-relay plugin or to greenbelay.
- The relais `programme` skill's own boundary text (relais pins its skill text with a Rust test);
  it runs this Handoff where worktree-task is installed.
- Tasks of other sessions: only this session's own.
- A hook that checks the sweep: a follow-up (below), filed at the boundary.

## Code review
- skills: none — markdown only

## Behaviour

In `parts/workflow/skills/worktree-task/SKILL.md`, `## Handoff` (also `### Steps at a size
boundary`, before its step 5: the same sweep, where the task worktree's own edits are expected):

1. `### When`, the in-flight list: the item "none of its background tasks, polls or relais runs is
   still running or waiting on a decision" now reads that this holds **after** step 0's sweep.
2. A new `### Steps` step 0, before "File the inbox", **Stop what this session left running**:
   - List this session's own tasks from its transcript: each `Agent` launch, each Bash call with
     `run_in_background`, each Monitor, whose completion notification has not arrived, plus each
     agent or teammate that answered but may still be idle or waiting.
   - For each, decide from what the session knows:
     - its result is still needed (a land, a merge poll, a relais run, an agent whose answer the
       handoff depends on) → it is in flight: say what it is, print no clear line (today's rule);
     - not needed (superseded, a Monitor or poll whose answer arrived, an agent that already
       answered, a dev server of a finished preview) → `TaskStop` it;
     - a stop that fails, or a task it cannot judge → in flight, as above.
   - A task that may hold uncommitted work in a worktree the session made is in flight until that
     worktree is clean: stopping it would cut the work short.
   - Run the sweep again just before step 4: step 3 can start a merge poll for a docs PR.
   - After the stops, one line in the answer names what was stopped (`stopped: <id> <what>, …`),
     or `stopped: none`; the line comes before the clear line, never after it.
   - For a task judged not needed, when unsure whether its id is still live, `TaskStop` it: an id that is gone answers
     `No task found`, which is not a failure.
3. merge-when-green and tag-release already run this Handoff when worktree-task is installed. Their
   fallback branch (without it, merge-when-green:88-90, tag-release:101-104) gains its own clause:
   "first `TaskStop` each task of this session whose result is no longer needed", so the
   fallback sweeps too.

## Phases

- [ ] Phase 1: the Handoff step and its pointers, then the release.
  - Files: `parts/workflow/skills/worktree-task/SKILL.md`,
    `parts/gate/skills/merge-when-green/SKILL.md`, `parts/gate/skills/tag-release/SKILL.md`.
  - After the merge: tag the skills `v0.24.0` (the repository releases by tag alone, the
    `tag-release` skill) and install them on this machine (`grh install workflow gate`), so
    `~/.claude/skills/worktree-task/SKILL.md` carries step 0.

## Verification

- `grep -n 'Stop what this session left running' ~/.claude/skills/worktree-task/SKILL.md` after
  `grh install` → one match inside `### Steps`, one in `### Steps at a size boundary`; the gate
  skills' fallback text carries the `TaskStop` clause. `scripts/check.sh` stays green (the gate).
- Piloted: a session starts one background `sleep 600` shell and one background agent that answers,
  then reaches a boundary. Expected: the answer names both under `stopped:`, then the clear line;
  after the relay's clear, the next session gets no "didn't finish before the previous session
  ended" notice.
- Piloted hold: the same with a background `sleep 600` that the handoff depends on (named so in
  the prompt). Expected: no clear line, and the answer says what is in flight.
- After 7 days: count the sessions that open with "didn't finish before the previous session
  ended" (before: 2 of the last 150 transcripts, plus the by-hand kills). Expected: none after a
  relay.

## Follow-ups

- A greenbelay Stop-hook check: at a clear line, the transcript's tasks with no completion
  notification and no `TaskStop` are named, at advise first. This is the deterministic backstop
  for a model that skips step 0.

## Verification results (before the push)

- `grep -n 'Stop what this session left running'` on the branch's
  `parts/workflow/skills/worktree-task/SKILL.md` → line 674 (`### Steps`, step 0) and line 817
  (`### Steps at a size boundary`, step 5); the fallback clause `whose result is no longer needed`
  → 1 match each in merge-when-green and tag-release.
- `scripts/check.sh` → exit 0; `python3 -m unittest discover -s tests` → exit 0 (CI's own commands).
- Not yet observed (after the merge, tag v0.24.0 and `grh install workflow gate`): the installed-file
  grep, the stop pilot, the hold pilot, and the 7-day count. Those belong to the next action.

## Decision log

- 2026-11-26: the person chose "Handoff rule instead" over a clear-relay plugin check for agents.
  The plugin plan had two full panel rounds and was dropped: no mod API lists background shells,
  and the engine's own leftover reports are mostly shells.
- 2026-11-26: deliberate: the Picture does not draw the second sweep before step 4 or the
  size-boundary sweep. Redrawing it would change the reviewed body for a drawing alone.

## Implementation review

- approve-with-changes (opus, 36k tokens, 33 s): fixed the badly wrapped fallback paragraphs; kept
  Phase 1 open on purpose, since its tag and install come after the merge.
- Delta: approve (opus, 26k, 21 s): all round-1 findings resolved, nothing new.

## Next

Merge the PR, tag `v0.24.0` (the `tag-release` skill), run `grh install workflow gate`, then the two
pilots and the installed-file grep; tick Phase 1 and set `status: done` with their results.

<!-- panel: repos=skills reviewers=backend body-sha=162c037a9106 -->
