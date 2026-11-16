---
name: plan-review
description: Run the expert review panel on a plan before ExitPlanMode, and again as a delta after the person asks for a change. Use in plan mode every time a plan is about to be presented. The greenpiste plan-review-panel hook refuses a plan whose panel did not run.
---

# plan-review

Every plan is reviewed by a panel of experts **before** the person sees it.
The panel follows what the plan touches, and greenpiste computes it, never
from keywords. With a greenpiste older than 3.22.0
(`greenpiste --version`), only the area table below holds, and `adds=`
takes the values it took then: `cli`, `ui`, `ops`, `large`,
`lang:<language>`.

When every phase of the plan names, in backticks, the files it touches,
the seats come from those files' types:

| the named files | agents |
|---|---|
| always | `plan-review-backend` |
| `.rs`, `.go`, `.py`, `.ts`/`.js` and their manifests | `plan-review-language` for that language |
| `.tsx`/`.jsx`, CSS, stories | `plan-review-react`, `plan-review-ui-design` |
| Kubernetes, Helm, Flux, Terraform, a Dockerfile, CI workflows, other YAML that is not a tool's configuration | `plan-review-platform` |
| any code file of a repository with a command line | `plan-review-unix`, `plan-review-tui` |
| `adds=screen` | `plan-review-ux-research`, `plan-review-game-ux` |
| `adds=contract` | `plan-review-po`, `plan-review-architect` |

When a phase names no file, the panel follows the areas of the plan's
repositories instead, and `plan-panel` says so on stderr:

| area | agents |
|---|---|
| always | `plan-review-language` for each language, and `plan-review-backend` |
| ops | `plan-review-platform` |
| a command line | `plan-review-unix`, `plan-review-tui` |
| large (500 or more files or own commits) | `plan-review-po`, `plan-review-architect` |
| an interface | `plan-review-react`, `plan-review-ui-design`, `plan-review-ux-research`, `plan-review-game-ux` |

Rounds are bounded: round 1 is the whole panel, round 2 is a delta, and
there is no round 3. A change the person asks for gets one delta review and
never a loop.

## 0. The machine comment

**The plan id.** `greenpiste plan-panel` gives the plan a `plan-id:` line in
its front matter the first time it runs, and a fresh one once the person has
approved that id. Never write, copy or edit `plan-id:` by hand, not even
into a new plan written over an old file (worktree-task's landing step is
the one exception: it copies the line word for word into the landed plan): the id is how the ledger, the panel
and `stats --time` tell one plan from the next in a reused plan file. After
`plan-panel` runs, re-read the file before the next Edit (it may have
written the front matter). A plan-panel that prints `ledger busy` or
`plan changed under plan-panel` wrote nothing: do what its message says.

The plan's **last line** names the repositories it touches, and the areas it
adds that do not exist yet:

```
<!-- panel: repos=amont-agent,decisions adds=ui -->
```

- Repository names resolve under greenpiste's plan root
  (`GREENPISTE_PLAN_ROOT`). A repository kept
  elsewhere has `git config --global greenpiste.plan-review.<name>.path`
  set, for example `dotfiles` → `~/.local/share/chezmoi`.
- `adds=` takes `cli`, `ui`, `screen`, `ops`, `contract` (`large` is its
  old name) or `lang:<language>`. It declares what no named file shows:
  - `contract` when the plan adds a module, crate or repository, or
    changes a contract another repository consumes;
  - `screen` when the Behaviour adds a screen or a flow;
  - an area the plan creates: a first CLI, UI or manifests, or a new
    repository (`adds=lang:rust`).

  A plan seated from its files without the `contract` or `screen` it needs
  loses those seats; the backend reviewer holds it to them.

The plan also needs a `## Review panel` section directly under the H1. Write
a placeholder line there now; step 7 fills it.

When `~/.claude/skills/plan-picture/check.py` exists (the `plan-picture`
skill is installed), the plan needs a `## Picture` section after
`## Review panel`: follow that skill, then run its checker before seating
the panel, and fix every finding first:

```sh
python3 ~/.claude/skills/plan-picture/check.py <plan.md>
```

Exit 1 is a finding to fix, exit 2 a usage error, never a pass. When the
file does not exist, skip this: a plan needs no picture.

And a `## Code review` section in the body, after `## Non-goals`: which
expert profiles review the code at the branch's close (worktree-task F4b),
beside implementation-review. Propose it with

```sh
greenpiste plan-panel --code-review <plan.md>
```

