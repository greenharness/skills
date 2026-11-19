---
name: worktree-task
description: Create or tear down a per-task git worktree, isolated from the live checkout — landing the approved plan as the first commit and running the verification loop (and, for UI, the localhost preview) before the single push. Use at the start of substantive edit/commit work in any repo, and again when that work is done.
---

# worktree-task

Standing rule (see `~/.claude/CLAUDE.md` § Git worktree isolation for agent work): do substantive edit/commit work in a per-task worktree, not the shared/live checkout — the user runs their own git activity (branch switches, commits, releases) in that same checkout concurrently, and collisions have repeatedly clobbered uncommitted work on both sides.

The convention for worktree paths: a **sibling directory** named `<repo>-wt-<slug>`, e.g. `../app-wt-toast`. Use that convention unless the user specifies otherwise.

## Args

- `args` empty, or `start <slug>` / `<slug>`: **start** mode — create a new worktree.
- `args` = `finish` / `done`: **finish** mode — rebase, push, and remove the *current* worktree (run this from inside the worktree, or pass the path).
- `args` = `cleanup <slug>` / `remove <slug>`: **cleanup** mode — abandon and remove a worktree without pushing (use for scrapped work; confirm with the user before discarding uncommitted changes).

If no slug is given in start mode, derive a short kebab-case one from the task at hand and confirm it with the user before creating the worktree.

## Start

### Check what is in flight (before the worktree exists)

Another session may already work this change, or may have just landed it.
From `<repo-root>`, for each repository the plan's `repos:` names (else the
current repository), run:

```bash
git fetch origin -q
greenbelay board --repo <repo> --fetch
```

- For each worktree, branch or plan of another session that overlaps this
  task, write one line: what it is, and the next action. Read its plan or
  pull request, message that session (`ListAgents` names the peers,
  `SendMessage` reaches one), or ask the person. Create the worktree below
  only when no other session already works this change.
- A commit under "just landed" that already does this task: stop and tell
  the person.
- When `greenbelay board --help` fails (greenbelay absent), run
  `git log --oneline HEAD..origin/<default>` instead and say the board is a
  gap.
- Done when every overlap has a next action, or the output names none.
  Then create the worktree.

### Create the worktree

```bash
cd <repo-root>
git worktree add --no-track ../<repo>-wt-<slug> -b <branch-name> origin/main
```

