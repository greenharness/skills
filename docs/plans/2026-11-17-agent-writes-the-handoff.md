---
status: active
branch: feat/handoff-step
repos: [greenharness-skills, grh, relais, decisions]
programme: decisions docs/programmes/session-boundaries t04-handoff-step
adrs: []
plan-id: p-01M7KV4XQ0QAJ4WZMDADKV2MB2
---
# The agent writes the handoff and ends with the clear line

## Review panel

👉 **Decide:** none — approve if the agent, not the person, should write the handoff and print the clear line at every boundary.
📍 greenharness-skills, grh, relais, decisions · 3 phases · 4 PRs · next: Phase 1. Panel: backend (opus-5-5); codex: not installed.
**Changed by review:** grh named as a fourth repo; the inbox is taken atomically by `mv` before filing; orphans are lines ≥ 2 days old; a 7-day compliance ticket.
📄 Full reviews: [2026-11-17-agent-writes-the-handoff.reviews.md](2026-11-17-agent-writes-the-handoff.reviews.md)
**Verdicts:** round 1 approve-with-changes, round 2 approve-with-changes; 3 carried; words 1477 → 1572 (×1.06); remove 0, merge 0.

## Picture

```
 boundary: plan landed / PR merged + torn down /
           ticket closed / release swept
    |
    |  anything in flight for THIS session? --yes--> name it, no line
    v  no
 1 file inbox     <common-dir>/greenharness/inbox.md --> task tickets
 2 write handoff  the map's ## Handoff (replaced), or the plan
 3 land it        in the closing commit, before the merge
 4 last line      safe to /clear; next: `<prompt>`
    |
    v
 clear-relay (if installed): 10 s countdown --> /clear --> <prompt>
```

The agent runs the four steps itself at a boundary; the plugin does the
clear.

## Context

This is ticket t04 of the session-boundaries programme, "The handoff step in
worktree-task and programme". It was observed on 2026-11-17, after
greentopo 2.0.0 was released. The turn reached a boundary and only
summarised. `clear-at-boundary` was at `advise`, so it spoke only to the
person, and the person had to type "write the handoff". The agent then wrote
the handoff to `~/.claude/handoffs/` and moved it into the map only when told
again. No skill names the line: `grep -r 'safe to /clear'` finds it only in
greenbelay's rule (`MARKER`) and in the clear-relay plugin's regex
`^safe to \/clear; next: \`(.+)\`$`. Nothing writes the t02 inbox yet either.

The person's words were "write it, clear and continue … without me nor
mistakes". So the step is the agent's to run. It must work with greenbelay at
`advise`, or absent.

## Goal

Skill text that, at each t03 boundary with nothing in flight and without
being asked, makes the agent:
1. file this session's inbox lines as tickets;
2. write the handoff into the repository (the programme map's `## Handoff`
   and its tickets, or the plan), never into memory or a file outside it;
3. land the handoff;
4. end the final message with exactly ``safe to /clear; next: `<prompt>` ``.

## Non-goals

- A size gate. The ticket and t03 say every boundary, boundary 1 included;
  clearing early at a small context goes under Not yet specified.
- SessionStart showing orphans and the frontier: t05.
- Changing greenbelay's `advise` note, which still tells the person to reply
  "write the handoff". That is amont-agent, so it goes to the inbox as a
  follow-up, and the live proof below files it.

## Code review

- greenharness-skills: unix (added over the proposal: the skill text carries the inbox append and git-dir shell the agent runs)
- grh: none — a version pin bump only
- relais: none — markdown only
- decisions: none — markdown only

## Behaviour: the step text

### worktree-task: a new `## Handoff` section (between Finish and Cleanup)

- **Follow-ups go to the inbox, at any time.** When the agent notices work
  that is not this task, it appends one line, under 512 bytes, with a single
  `>>`:
  ```bash
  inbox="$(git rev-parse --path-format=absolute --git-common-dir)/greenharness/inbox.md"
  s8=$(printf %s "${CLAUDE_CODE_SESSION_ID:-nosession}" | cut -c1-8)
  mkdir -p "${inbox%/*}" && printf '%s %s %s\n' "$(date +%F)" "$s8" "[due=YYYY-MM-DD] <text, naming the repo when not this one>" >> "$inbox"
  ```
  The `due=` field is optional.
- **When the step runs.** It runs at four boundaries:
  1. after Land the plan step 5, when implementation is not starting in this
     turn;
  2. after F10;
  3. when a programme ticket is closed and merged;
  4. after tag-release's verify and sweep.