which prints, per repository, `<repo><TAB><profiles>`, or
`<repo><TAB>none<TAB><reason>` (`markdown only`, `no reviewed file type`,
`no file named`, `no language area`), from the file types of the files its
phases name, or from its areas when a phase names no file. Write one line
per repository:

```markdown
## Code review
- my-app: backend, lang:rust, unix (tui left out: no output change)
- docs-repo: none — markdown only
```

A profile left out of the proposal names its reason in parentheses, and
the panel's backend reviewer checks it. The section is in the body, not the
front matter, so the panel's sha binds it. A plan without it keeps a single
implementation review.

## Models

Every panel launch carries `model: "opus"` on the `Agent` call: round 1,
round 2, the step 8 delta and every backend re-run. The agents inherit the
root model by default, so the call is what keeps the preference. A launch
that fails on model availability follows the `agent-model-fallback` skill.

## 1. What to run

```sh
greenpiste plan-panel <plan.md>
```

The first line reads `repos=… areas=… body=<12> panel=full|delta|current
seats=paths|areas counts=…`, then one agent per line; `counts=` is one
token (`repos:3,phases:6,prs:3,releases:2,person:2,words:3100,steps:2,merge-candidates:2+3;5+6`),
read by key name: a new key goes before `merge-candidates`, which stays the
last comma field. `steps:` counts the actions only the person can run;
decisions stay in `person:`.
the plan's size for step 7 and for the backend seat. `words:A/B` is the
body now and at round 1 (read it as `A words`); a `-` value counts as zero; `areas=` lists the classes the
seats came from. That list is exactly what the hook will require;
launch that list, no more and no fewer. `panel=current` means nothing
changed since the last accepted body: go to step 7.

## 2. The shared brief

Build it once and give it to every reviewer, so that each one does not
explore the repositories on its own. That exploration is where the tokens
go, about 40–80k per reviewer.

- The `plan-panel` output (areas, and why this panel).
- Each repository's top level:
  `git -C <repo> ls-tree --name-only origin/HEAD`.
- The decisions the plan bears on: `aval relevant --text "<plan title and
  key terms>"`, then `aval resolve <key>` on each key it names. Include the
  verdicts, not the ranking.
- The files the plan names, with line counts (`wc -l`).
- The design lookup, for a repository with an interface only: when an
  agent named `design-system-lookup` is installed (its file exists under
  the agents directory), run it once on the plan before the panel, passing
  the decisions block above when there is one, and give its output to
  every seat as a `design-lookup` block. When no such agent is installed,
  skip this step silently. The slot names an agent contract, never a
  product; seats read the block as their **Design-system lookup** section
  says.

## 3. Round 1: the whole panel

1. Tell the person first, in one line:
   `📍 <project>: reviewing "<plan title>" with <agent names>; about 3–6 min, you can switch projects meanwhile.`
2. For each agent, get its review block: run `plan-sha --block` with the
   flags its `plan-panel` line ends with (`--lang rust` for a language
   review, `--slice <role>` for a seat bound to its slice):

   ```sh
   greenpiste plan-sha --block [--lang rust] [--slice lang:rust] <plan.md>
   ```

   With `--slice` it prints two lines: the block, and `Your slice: …`,
   which tells the reviewer which phases are its own. A greenpiste older
   than 3.23.0 prints no `--slice` in `plan-panel`; run the plain block then.

3. Launch **all** the agents in ONE message, in parallel. Each prompt
   carries, in this order:
   - the review block's stdout lines (one, or two with `--slice`),
     verbatim; never its stderr;
   - `Round 1.`;
   - the shared brief;
   - "Read the plan at the block's path. Open at most 10 more files or
     1,500 lines. Follow your output contract."
4. As each one returns, post one line, so that a round longer than 10 s
   shows what is done and what is left:
   `k/N returned: <role> <verdict> (<tokens>, <seconds>)`, for example
   `2/4 returned: lang:rust approve-with-changes (35k, 45 s)`.

A launch that fails follows the `agent-model-fallback` skill: when the
failure is model unavailability, relaunch the same agent once with no
`model` on the call; once a model is seen cooling down, launch its later
seats on the fallback at once. A failure the policy excludes is not
relaunched; any other failure is relaunched once as it was. A launch that fails again becomes a 👉 decision for the person, and is
never silently dropped. In the review section, name each seat that ran on
the fallback.

## 4. Merge

The main session keeps a ledger, not the plan. Editing the plan there
resends the old and new text of every edit: on 2026-10-10 the integration
edits cost more of the session's context than the four reviews they applied.