- `--no-track` is required. Without it git makes the new branch track `origin/main` (or `origin/dev`), and `amont land` pushes to the upstream: the work lands on the default branch with no pull request. This happened twice in one week (2026-10-21, 2026-10-25) on a repository whose default branch no hook guards.
- A branch that already exists (an earlier session's worktree): run `git branch --unset-upstream` in it.

- Pick `<branch-name>` following this repo's existing convention (check recent branch names via `git branch -a` / `git log --all --oneline -20` if unsure — e.g. `feat/…`, `fix/…`).
- After creating it, `cd` into the new worktree path for the rest of the task. Confirm you're on the right branch with `git branch --show-current` before editing.
- Do NOT symlink `node_modules` or other deps into the worktree as a shortcut — it has broken dev-server file resolution before (see `application_landscape_e2e_debug_traps` project memory). Let the worktree install its own deps — the next step does it.

### Bootstrap dependencies (before the first commit)

A fresh worktree has no `node_modules`, `.venv` or build cache. The plan
commit below is the FIRST commit, and where amont is installed that commit
runs the project's tests at pre-commit — so without this step the very first
gate fails with "command not found" and the session stops to install.
Bootstrap once here, from the worktree root, frozen to the lockfile so the
tree stays clean:

| Present at the root | Run |
| --- | --- |
| `relais.toml` with a `[[verification.profiles.*.setup]]` | that `argv`, first — it is the declared bootstrap |
| `pnpm-lock.yaml` | `pnpm install --frozen-lockfile` |
| `package-lock.json` | `npm ci` |
| `yarn.lock` | `yarn install --immutable` (Yarn 1: `--frozen-lockfile`) |
| `uv.lock` | `uv sync --frozen` |
| `go.mod` | `go mod download` (respects the repo's `GOTOOLCHAIN` pin) |
| `Cargo.lock` | `cargo fetch` (`rustup run <pin>` when the repo pins a channel) |

- A monorepo installs from the root only, never per package.
- Run it bare and read the exit status; never pipe it through `tail`.
- `git status --short` afterwards must be empty. A lockfile that changed
  means the wrong installer or version — undo it, do not commit it.
- Gitignored inputs the gate needs (an `.env` for Playwright, a local
  certificate) are copied from the live checkout only when the gate names
  them; never copy them speculatively.
- An installer that fails is a blocker report before any edit, not
  something to work around inside the task.

### Refresh the fleet pack (when the repository vendors one)

A repository that vendors the decisions pack (`.adr/packs/decisions.pack`
in its `.adr.yaml`) resolves fleet rules from that copy, and nothing tells
it when a decision changes: on 2026-09-29 every consumer was weeks behind
and none knew the `work.*` rules. The refresh rides this branch
(`guidance.generated-block-rides-the-change`), never a fleet sweep:

```bash
aval add --check --quiet --budget 20; rc=$?
```

Branch on `rc` (zsh: `status` is read-only, never use it as a name):

- `1` (behind, or edited): `aval add <the pack's source>` (the source `.adr.yaml` names), read
  the diff, `aval heads --write` where the repository has its own corpus,
  and commit `chore(adr): refresh the fleet pack` — before the plan commit;
- `0` (current, or unknown because GitHub was unreachable): continue;
- `2` or `3`: one line to the person, never a blocker.

### Land the plan

The approved plan is the branch's FIRST commit, before any code.

1. **Which plan.** The path this session's ExitPlanMode result gave. If this
   session approved no plan, ask the person for the path. Never pick the
   newest file in `~/.claude/plans/` — with parallel sessions, mtime is not
   task identity.
2. **Reuse before writing.** If `docs/plans/` already holds an `active` plan
   for this work, continue it instead of adding a second one.
3. **Write it** as `docs/plans/<approval-date>-<slug>.md` (slug: the H1,
   kebab-case, ≤5 words), with front matter per
   [plan-template.md](plan-template.md): `status: active`, `plan-id` (copied
   word for word from the approved plan-mode file), `branch`, `repos`,
   `adrs`. When this repo is not the plan's home (the repo owning its
   decision), write a **pointer file** of the same name instead
   (`canonical:`, `phases:`, `status:` for this slice), and copy this
   repository's line from the canonical plan's `## Code review` section
   into the pointer's own `## Code review` section, verbatim.
4. **Check its review**, before writing it:
   - **No `## Review panel` heading** (an old plan, or one the person had
     skipped): land it as it is, with a
     one-line note in its Decision log.
   - **The section is there:** the last line must be the machine comment
     with a `body-sha`. If it is not, refuse; never treat the plan as
     unreviewed.
   - **Compare the sha:** run `greenbelay plan-sha --short <source>` on
     the approved source file in `~/.claude/plans/` (the file the hook
     judged). Never run it on the landed copy, whose front matter
     `plan-sha` does not strip. It must equal `body-sha`.
   - **On a mismatch** (the body changed after its review), do not land.
     Either re-run `/plan-review` as a delta and land once it passes, or
     the person accepts it unreviewed, recorded in one Decision-log line.
   - **Where the reviews go:** move `## Full reviews (reference)` into a
     sidecar, `docs/plans/<name>.reviews.md`. Link it from a
     `📄 Full reviews:` line inside `## Review panel`, which is outside
     the reviewed body.
   - **Check the landed copy:** `greenbelay plan-sha --short <landed>`
     must still equal `body-sha`: `plan-sha` skips front matter.
   - **A linked picture** (`.svg` or `.html` in its `## Picture`): copy
     each file from beside the approved source into `docs/plans/` under
     the same name, byte for byte, refusing if a different file of that
     name exists. Then, when `~/.claude/skills/plan-picture/check.py`
     exists, it must exit 0 on the landed plan.
5. **Commit it alone** (with its sidecar): `docs(plan): <slug>`.
6. **Boundary 1.** When implementation does not start in this turn, run
   [Handoff](#handoff) now: the landed plan is the whole handoff.

Skip all of this for a change describable in one sentence: it joins the
open batch branch with no plan.

**New screen or material UI choice, on a stack with a mockup contract** (`handoff.fresh-directions-trigger`):
before implementing, run the design extension's mockup skill, when one is installed, for 2–4 directions (its
checks must pass), let the person pick through options, and commit the
picked artboard on this branch. A fix that restores an existing design
reuses the picked artboard.

## Finish

Run from inside the worktree. The steps are labelled; every "return to"
below names one of them.

- **F1. Rebase.** `git fetch origin -q && git rebase origin/main`. Resolve
  conflicts in place, never in the live checkout.
- **F2. Verification loop**. Check
  the changed behaviour observably, against the plan's Verification section.
  When the repository has a `verify-*` skill, follow it for this check; when
  it has none and the check needs a running app, `create-verify-skill`
  writes one.
  - UI: launch the `browser-check` agent with `model: "haiku"` (failure: `agent-model-fallback`) on the local dev server (its start, login and seed
    from the `verify-*` skill's Launch and Drive, when there is one) with
    the route, viewport, theme, steps, questions and the short sha; it opens
    the changed route, exercises the interaction (click, type, mobile width),
    reads console and network, and files screenshots under
    `attestations/<sha>/`. Read only its report: the screenshots stay out of
    this session. Done when the report answers every question and every path
    it lists exists. Where a picked artboard exists (`handoff.prove-fidelity`),
    name in the brief the elements and properties to measure; compare the
    measured values to the artboard yourself, open one screenshot beside it
    for what numbers cannot show, and list every difference BEFORE the guide: fix each, or name it
    `deliberate: <reason>`. When accessibility seems to need a design
    change, look first for a fix that keeps the design (an `sr-only`
    copy, aria, a live region outside the control).
  - Non-UI: a piloted run — the CLI on a real input, the
    service plus requests, an operator on kind, `kustomize build` /
    `flux diff`. A focused test can be the check for a library, test-only
    or docs change; a green general suite alone never is.
  - Budget: one attempt plus at most 3 repairs of the same failure, then
    stop and report without pushing. Missing credentials or infrastructure
    is a blocker report, not a fix. Changes the person asks for do not
    count against the budget.
- **F3. Record.** In the plan: input → expected → actual per check, tick
  the phases, append Decision log / Outcome. Set `status: done` only if
  verification passed AND this PR implements the last phase. Record only
  what was observed before the push: never a "pending" row for CI, the
  merge or a release — those live in the PR checks and the tag
 . Offer to turn
  a lasting decision into an ADR in this same PR
 . Screenshots and raw output go
  OUTSIDE the worktree (`~/.claude/greenbelay/attestations/<sha>/`).
  They last 30 days unless a plan cites them as `attestations/<name>` or
  the directory holds a `.keep`; then they move to `.trash-<secs>-<name>`
  for 7 days (`greenbelay attestations` lists what stays and why).
- **F4. Commit.** Where amont is installed this commit IS the project gate
  (the gate runs the tests at pre-commit); only a repo without amont runs a
  separate `make check` or equivalent here. Run `git status` first and
  stage explicit paths.
- **F4b. Implementation review** (skipped
  when the branch carries no plan). One independent reviewer reads the
  diff against the plan and the active rules. The greenbelay
  `implementation-review` hook checks at the push that it happened for
  the tree being pushed, so run it after F4, on the committed tree:
  1. Post `📍 <project>: implementation review, round 1, about 2 min.`
  2. Build the brief with one command, in the worktree (the pack refreshed
     at Start), never by hand (a hand-built brief once carried
     rule statements only, and the reviewer passed a placeholder name):
     ```bash
     greenbelay review-brief --plan <landed plan> > <scratch>/brief.md
     ```
     It prints, in order:
     - the `<<<TREE repo=… sha=…>>>` block (the same as `tree-sha --block`:
       `HEAD` without `docs/plans/`) and a `<<<RULES sha=…>>>` line;
     - the `<<<CANDIDATES sha=… n=…>>>` block (adr-lint 0.3.0 or
       later): one line per candidate line the diff adds, ending
       `<<<END CANDIDATES>>>`, or `<<<CANDIDATES unavailable>>>` when adr-lint
       could not run;
     - the plan's Verification section;
     - the diff stat, and the full diff under 60 KB;
     - the code rules in full;
     - the constraint index;
     - the decisions that apply to the changed paths, each resolved;
     - a `## Candidates` section with each candidate's pattern and line;
     - the plan's Non-goals;
     - in the plan section, the plan's `## Code review` line for this
       repository (`Declared code review for <repo>: …`).

     For a pointer plan, pass the canonical plan's path. The merge-base is
     the remote's default branch; pass `--base <ref>` for a stacked branch.
     Exit 1 means the repository or its base could not be read: pass
     `--base <ref>` (a stacked or local-only branch). Exit 3 means aval
     failed and nothing was printed; fix aval, never hand-build the brief
     instead. A repository with no `.adr.yaml` has no decided code rules:
     the brief says so and carries no RULES line.
  2b. **Interface review** (advisory; skipped unless the diff touches the
     repository's UI). Trigger: the `ui` areas from `aval traits`, matched
     against `git diff --name-only <base>..HEAD`; no match, no step. Build
     one brief for the `interface-review` agent: the base sha, the scope
     block, the `aval traits` output, the `aval resolve` output for the ui
     and design-system keys (it answers at the repository's declared
     `in_scopes`; no hand-typed `--scope`), with the
     exemption list of `design-system.every-measure-is-a-token`, the full
     diff (no 60 KB cut)
     and the removed lines of `git diff -U0 <base>..HEAD`. Launch it in
     the same message as step 3's `implementation-review` launch, so the
     two run in parallel. Findings are advisory:
     each is fixed or recorded `deliberate: <reason>` under a separate
     `## Interface review` section of the plan. There is no hook gate, no
     Overrule question and no Delta round of its own. Interface fixes land
     before the closing commit; a fix that changes code returns to F1, and
     the implementation-review pass on the new tree is its Delta. When the
     plan's `## Code review` declares `ui-design`, interface-review is that
     profile instead (step 2c), gated, and this advisory launch is skipped.
  2c. **Code-review profiles** (skipped when the plan has no
     `## Code review` section, or its line for this repository is
     `none — …`). For each profile the line declares, build its brief:
     ```bash
     greenbelay review-brief --profile <role> --plan <landed plan> > <scratch>/brief-<role>.md
     ```
     It carries the TREE and RULES lines, `Profile: <role>` and the judge
     rules that profile reviews, and no candidates: candidates are
     implementation-review's alone. The agent is `code-review-<role>`; for
     `lang:<x>` it is `code-review-language`, for `ui-design` it is
     `interface-review` with step 2b's inputs added to its brief. Each
     prompt carries, in order: the TREE line verbatim; `Round 1.`; the
     RULES line verbatim; `Profile: <role>` (exactly one, matching the
     agent: the hook counts nothing else); the brief's path with "read it
     in full" (the brief is long, and a path keeps the prompt small; the
     hook reads the `Profile:` line and the TREE block only from the
     prompt's header, the lines before any heading, fence or diff, so they
     must come before any pasted text); "Read the plan and the diff. Open at most 10 more
     files or 1,500 lines. Follow your output contract." The push hook
     refuses a push that misses a declared profile, naming the agent to
     launch.
     Every review launch in steps 2b, 2c and 3 carries `model: "opus"`. When
     one fails because that model is unavailable, follow `agent-model-fallback`:
     relaunch the same agent once with no `model`, with the same prompt, TREE
     line and `Profile:` line. Record `opus → root` on its line in step 5.
  3. Launch the `implementation-review` agent once, in the foreground,
     with, in order: the TREE line verbatim; `Round 1.`; the RULES line
     verbatim (the push check journals a review whose prompt lacks it, or
     carries a stale one); the CANDIDATES block verbatim, from its first
     line to `<<<END CANDIDATES>>>` (the push check reads the ids from the
     prompt, not from a file); the brief, inline or as its path with "read
     it in full" (an inline brief repeats these lines at its top; leave
     them); when the block lists any id, "Your result must carry a
     `Candidates:` block ruling on every listed id";
     "Read the plan and the diff. Open at most 10 more files or 1,500
     lines. Follow your output contract." A background launch counts only
     after its completion notification. Launch it in ONE message with every
     step 2c profile, so they all run in parallel.
  4. Post `returned: <verdict> (<tokens>, <seconds>)`, one line per
     reviewer as each returns (`k/N returned: <role> <verdict> …`).
  5. Record it in the plan under `## Implementation review`, one line per
     reviewer and at most 5 lines in all, about 20 words each, verdict
     first: the verdict; findings fixed;
     findings kept as `deliberate: <reason>`; tokens and seconds. This is
     the branch's **closing commit**,
     the counterpart of the plan commit that opened it: in the same commit
     set `status: done` (or keep `active` and name the next phase), with
     every Verification row holding its observed result and none pending.
     Commit `docs(plan): <slug>, done` (or `…, phase N`). The canonical
     tree does not change, so the review stays bound. It stays the LAST
     commit: anything committed after it (a CI fix) returns to F1, and the
     closing commit is made again on top.
  6. `approve`, or `approve-with-changes` with every finding fixed or
     named deliberate: continue to F5. A fix that changes code returns to
     F1, and the **second** pass through F4b is the `Delta`: a fresh block
     for the new tree, `Delta.`, the RULES line (absent in a repository
     with no `.adr.yaml`) and the CANDIDATES block from a fresh
     `review-brief`, the round-1 findings, the diff since,
     "answer resolved / not resolved / new blocker for each". The Delta may
     resume the same reviewer with `SendMessage` (the block first in the
     message) instead of a fresh launch: the hook counts a resumed round on
     its new tree. Prefer a **fresh, small** launch
     per seat with `greenbelay review-brief --interdiff <head>
     [--profile <role>]` (the stale line names
     `<head>`): the headers plus only what changed, instead of resuming a
     50-80k-token context. Never assert in prose that something is
     unchanged; the interdiff shows it. When it refuses (rules changed,
     60 KB or more), build the full brief. Among the step 2c profiles, one
     that said `rework` or `approve-with-changes` re-runs as a Delta too;
     one that said `approve` keeps its pass when the hook can carry it: the
     same landed plan and `## Code review` line, its reviewed commit an
     ancestor of the pushed one after the merge-base, and
     implementation-review passed the new tree. A rebase carries nothing by
     ancestry, so its profiles re-run unless the branch patch is unchanged
     or only the root `CHANGELOG.md`'s context moved (journalled
     `reviewed-by-patch-notes-moved`): then no delta is due.
     A resumed profile round may omit its `Profile:` line; it keeps its
     launch's. There is no
     third pass: a `rework` that survives the Delta goes to the person with
     a **marked** AskUserQuestion — its text starts with
     `[implementation-review <repo>@<sha64>]` (the full id from
     `tree-sha`), or `[implementation-review <repo>@<sha64> profile=<role>]`
     for a profile's rework, its options are exactly `Overrule`, `Fix`, `Hold`, with
     both positions stated and `answers` never pre-filled. `Overrule` is
     recorded by the hook itself and in the plan as `deliberate:
     overruled — <reason>`; `Fix` returns to F1 and the next F4b is a
     fresh round 1; `Hold` stops without pushing.
  - Never write under `~/.claude/greenbelay/implementation-review/`: the
    hook alone writes a pass file, and refuses a Write, Edit or Bash there.