- **Nothing in flight, for this session only.** Another session's worktrees
  and runs do not count. All of these must hold:
  - its worktree has no uncommitted or unpushed work (at boundary 1, the plan
    commit may be unpushed);
  - none of its background tasks, polls or relais runs is still running or
    waiting;
  - no question to the person is unanswered;
  - no worktree it made is left to tear down, apart from boundary 1's own.

  If anything is in flight, say what it is and print no line.
- **1. File the inbox** of every repository this session touched, not only this one.
  - File the lines that carry this session's `session8`, plus any line dated
    two or more days before today (t02's orphans; a date has no hour, so this is how the 24 h rule is read, recorded in t04's Resolution).
  - Each line becomes a `task` ticket with `mode = "afk"`. A `due=` field
    becomes `due`. The ticket also gets `## Look at` and `## Answer looks
    like`.
  - The ticket goes in the plan's programme, or else in this repository's
    `docs/programmes/follow-ups/`, whose map is created on first use.
  - Take the inbox atomically first (`mv inbox.md inbox.<session8>.filing`), so
    appenders start a new file and no two sessions file one line. Append the
    unfiled lines back with one `>>` each, then delete the taken file.
    `relais programme check` must exit 0.
- **2. Write the handoff.**
  - **In a programme,** replace the map's `## Handoff` section, which sits
    between Decisions so far and Not yet specified. Replace it; never append
    a second one. It holds:
    - the date and the boundary;
    - what is done and what merged;
    - the live state;
    - what is next, in order, by ticket name;
    - accepted gaps and lessons;
    - the plan's Your steps when there are any, so a clear does not lose
      them.
  - **Without a programme,** the plan is the handoff. Check that its next
    open phase, or its Outcome, states the next action.
  - Never write the handoff to memory or to a file outside the repository.
- **3. Land it** with the change it describes: the ticket's closing commit,
  or the plan's last commit, before that PR merges. Only what the merge
  itself reveals goes in one docs PR afterwards, merged with
  merge-when-green, and the line waits for that merge.
- **4. The line.** It is the answer's last line, with nothing after it:
  ``safe to /clear; next: `<prompt>` ``.
  - The prompt is one line, non-empty, at most 2,000 characters, with no
    backtick. It is what a fresh session needs to resume, for example
    ``resume <programme> <ticket id>: <gist>`` or ``implement
    docs/plans/<file> in <repo>``.
  - When the next step is the person's, the prompt says so. For example:
    ``what is next on <programme>; the person's steps are in its map``.
  - A clear-relay plugin, when installed, clears and submits the prompt
    after a short countdown that the person can stop.

### worktree-task: pointers and the F10 order

- Land the plan, a new step 6: "Boundary 1: see Handoff."
- F10 step 4: the Your steps block becomes the last lines *before the
  handoff line*, and step 5 is "Handoff".
- `tag-release` SKILL.md, at its final sweep: "Boundary 4: run
  worktree-task's Handoff."

### relais programme SKILL.md (self-contained: worktree-task may be absent)

- "The files": the map may carry an optional `## Handoff` section between
  Decisions so far and Not yet specified, and it is replaced, not appended.
- "Work a ticket", step 3 gains "file this session's follow-ups as task
  tickets".
- A new step 4, **Hand off**, gives the short form of the four steps and the
  exact line. Where worktree-task is installed, it points to its Handoff
  section. The old step 4, "Done", becomes 5.

### check.sh constraints

- The new text carries no `work.*` id, no `ADR-NNNN`, no `/Users/`, and no
  `homelab`.
- It does not depend on the greenbelay rule id.

## Phases

- [ ] Phase 1: greenharness-skills, in
  `parts/workflow/skills/worktree-task/SKILL.md` and
  `parts/gate/skills/tag-release/SKILL.md`. Released through tag-release
  (v0.13.0), then the grh pin is bumped and released, and installed on this
  machine.
- [ ] Phase 2: relais, in `claude-plugin/skills/programme/SKILL.md`, with a
  pointer plan in `docs/plans/`. Released as v0.68.0, installed, and the
  plugin reinstalled.