- Write one line per finding: `accepted`, `rejected: <why>`, or
  `👉 decision`. Findings that duplicate each other become one line.
  Findings that conflict become a 👉 decision for the person, with both
  positions.
- A `remove` or `merge` finding is accepted or rejected like any other;
  rejecting one needs a reason that names whom the phase or safeguard
  protects.
- Count the growth before editing. Take the body as presented: the word
  count (`wc -w`) of the plan the panel first reviewed, kept from round 1's
  scratch copy. Every round compares to that same number, never to the
  previous round. Count the body the accepted edits would produce:
  - a round that would add a phase, or grow the body past ×1.25 of the
    body as presented, states for each addition what it protects;
  - past ×1.25, the additions become one 👉 decision for the person
    instead of edits. `blocking` findings, and findings that fix a wrong
    or unverifiable statement, are exempt and stay edits.
- Record the round, BEFORE the plan is edited (it saves the reviewed body
  only while the file still holds it), with one object per finding on
  stdin; `section` is the plan heading it is about, `area` one of
  cli|ui|screen|ops|contract|lang:<x> (`large` with a greenpiste older
  than 3.22.0) when it is clear:

  ```sh
  echo '[{"role":"tui","severity":"high","disposition":"accepted","section":"Behaviour","area":"cli"}]' \
    | greenpiste plan-review record <plan.md>
  ```

  It prints `wrote N rows (round R, plan <sha12>)`. Exit 1 (ledger or a
  missing agent id) is reported in one line and never stops the review.
- `cp` the plan to a scratch file first: round 2's diff is `diff -u`
  against that copy.
- Apply the accepted findings with no model: each reviewer's `Patches:`
  block is read from the transcript, so stdin names only the findings:

  ```sh
  echo '[{"role":"tui","finding":1},{"role":"unix","finding":3}]' \
    | greenpiste plan-apply <plan.md>
  ```

  It prints `applied tui#1 <section>` or `unmatched tui#3: <reason>` per
  finding, then `applied A, unmatched U, sha <sha12>`, and exits 0 when
  everything matched. On 2026-10-11 the four subagents that applied one
  review's findings cost about 320k tokens, more than the reviews.
- Exit 3 means some patch did not match (the matched ones are written; a
  `next:` line and an `<<<APPLY path=… sha=…>>>` block end stdout). Apply
  the remainder the cheapest way that fits:
  - `unmatched … overlaps …` never goes to a subagent: two reviewers edited
    the same lines, and a subagent resolves that with one merged edit that
    contains neither `new_string`, so `--check` cannot verify it (measured
    2026-10-11: 12 of 12 such patches came back unverified, after a 107k
    fallback). The main session reads the two patches, writes the merged
    pair itself and re-runs `plan-apply` with it as a `patch` object, as
    below.
  - at most 3 `absent` findings, each edit under about 15 lines: the main
    session writes the pair itself and runs `plan-apply` again with it on
    stdin, so the edit is applied, recorded and checked like any other —
    the old and new text cost less than a subagent's read of the plan:

    ```sh
    echo '[{"role":"tui","finding":3,"patch":{"old_string":"…","new_string":"…"}}]' \
      | greenpiste plan-apply <plan.md>
    ```

  - otherwise (more or larger `absent` findings) ONE `general-purpose`
    subagent, in the foreground, with
    `model: "sonnet"` on the call. Its prompt starts with the `<<<APPLY …>>>`
    block verbatim, then the unmatched findings with their evidence and
    edit, and ends with: run `greenpiste plan-apply --check <plan>` with
    the findings on stdin as the last command and return its output only.
    `sonnet` is a preference, not a pin: relais's router keeps it when
    routing is off or abstains, and overrides it when its table decides.
    If the call fails because `sonnet` is unavailable, follow
    `agent-model-fallback`: one relaunch with no `model`, and only when
    `greenpiste plan-sha --short <plan>` still prints the sha it printed
    before the launch. A changed plan means edits landed: do not relaunch
    (it would apply them twice); make it a 👉 decision.
  After the subagent, record what it did (it finds the launch by the
  `<<<APPLY` block, so this is the subagent path only):

  ```sh
  echo '[{"role":"tui","finding":3}]' | greenpiste plan-apply --record-fallback <plan.md>
  ```

  Exit 1 (no transcript, ledger) is reported in one line and never stops
  the review: apply the edits by hand and go on. Exit 2 is a usage error
  and nothing was applied: when it names a reviewer's patch (an empty
  `old_string`), drop that finding from stdin, re-run, and apply it in the
  remainder.
