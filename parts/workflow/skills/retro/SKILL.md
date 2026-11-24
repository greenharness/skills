---
name: retro
description: Retrospective on one or more sessions: finds where the agent lost time or made a mistake, and proposes the harness change that stops it, most severe first.
disable-model-invocation: true
---

# retro

You do a **retrospective**. You do not fix the session's task. You find what
in the agent's **environment** made the session slower or wrong, and you
propose the one change that stops it next time. You change nothing, except
the cause tally in step 4. The person picks.

Adapted from mattpocock/skills (see [NOTICE.md](NOTICE.md)).

## 1. Find the sessions

- **Arguments are transcript paths**: use them.
- **No argument**: use the current session. It is the newest `*.jsonl` in
  `~/.claude/projects/<slug>/`, where `<slug>` is the cwd with every `/` and
  `.` changed to `-`. Before you read it, write the file name and the
  session id, so the person can correct you.

A transcript is large (often 10–60 MB). Never read one whole. Read it with
`jq` filters and `grep -n` windows. These filters give the signal:

```sh
T=<transcript.jsonl>
# what the person typed (corrections live here)
jq -r 'select(.type=="user" and (.message.content|type)=="string") | .message.content[0:400]' "$T"
# tool calls that failed
jq -c 'select(.type=="user") | .message.content[]? | select(.type=="tool_result" and .is_error==true) | .content|tostring|.[0:300]' "$T"
# tool calls by name, most used first
jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="tool_use") | .name' "$T" | sort | uniq -c | sort -rn
# skills that ran
jq -r 'select(.type=="assistant") | .message.content[]? | select(.type=="tool_use" and .name=="Skill") | .input.skill' "$T"
```

Also read:
- the greenbelay journal lines for the session: `grep ' <id8> '
  ~/.claude/greenbelay/journal.log` (`<id8>` is the first 8 characters of
  the session id; the 4th field is the stance: `deny`, `advise`, …);
- `greenbelay mine`: mistake shapes that no rule names yet.

Done when you can name, for each session, its task in one line and its
three most expensive moments (time, tokens or a wrong result), each with a
line of evidence.

## 2. Find candidates

Look for candidates in each class. A class with nothing is fine; say so.

- **Navigation**: the agent searched long for a file, a command or a fact.
  Would one pointer have found it?
- **Automated checks**: the agent made a mistake that a lint, a type check,
  a test or a hook could catch. First look for a check that exists but is
  not wired, or fails open. That is the finding, not a new check.
- **Coding rules**: the review did not catch a mistake. Is a rule missing,
  unclear, or not enforced?
- **Always-on text**: CLAUDE.md, MEMORY.md, skill descriptions. Is a line
  wrong, stale, or too long (`guidance.always-on-is-an-index`)? Did a skill
  not fire when it should have (for example `diagnosing-bugs` on a red
  check), or fire when it should not have (`guidance.pointer-names-when`)?
  Does a prohibition lack its positive target (`guidance.state-the-target`)?
- **Tool economy**: a call that returned much more than it needed (a whole
  file, a full log, a re-read), or a slow loop.
- **No-ops**: an instruction that changes nothing, because the model does
  it anyway (`guidance.delete-no-ops`).
- **Information access**: the agent did not have a log, a metric, or a
  read-only view that would have answered the question.

Give each candidate exactly one cause, from this fixed list, so the same
mistake keeps the same name from one retro to the next:

- **A greenbelay rule name**, when a rule names the mistake
  (`whole-file-dump`, `file-reread`, `pipe-to-tail`, `chain-with-and`, …).
  `greenbelay status` lists the names.
- **A relais cause**, when the mistake is a relais run failure. Write it
  with the `relais:` prefix: `relais:scope_exceeded`, `relais:check_failed`,
  `relais:criteria_unmet`, `relais:criterion_unreported`,
  `relais:same_failure_recurrence`, `relais:review_findings`. The names come
  from relais's cause query
  (`docs/programmes/run-lessons/cause-counts.py --list-causes --class guidance`
  in the relais repository); the query takes the name without the prefix.
  When `~/.local/state/relais/ledger.sqlite` does not exist, use no
  `relais:` cause.
- **An agent-behaviour cause** that no rule or reason names yet:
  `stops-before-verifying`, `skill-not-loaded`, `skill-misfired`,
  `pointer-missing`, `check-not-wired`, `rule-missing`, `stale-text`,
  `no-op-text`, `info-missing`.
- **`unlisted`**, when nothing fits. Then propose the new cause name as a
  candidate of its own. Do not invent a name inside another candidate.

Done when every candidate has one cause from the list.

## 3. Give each candidate exactly one fix