- [ ] Phase 3: decisions, on branch `prog/session-boundaries/t04-handoff-step`,
  in `docs/programmes/session-boundaries/t04-handoff-step.md` and
  `docs/programmes/session-boundaries/map.md` (plus the filed ticket's file):
  - the t04 Resolution, with the PRs, the releases and the live proof;
  - `status = "closed"`;
  - the Decisions-so-far line;
  - a "clearing early below 200k at boundary 1" line under Not yet specified;
  - the map's `## Handoff`, which the step itself writes, as its first real
    use;
  - a `task` ticket with `due` 7 days after install: clear-at-boundary firings against answers ending with the line (expected at least 90%).

## Verification

- `sh scripts/check.sh` exits 0 in greenharness-skills.
- `cargo test -p relais --lib install::` passes, and so does the full
  pre-push gate.
- The line in both skills matches the plugin's regex. Check it with
  `grep -o 'safe to /clear; next: `[^`]*`'` on each SKILL.md, and assert the
  match.
- The append command runs in a scratch `git worktree add --detach`. It writes
  to `<common-dir>/greenharness/inbox.md`, not into the worktree's own
  `.git` file, and the line is under 512 bytes.
- **Live proof**, after both installs:
  1. Re-invoke the installed worktree-task and programme skills.
  2. Append the amont-agent follow-up to the decisions inbox.
  3. At boundary 3 (this ticket closed and merged), file that line as a
     ticket in the programme, with t05 as the next work.
  4. Write the Handoff and the Resolution, recording the filed ticket and
     the boundary, both in the decisions closing commit.
  5. After that PR merges, end with
     ``safe to /clear; next: `resume session-boundaries t05-resume-on-clear: …` ``.
     The line comes after the merge, so the next session records it: t05's
     first act is to note in t04's Resolution that it was printed and that
     the plugin relayed it, as a one-line commit on t05's branch.

### Observed (2026-11-17, before the push)

- `sh scripts/check.sh` at f6d736d: exit 0 expected, exit 0 seen.
- `cargo test -p relais --lib install::` (via `greenbelay quiet`) at
  d0ddbef4: a pass expected, `ok 363.5s` seen. The later relais commits
  change only that SKILL.md's fallback bullet, and the pre-commit gate
  passed on each one.
- `grep -o 'safe to /clear; next: `[^`]*`'`, run on every file that
  carries the line: worktree-task, tag-release and programme expected; each
  printed the line once (worktree-task and tag-release with `<prompt>`,
  programme with `<the next session's first prompt>`).
- The append from a detached linked worktree, `/tmp/t04-scratch/inbox-test.sh`:
  expected to land in the common `.git`; seen at `r/.git/greenharness/inbox.md`,
  a 54-byte line.
- The take with appends running, in the same script: 2 appenders of 300 lines
  each, while 10 takes file one session. Expected 10 filed, 600 kept,
  0 duplicates and no `.filing` left; seen exactly that.
- Under zsh 5.9:
  - a text holding `'`, `$HOME` and backticks was stored literally;
  - the take name was unique (`inbox.3571e691.62624.filing`);
  - `find -mtime +0` listed 0 of a fresh take;
  - outside a repository, the chain stopped before the append.
- The take as two separate tool calls, with an inbox stamped 2026-11-14:
  - call 1 took it, touched it and printed its path;
  - in call 2, another session's `find -mtime +0` listed 0 (0 expected);
  - deleting by the printed path left nothing behind.
- The live proof runs at Phase 3, recorded in t04's Resolution.

## Implementation review

- greenharness-skills, implementation-review: approve-with-changes, then
  approve-with-changes in the Delta, then approve (699c905). Fixed:
  - reading another session's take while it was still being filed;
  - the `Your steps: none` line;
  - dating the take with `touch`;
  - `$$` changing between tool calls.

  About 101k tokens, 118 s.
- greenharness-skills, unix: approve-with-changes, then
  approve-with-changes in the Delta, then approve. Fixed:
  - the chained `rev-parse`;
  - a unique take name;
  - the single-quoted text;
  - `find` in place of a glob;
  - variables set again in each command;
  - the take's mtime and printed path.

  About 81k tokens, 88 s.
- relais, implementation-review: approve-with-changes, then
  approve-with-changes in the Delta, then approve (fa5bdc2). Fixed:
  - the fallback now spells out the session8 cut, orphans and the take;
  - the inbox path is absolute;
  - it covers every repository touched.

  About 112k tokens, 95 s.

## Decision log

- 2026-11-17, from review: "no PR of its own is open" became an in-flight
  condition. A PR that F9 left waiting on `merge-after:` gets a handoff
  but no line. tag-release's fallback checks the same list. Before this,
  the Behaviour section did not list an open PR.
- 2026-11-17, from review: the inbox shell differs from the Behaviour
  section's snippet:
  - the steps are chained with `&&`;
  - `<text>` is single-quoted;
  - a missing session id is cut to `nosessio`, and such a line is filed
    only as an orphan;
  - the take is `inbox.<s8>.<pid>.filing`, touched when it is made, and
    its path is printed for later calls;
  - a take another session left is read only once it is more than a day
    old.
- 2026-11-17: a session that holds its own take for more than a day can
  have it read by another session. This is accepted: a boundary does not
  last a day.
- The plan stays `active`. The phases are ticked and `status: done` is set
  in the release PR, which carries the version bump, once the release is
  verified.

## 🧑 Your steps

- none

<!-- panel: repos=greenharness-skills,grh,relais,decisions reviewers=backend body-sha=ac22ca3afb60 -->