- Do not read the plan back. Read a section only to settle a 👉 decision.

## 5. Round 2: delta only

Re-run the reviewers whose verdict was `rework`, plus
**`plan-review-backend` always**, plus every seat `plan-panel` names that
the edits made stale. Backend must bind the FINAL body, because the hook
requires it: every edit to the body after backend's review makes backend
stale. A seat bound to its slice (greenpiste 3.23.0) is stale only when an
edit touched its slice; then the hook names it, with the span that moved.

1. Post: `📍 <project>: round 2, re-running <names>, about 2 min.`
   Returns use the same `k/N returned:` line.
2. Get fresh blocks: re-run `greenpiste plan-panel <plan.md>` and use the
   flags each seat's line now ends with (a seat can gain or lose its slice
   with an edit). The sha changed with the edits.
3. Each prompt carries:
   - the block's stdout lines (two with `--slice`), verbatim; never its
     stderr;
   - `Round 2.`;
   - that reviewer's round-1 findings, and that its patches were applied
     by `plan-apply` where they matched;
   - the diff of the plan since round 1 (for a sliced seat, the part of it
     inside its slice is what it must answer for);
   - "answer resolved / not resolved / new blocker for each".

A round-1 reviewer may be resumed with `SendMessage` instead of a fresh
launch. The hook counts the resumed round once the message STARTS with the
new `<<<PLAN path=… sha=…>>>` block (for a sliced seat, the block's two
stdout lines) and the agent's reply has completed
(greenpiste ≥ 3.16.1). A message without the block binds nothing, so the
reviewer stays stale.

After round 2, only a `high` or blocking finding may change the body. A
`medium` or `low` one gets no edit: it goes in step 7's review section, as
`carried into implementation`, and the landed plan keeps it beside the
body. An edit after round 2 makes backend stale, so a blocker that forces
one is applied as in step 4 (`plan-apply`, then the remainder), and
backend alone re-runs on it.

## 6. No round 3

Whatever stays unresolved goes to the person as a 👉 decision, with both
positions stated. It never becomes another round.

## 6b. Final review: Codex (optional)

Only when the `codex` CLI is installed; otherwise skip to step 7 and write
`codex: not installed` in the review section. After the panel's last round,
one review by Codex, a model from another vendor, reads the body the panel
accepted. It runs once per plan, and never on a step 8 delta.

1. Post: `📍 <project>: final review by Codex, about 2–4 min.`
2. Write the prompt to `<scratch>/codex-prompt.md`, in this order:
   - "You are in Plan mode: read only. Do not create, edit or delete any
     file, and run no command with side effects (no install, build, commit
     or push).";
   - the shared brief from step 2;
   - the plan's path;
   - each panel finding, one line with its disposition from step 4;
   - "Review the plan as a staff engineer. Report what the panel missed or
     got wrong; do not repeat its findings.";
   - the `## Output` section of `~/.claude/agents/plan-review-backend.md`,
     verbatim.
3. Run it in the foreground, bare, with no pipe:

   ```sh
   timeout 1800 codex --no-daemon exec \
     --dangerously-bypass-approvals-and-sandbox --ephemeral \
     -C <repo> -c model_reasoning_effort="high" \
     -o <scratch>/codex-review.md - < <scratch>/codex-prompt.md
   ```

   `--no-daemon` goes before `exec`; `exec` refuses it. `codex exec` has
   no Plan mode switch, so the first prompt line is the only thing that
   keeps it read only. The timeout comes from the Codex history on
   2026-10-15: 133 plan reviews at medium effort took 99 s at the median,
   218 s at p95 and 453 s at most, and one stalled for 96 min with no event.
   1800 s is twice the longest run, doubled for high effort.
4. Done when exit is 0 and `codex-review.md` has a `Verdict:` line. Any
   other result is relaunched once. If it fails again, the review section
   says `⚠ codex: <exit or reason>`, and the plan goes on: Codex never
   blocks it.
5. Run `git -C <repo> status --short`. A change Codex made is reported to
   the person and never kept.
6. Treat its findings as round 2 does: only a `high` or blocking one changes
   the body. Apply it with `plan-apply`, `role: "codex"`, and its patch
   copied from `codex-review.md` as the `patch` object. Then
   `plan-review-backend` alone re-runs, because the edit made it stale.
   Every other finding is `carried into implementation`.

## 7. Write the results

Writing these never changes the body's sha, so the reviews stay bound.