- **F5.** If the SHA to push differs from the verified tree in more than
  the plan commit, return to F2.
- **F6. Non-UI push.** First, in the same turn, `git rev-parse --abbrev-ref @{u}`:
  it must fail (no upstream) or name `origin/<branch>`. Any other answer
  (`origin/main`, `origin/dev`) would make the land a push to the default
  branch: run `git branch --unset-upstream` first. Then land the branch: `amont land --json`, alone in its
  command (or after one `cd <worktree> &&`), in the foreground. From amont
  2.0 it runs every push gate the push owes before git connects, then
  pushes; below 2.0, run `amont rehearse --wait` first. Exit 0 is the proof:
  the remote branch is the sha it pushed. Exit 4 means the remote accepted
  the push but shows another sha: read `remote_after` before anything else.
  1 is refused (a gate failed before the push, or the push was refused;
  nothing was pushed). 3 is unreachable (nothing pushed) or unverified (the push
  was accepted but could not be read back): run the `git ls-remote` that
  land prints before landing again. The push guards judge a land as they
  judge a `git push`, but only in that shape; any other shape is held
  under deny. Where amont or greenbelay is missing, or `amont --version`
  is below 1.54 (the guards would not
  see the land), push as before: `git push -u origin <branch>` bare,
  confirmed with `git ls-remote origin refs/heads/<branch>`; with amont 2.0
  or later there, run `amont rehearse --wait` first, as its own command, or
  that bare push is refused (`push refused: … have not run on`). Then open ONE
  pull request whose body carries the verification record.