Use the first fix that applies:

1. **Mechanical mistake** (a fixed pattern, a banned command, a path rule):
   a greenbelay rule (a hook), or an amont check in the repo's
   `amont.conf`. A check is better than a written rule.
2. **Judgement call**: a proposed aval rule or ADR in the `decisions`
   corpus. You propose it; the person decides it.
3. **Missing pointer**: one index line in CLAUDE.md or MEMORY.md, or a skill
   description made sharper.
4. **No-op or stale text**: delete it.
5. **A fact only this machine knows**: a memory file.

If an earlier report in `~/.claude/retro/` already proposed the same fix,
drop the candidate, unless its evidence is new. Then say "again, new
evidence". Tally its cause in step 4 even when you drop it.

A fix names its target: the cause's count, its denominator and the week
(`harness.change-targets-a-counted-cause`). When no count exists, the fix
ships its count first. A cause with fewer than 5 events in 28 days is not a
target: its candidate reads `Fix: none yet; under 5 events in 28 days`.

## 4. Report

Print the list in your reply, most severe first (no report file: a headless run captures the reply; the tally below is the one file). Severity is the cost if nothing changes:
a wrong result before lost time, lost time before lost tokens.

For each candidate:

```
### <n>. <one-line title>  (severity: high | medium | low)
Evidence: <transcript path:line, or the tool call and its result, short>
Cause: <one cause from step 2>
Target: <count>/<denominator> <unit>, week of <Monday>; recount: <command>
Fix: <the one fix>  →  <where it lands: file, repo, rule id>
```

The Target line takes its numbers from the cause's own count:

- a `relais:` cause: the cause query's row for the last complete week, and
  its recount command with an absolute or `~` path, so it runs from any
  directory;
- a greenbelay rule: the replay's row for the last complete week, as
  `<firings>/<calls> Bash calls`, with this recount (`<rule>`, and
  `<from>`, the week's Monday as `YYYY-MM-DD`):
  `greenbelay backtest --rule <rule> --since <from> --json | jq -r '.version as $v | .rules[] | select(.replay=="exact") | .id as $r | .weeks[] | select(.week=="<from>") | "\(.week) \($r) \(.fires) \(.calls) \(.per_1000) v\($v)"'`.
  It prints `week rule firings calls rate version`. When it prints
  nothing, the replay cannot count that rule (its `replay` is `none`: it
  fires on another tool, only the live session decides, or the hook checks
  the world at the time), or this greenbelay is older than the label. Then
  try the roll-up, with the same `<rule>` and `<from>`:
  `greenbelay rollup --json | jq -r '.weeks[] | select(.week=="<from>" and (.partial|not)) | .week as $w | .rules[] | select(.rule=="<rule>" and .calls!=null and .calls>0) | "\($w) \(.rule) \(.firings) \(.calls) \(.rate) \(.tool)"'`.
  It prints `week rule firings calls rate tool`: the Target reads
  `<firings>/<calls> <tool> calls, week of <Monday>`, a tool of `any` reads
  `tool calls`, and this command is its `recount:`.
  When that prints nothing too (no closed week yet, a rule with no tool, or
  a greenbelay older than the roll-up), write `Target: uncounted; count by:
  no roll-up row for <rule> (no closed week, no tool, or an older
  greenbelay)`;
- an agent-behaviour cause: the tally below, as `<sessions with the cause>/
  <sessions retro'd> sessions retro'd`, with this recount (`<cause>` and
  `<from>`, `<to>` as `YYYY-MM-DD`, the week's Monday and the next one):
  `awk -F'\t' -v c=<cause> -v a=<from> -v b=<to> '$1>=a && $1<b {if($3=="__reviewed__")r[$2]=1; if($3==c)h[$2]=1} END{n=0;for(s in h)if(s in r)n++; m=0;for(s in r)m++; print n"/"m}' ~/.claude/retro/causes.tsv`;
- no count at all: `Target: uncounted; count by: <how>`.

Start the report with one line: `candidates: <N>`.

Then append the tally to `~/.claude/retro/causes.tsv` (create the directory
when it is missing), one tab-separated line `<session start date> <session
id> <cause>`, written in a single append:

- one `__reviewed__` line for every session you read, also when it gave no
  candidate;
- one line per cause you observed, dropped candidates included;
- no line whose session id and cause are already in the file.

The tally counts sessions retro'd, not all sessions. It is the only file
retro writes.

Done when every candidate has evidence, one cause, one Target and exactly
one Fix line (a fix, or `none yet` under the 5-event floor), and the tally
holds a `__reviewed__` line for each session read.
Retro does not apply any fix.