- **The `## Review panel` section**, under the H1, at most 5 lines of
  **about 20 words each**. The person reads it after being away, working
  on several projects, so it leads with the decision and says what comes
  next:
  1. `⚠ unreviewed: <why>`, only when the person asked to skip the panel;
  2. `👉 **Decide:** <what the person must decide>`, or
     `none — approve if <the one-line bet>`;
  3. `📍 <repositories> · <counts in words, or where the work stands once a phase ships> · next: <one action>. Panel: <roles>.`,
     each role with the model it ran on (one model named once when every
     seat ran on it), and Codex last.
     - The counts come from `counts=` and read `6 phases`, `3 PRs`,
       `2 releases`, `2 decisions` (from `person:`), `2 steps for you` (from
       `steps:`, the actions only the person can run), `2 merge candidates`,
       `3100 words`. Leave out a zero count, and use the singular for 1.
     - Stay within about 20 words by dropping, in order: `words`, merge
       candidates, PRs when equal to the repository count, then the list of
       repositories (for `N repos`) when there are more than three. PRs
       equal to the repository count are the usual case, so the example
       leaves them out.
     - For example
       `📍 my-app · 6 phases · 2 releases · next: Phase 1. Panel: backend (fable-5-1), tui (sonnet-5-5), codex (gpt-6-astra).`,
       or once work has shipped,
       `📍 my-app · Phases 1–3 shipped · next: the nine agent files. Panel: backend, tui (sonnet-5-5).`;
  4. `**Changed by review:**` up to 3 items;
  5. `**Verdicts:**` the counts per verdict, any delta rework that went
     to the person, the count of findings `carried into
     implementation` (listed in the full reviews), the words as
     presented → final (×ratio), and the `remove` and `merge` findings
     accepted, for example
     `**Verdicts:** 2 approve-with-changes; 3 carried; words 776 → 900 (×1.16); remove 1, merge 0.` Token counts and
     timings go in the full reviews, not here.
- **`## Full reviews (reference)`** as the last heading: each reviewer's
  verdict, findings, tokens and wall time, Codex's included, as a plain
  section with no `<details>`.
- **The machine comment** as the last line:
  `<!-- panel: repos=… adds=… reviewers=<roles> body-sha=<plan-sha --short> -->`.

Then call ExitPlanMode.

## 8. The person asks for a change

After ExitPlanMode is rejected with feedback:

1. Edit the plan as in step 4's remainder: `plan-apply` with a `patch`
   object under `role: "person"` when small, else the Sonnet subagent, with
   the person's words as the accepted line; there is no reviewer patch for
   it.
2. Run `greenpiste plan-panel <plan.md>`. It prints `panel=delta`, with
   backend plus the reviewers of any area that is new, plus every seat
   bound to a slice that the change touched (greenpiste 3.23.0).
3. Launch those once. Each prompt carries:
   - the block's stdout lines (two with `--slice`);
   - `Delta.`;
   - the person's words, quoted;
   - the diff (for a sliced seat, the part inside its slice is what it
     answers for);
   - "check how the change is made, not whether".

   A reviewer from the same session may be resumed with `SendMessage`
   instead: the message starts with the fresh block and carries the same
   items; it counts once the reply completes (greenpiste ≥ 3.16.1).
4. A `rework` from them becomes a 👉 decision, never a re-run.
5. Update the review section, then call ExitPlanMode.

## If the hook refuses

The refusal names what is missing (`missing for repos=X: <roles>`) or stale
(`stale (reviewed an older body)`), and, with greenpiste 3.23.0, a seat
bound to its slice that must re-run:
``stale (its slice changed: Phase 2) for repos=X: <role>; re-run: `greenpiste plan-sha --block … --slice <role> <plan.md>` ``,
or `its slice changed: the order of its phases`, `it has a new slice`, or
`it now binds the whole body`. Run exactly those, each block with the
command between the backticks as printed, then present again.
After 2 refusals of the same plan, the hook hands the decision to the person
with `UNREVIEWED: refused N×`, naming the missing reviewers and the body
each time, so a repeated prompt still says something new. Do not try to
get past it. Tell the person what is missing and why.

A warning seen again and again stops being read, so the prompt must stay
rare. The hook cannot see how the person answers; the number it can give
is how often it asked. Before the panel's usefulness is decided, count
them:
`grep -c 'plan-review-panel deny asked' ~/.claude/greenpiste/journal.log`.

## Skipping

Only the person can skip the panel. Write `⚠ unreviewed: <their reason>` as
the first line of the review section. The hook then asks the person to
confirm, and remembers nothing.