- **F7. UI push** (the push carries interface changes in a repository with a
  user interface). The person works
  on several projects at once and will not remember where this one stood.
  **Never ask for an approval without a guide.**
  0. **Planned evidence**.
     If the plan approved through ExitPlanMode has, in its body, a
     `## Preview` section whose first non-empty line starts with
     `evidence:`, do steps 1–3 (server, screenshots, guide; not 3b),
     compare every existing screen against the base, and put the
     guide, screenshots and comparison in the PR body. Ask nothing, then push
     as in F6: the hook passes the push and journals `evidence`. If the
     comparison shows a visible change the plan did not decide, the
     exemption lapses: run steps 1–7 as usual. The hook still holds the push,
     so ask as usual, when the section was added after the plan's first
     commit, the branch carries only a pointer plan (`canonical:`), the plan
     landed on main before the branch, the base ref is missing, or the push
     touches screens drawn from a picked mockup.
  1. Dependencies are already there from the Start bootstrap; re-run that
     step only if the rebase in F1 changed the lockfile. Start the dev
     server on a free port and keep it up until the person answers.
  2. **Screenshots.** Take `before.jpg` from `origin/main`'s build or from a
     step taken earlier, and `after.jpg` from this commit, at the same route
     and state. Put them in `~/.claude/greenbelay/attestations/<short-sha>/`,
     outside the worktree.
  3. **Write the guide** in that directory as `guide.md`, from
     [preview-guide-template.md](preview-guide-template.md). Fill every
     section:
     - Where we are;
     - What you should see;
     - Try it: numbered steps, the exact URL, each click named by its visible
       label and position, and after each step what should appear;
     - Reference;
     - Already checked.
     Write it for someone who has not seen this session.
  3b. **Cold load before register.** The person's browser has none of the
     agent's logins, and the page they get must show the change without
     them: a guide once said "signed in" for a state only the agent's own
     browser had, and the person approved a page they could not see. Skip
     3b on the step 0 evidence path, and when `cmp before.jpg after.jpg`
     says the pair is byte-identical: the `unchanged` path asks nothing and
     stays as it is. A fallback to steps 5–7 (the hook journals
     `unchanged-skipped`, or holds a step 0 push) runs 3b first.
     Launch `browser-check` (`model: "haiku"`; failure:
     `agent-model-fallback`) on the exact URL step 5 will open. The caller's
     brief to it says to open the page with `new_page` and an
     `isolatedContext` of a fresh name, never in the default context: that
     one keeps an earlier agent's login across runs (measured: a cold load
     after another agent's sign-in showed the signed-in page). It reports,
     as measured facts, the script-visible cookies and storage it holds for
     the origin after the load, the final URL, whether a sign-in form or
     login route is showing, and whether the text or element "What you
     should see" names is on the page. HttpOnly cookies are not
     script-visible: the isolated context, not this report, is what makes
     the load cold.
     - **A wall is the agent's to fix, outside the commit.** Change only the
       running preview: seed a throwaway account in the dev data, start the
       server with the repository's existing dev-login switch, or pick a
       route that renders the change signed-out. With a throwaway account the
       cold load signs in with exactly the credentials "Try it" step 1
       gives. Never a code change (it returns to F1, and a committed
       auto-login ships an auth bypass), and never a session token in the
       URL, the guide or the PR body. Two rounds at most.
     - **Still a wall after two rounds, or a fix that needs code:** ask the
       person one unmarked question: the preview needs a login the agent
       cannot provide, with what the cold load showed. Options: `I'll sign in
       or give a login`, `Skip the page, review the PR evidence`, `Hold`. It
       carries no `[preview` marker and names no localhost URL
       (`ask-unopened-page` would otherwise require a fresh open before step
       6). It comes before step 4, so no registration is pending; on a fallback
       the answer lapses the earlier one. Then, by answer:
       - `I'll sign in or give a login`: put that sign-in in "Try it" step 1
         and run 3b again with it (a round past the two). If it passes,
         steps 4–6, registering again. If the wall stays (a login typed into
         their own browser is invisible to the isolated context, and a given
         login can be wrong), ask once more with only `Skip the page, review
         the PR evidence` and `Hold`, and follow that answer's branch;
       - `Skip the page, review the PR evidence`: skip step 5, register
         (step 4), and word the marked question to name no URL and point to
         the PR evidence;
       - `Hold` stops.
     - "Try it" step 1 of the guide says what sign-in the page needs and how
       it was provided; it never says "signed in" for a state only the
       agent's browser had.
  4. **Register it** in the foreground, as the last command of its Bash call
     (anything joined by `&&` or `;` may come before it; never pipe it,
     redirect it or put it in `$(…)`):
     `greenbelay preview register --url <url> --guide <that guide.md> --open`
     It refuses an incomplete guide. `--open` opens the rendered guide page
     in the person's browser.
     Its JSON prints `question_prefix` (`[preview <id>] <label>`): the
     question in step 6 starts with it, verbatim. A register that did not
     bind says so right after it runs; run the command it prints.
     When it prints `"unchanged": true`, the guide's one before/after pair
     is byte-identical, and the hook approves the preview when it binds
     it, if the files still match. Skip steps 5 and 6, put the guide and
     both screenshots in the PR body, and push as in F6; say so in one
     line. If the push is still held, or the hook journals
     `unchanged-skipped`, run 3b, then steps 5 to 7. This holds only for
     the real pair of step 2: `before` from the base build (not an earlier
     step's shot), `after` from this commit, at the same route and state.
     Never copy one shot onto the other; every `unchanged` approval is
     journalled and audited.
  5. **Open the app for them in their own browser**: `greenbelay open
     '<url>'`, alone in its command (the machine's opener,
     `greenbelay.opener`), with the URL
     deep-linked to the state step 1 of "Try it" reaches where a route or
     query can carry it. When the question in step 6 names this URL, the
     `ask-unopened-page` hook refuses it until this open ran. Never open the
     person's page with chrome-devtools MCP, Playwright or any headless or
     automation Chrome: that window is the agent's, it lives in a separate
     profile and the person does not see it, or sees it as a stray window.
     Those tools are for the agent's own checks only. When the state needs
     clicks a URL cannot carry, open the URL and let step 1 of "Try it" say
     the click. Say what was opened.
  6. **Print the brief in the terminal**: the guide's sections, short. Then,
     in the SAME turn, ask ONE marked question with AskUserQuestion, only
     when 3b passed, was skipped by its own rule, or the person chose `Skip
     the page`:
     - its text begins with the register's `question_prefix`, verbatim,
       then the project and the one-line change (the id in the marker is
       what binds; it starts with the commit's short sha);
     - options exactly `Approve`, `Request changes`, `Hold`, with no
       "(Recommended)" suffix;
     - never pre-fill `answers`.
  7. On `Approve` (or the person typing `approve`/`ship`/`lgtm`/`looks
     good` as the next prompt), push as in F6. On `Request changes`, apply
     what the person describes, then return to F1. On no answer, wait with
     the server up.
  - An approval given before the person had a guide is not informed. Hold
    the push, give the guide, and ask again.
- **F8.** Any code change or rebase after F4 returns to F1.
- **F9. Merge on green**. Do not stop at an open pull
  request, and do not ask: run the `merge-when-green` skill on every
  implementation PR this finish opened. It merges once every check on the
  head has completed with success, and only when all of these hold:
  - the F4b review is `approve`, or `approve-with-changes` with every
    finding fixed or named deliberate;
  - any `merge-after: <repo>#<n>` in the PR body has merged, with its
    release out when it names one;
  - the person has not said to hold it.

  A red check is a failure under the F2 budget. Read the log, fix it in this
  worktree, and return to F1; the next F4b is a fresh round 1 on the new
  tree. Keep the worktree until the merge, for exactly this.

  A PR that must wait for a release, or for another PR, stays open with its
  `merge-after:` line, and the report says what it waits for. Never cut the
  release yourself.
- **F10. Teardown: required, and the finish is not done without it.** Run it
  after the merge in F9, or once the push succeeds (`amont land` exit 0,
  or `git ls-remote` after a `git push`) for a PR that F9 left open. It is never "cleanup for
  later": skipping it has left merged worktrees behind.
  1. Remove this worktree from the **primary** checkout (not from inside
     itself), using `git -C` so no `cd` persists:
     ```bash
     git -C <repo-root> worktree remove ../<repo>-wt-<slug>
     ```
     If it refuses because of untracked files, inspect them first. Don't
     `--force` blindly: it may be legitimate leftover build output, but check.
  2. Sweep the other worktrees in this repo. A merged PR elsewhere does not
     clean itself up. Run it from the primary checkout: after step 1 the
     shell's cwd can be the worktree just removed.
     ```bash
     cd <repo-root> && python3 ~/.claude/skills/worktree-sweep/sweep.py --repo <repo> --apply
     ```
     It removes only worktrees that are clean, fully pushed, merged and
     contained in a release tag, and leaves anything it cannot verify. It
     also stops the language servers (rust-analyzer, gopls, pyright, the
     TypeScript server) of every checkout that no longer exists, the one
     removed in step 1 included. See the `worktree-sweep` skill.
  3. In the report, say what was removed and what the sweep kept, one line
     each.
  4. End the report with the plan's `### 🧑 Your steps` block, as its last
     lines before the handoff line of step 5, under `Your steps (the agent cannot run these):`, one numbered
     line per step in the form ``N. `command` — because <why>``.
     - **Which plan.** For a pointer plan (`canonical:`), read the block from
       the plan `canonical:` names: a pointer never holds it.
     - **When.** Read it before step 1 removes the worktree, or later with
       `git show <branch>:<plan path>`; a PR F9 left open has the plan only
       on its branch.
     - **What counts**, as `plan-panel` counts it: each top-level `- ` line
       of the block is a step, a `- [ ]` line included; a `* ` bullet and an
       indented line are not. Skip fenced lines. The block stops at the next
       heading, or at a `Phase N` or 🧑 decision item. The number of lines
       you print equals `plan-panel`'s `steps:N` for that plan.
     - With no block, or an empty one, the block is the single line
       `Your steps: none.`, before the handoff line.
       When the plan cannot be read (a missing file, or a `git show` that
       fails), print `Your steps: unknown (plan not readable at <path>)`,
       never `none`.
  5. **Boundary 2.** Run [Handoff](#handoff). Its line comes after the
     Your steps block and ends the report.

- One implementation pull request per repo per plan; F9 merges it with the `merge-when-green` skill. That skill's step 6 fast-forwards the live checkout after the merge, so this finish does not touch it: before the merge there is nothing new on `origin/main` to bring in.
- A release (`tag-release`) ends with the same sweep, because a worktree becomes sweepable only once its PR is in a release tag.

No release unless the person asks for one.

## Handoff

A session ends at a boundary with its state in the repository, so that a
`/clear` loses nothing. Run this without being asked: the person does not
type "write the handoff".

### Follow-ups go to the inbox, at any time

When you notice work that is not this task, append one line, under 512
bytes, with a single `>>`. The inbox is one per repository, shared by its
worktrees, and never committed:

```bash
d=$(git rev-parse --path-format=absolute --git-common-dir) &&
  inbox="$d/greenharness/inbox.md" &&
  s8=$(printf %s "${CLAUDE_CODE_SESSION_ID:-nosession}" | cut -c1-8) &&
  mkdir -p "${inbox%/*}" &&
  printf '%s %s %s\n' "$(date +%F)" "$s8" '<text>' >> "$inbox"
```

- `<text>` may start with `due=YYYY-MM-DD`, and names the repository when
  the follow-up is about another one. It is single-quoted: write a `'` in
  it as `'\''`.
- Shell variables do not survive between tool calls: recompute `inbox`
  and `s8` with the first three lines in every command that uses them.
- Without a session id the line carries `nosessio`. Such a line is never
  filed as anyone's own, only as an orphan.

### When

At each of these boundaries:

1. the plan has landed and implementation does not start in this turn
   (Land the plan, step 6);
2. the PR has merged and the worktree is torn down (F10 step 5);
3. a programme ticket is closed and its PR merged;
4. a release is verified and swept (`tag-release`).

Only when nothing of **this session** is in flight. Other sessions'
worktrees and runs do not count. All of these hold:

- its worktrees have no uncommitted or unpushed work (at boundary 1, the
  plan commit may be unpushed);
- none of its background tasks, polls or relais runs is still running or
  waiting on a decision;
- no question to the person is unanswered;
- no worktree it made is left to tear down (boundary 1's own excepted);
- no PR of its own is open. A PR that F9 left waiting on a `merge-after:`
  is in flight: write the handoff, naming what it waits for, but print no
  line.

If anything is in flight, say what it is and print no handoff line.

### Steps

1. **File the inbox** of every repository this session touched. Skip a
   repository with no `inbox.md` and no leftover `.filing` file.
   - First take the inbox atomically, when `inbox.md` exists, in the same
     command as the three lines that set `inbox` and `s8`:
     ```bash
     take="${inbox%.md}.$s8.$$.filing" && mv "$inbox" "$take" &&
       touch "$take" && printf '%s\n' "$take"
     ```
     The name is this shell's own, so it never overwrites another take, and
     appenders start a new file, so no two sessions file the same line.
     `touch` dates the take when it is made (`mv` keeps the last append's
     time), which the age test below relies on. `$$` changes with every
     tool call: use the printed path, as written, in every later command.
   - Read the taken file. Also read the takes a dead session left behind:
     `find "${inbox%/*}" -name 'inbox.*.filing' -mtime +0` lists those
     taken more than a day ago. A younger one is another session still
     filing, so leave it.
   - File the lines that carry this session's id, and every line dated two
     or more days before today (an orphan: its session is gone).
   - Each filed line becomes a `task` ticket, `mode = "afk"`, with
     `## Look at` and `## Answer looks like`, and `due` from `due=`. It
     goes in the plan's programme map, or else in this repository's
     `docs/programmes/follow-ups/` (write its `map.md` on first use).
   - Append each line not filed back to `inbox.md`, one `>>` each, then
     delete your own take and the leftovers you read, nothing else.
     `relais programme check <dir>`, when relais is
     installed, exits 0.
2. **Write the handoff** into the repository, never into memory or a file
   outside it.
   - **In a programme:** replace the map's `## Handoff` section (between
     Decisions so far and Not yet specified; never a second one). It holds
     the date and the boundary; what is done and what merged; the live
     state; what is next, in order, by ticket name; accepted gaps and
     lessons; and the plan's Your steps when it has any, so a clear does
     not lose them.
   - **Without a programme:** the plan is the handoff. Check that its next
     open phase, or its Outcome, states the next action.
3. **Land it** with the change it describes: in the ticket's closing
   commit, or the plan's last commit, before that PR merges. Only what the
   merge itself reveals goes in one docs PR afterwards, merged with the
   `merge-when-green` skill; the line waits for that merge.
4. **End the answer with the line**, as its last line, with nothing after
   it:

   ```
   safe to /clear; next: `<prompt>`
   ```

   - The prompt is one line, not empty, at most 2,000 characters, with no
     backtick in it.
   - It is what a fresh session needs to resume: for example
     `implement docs/plans/<file> in <repo>`.
   - **In a programme it names one ticket that no other session holds.**
     Run
     `relais programme next --from <repo>:<programme> --claim`. It chooses
     the first unheld ready ticket of this programme, else one of a
     programme no session is on, and reserves it for the next session.
     - Exit 0: its stdout is `<repo> <programme> <ticket>` then a tab and the
       ticket's name. The prompt is
       `resume <repo> <programme> <ticket>: <gist>`, and nothing open-ended.
     - Exit 22: nothing is left for an agent. `next` printed one `parked: …`
       line on stdout (`parked: next due <date>` or `parked: nothing due`).
       End with `safe to /clear; ` followed by that line, for example
       `safe to /clear; parked: next due 2026-11-24`, instead of a `next:`
       line. The relay submits nothing on it.
     - Any other exit: say relais's stderr line, print no clear line, and
       never fall back to an open-ended prompt.
     - Without relais: name the map's own next ticket, or park. Never name
       another programme from memory.
   - When the next step is the person's, park: the map's Handoff already
     carries the person's steps.
   - A clear-relay plugin, when installed, clears and submits the prompt
     after a countdown the person can stop. Without it, the person types
     `/clear` and pastes the prompt.

## Cleanup (abandon)

```bash
cd <repo-root>
git status --short              # sanity check what's about to be discarded, from the worktree path
git worktree remove --force ../<repo>-wt-<slug>
git branch -D <branch-name>     # only if the branch was never pushed / isn't needed
python3 ~/.claude/skills/worktree-sweep/sweep.py --lsp --apply   # stop its language servers
```

Confirm with the user before this mode if the worktree has any uncommitted work — this is the one destructive path in this skill.

## Never

Move work between a worktree and another checkout with a WIP commit, not `git stash` — `refs/stash` is shared across all worktrees of a repo. If a stash is genuinely needed, follow the "Git stash policy (worktrees)" section of `~/.claude/CLAUDE.md`: `git stash push -u -m <tag>`, then apply that entry by its sha.

Don't restore a mutated file with `git checkout -- <file>` while the tree holds uncommitted work: it reverts to the last commit and takes every unstaged edit with it. Copy the file aside and copy it back.
