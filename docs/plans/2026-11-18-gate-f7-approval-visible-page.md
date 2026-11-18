---
status: active
branch: feat/f7-cold-load-check
repos: [skills]
adrs: []
plan-id: p-01M7R4MM3AFYMEGZASG6K6NM9A
---
# Gate F7 approval on a visible page (worktree-task)

## Review panel

none — approve if the agent can make a preview reachable without a code change; when it cannot, it asks you once.
📍 skills · 1 phase · 1 PR · next: Phase 1 in a task worktree. Panel: backend (opus).
**Changed by review:** the cold load runs before register, fixes touch only the running preview, and refactors with an unchanged pair skip it.
**Verdicts:** 2 approve, 2 approve-with-changes (all high applied); 5 carried; words 1083 → 1359 (×1.26, the last high edit fixed a contradiction); remove 2, merge 0.
📄 Full reviews: [2026-11-18-gate-f7-approval-visible-page.reviews.md](2026-11-18-gate-f7-approval-visible-page.reviews.md)

## Picture

```
 today (F7)                    after this plan
 ----------                    ---------------
 open page                     cold-load check, no login
    |                             |-- wall --> fix running preview
    v                             |            (no commit), load again
 approval question                |<-----------'
    |                             |-- still wall --> ask the person
    v                             v shows the change
 push                          register, open page
                                  |
                                  v
                               approval question
                                  |
                                  v
                               push
```

A cold load of the page with no login runs before any question, so the agent fixes a wall and the person is asked only when there is something to review.

## Context

A happier session asked the person to approve changes from a page that opened logged out. The person could not see the changes and approved anyway. The F7 skill in `~/.claude/skills/worktree-task/SKILL.md` (steps 5–6, lines ~432–457) opens the page and asks in the same turn. Nothing checks that the page shows the change. "A guide exists" is the only precondition, and a guide can be correct while the person's page is a login screen.

The person wants no human step unless there is something to review, and the agent to check with Playwright, Chrome DevTools or Claude in Chrome. The `browser-check` browser is headless and isolated, with none of the person's logins: that is the state of a logged-out page, so a cold load of the exact URL shows what a logged-out person would see. What to avoid is trusting the agent's own signed-in profile, which is how the transcript's guide came to say "signed in".

## Transcript evidence

Likely session: `a6a522f6-abd7-4c96-9c5b-7ebb3816d4ec.jsonl` (happier M1 finish, worktree `happier-wt-m1-finish`). Inferred, not verified: no transcript shows the person saying the page was logged out at approval time.

- **2026-10-19 07:01 (person):** "I open http://localhost:4317/ see 'Authentication failed'… you shouldn't need me here, use claude in chrome". The person's own browser was signed out of the preview server.
- **07:04–07:07 (agent):** started a light server on port 3017 with a throwaway secret, rebuilt the preview, and signed in only in the agent's own chrome-devtools profile.
- **07:08:27:** the guide's step 1 said "you land on the Inbox, signed in to a throwaway account". Registered as preview `fd6a176ad5c1ea`, with `--open`.
- **07:08:39:** the marked question asked Approve / Request changes / Hold.
- **07:13:23 (person):** "Approve", about five minutes later. No visibility check happened between the open and the approval.
- **07:21:15:** re-registered for a rebased commit, approved again. Pushed to `dev`.

Root cause as the transcript shows it: the guide described a signed-in state that exists only in the agent's profile, and the approval step never confirmed the person could reach it. The "signed in" claim was the agent's, written as the person's experience.

## Approach

1. **Cold-load check before register (new, F7 step 3b, after the guide, before steps 4 and 5; skipped on the step 0 evidence path and when `before.jpg` and `after.jpg` are byte-identical, so the `unchanged` path stays as today).** Run `browser-check` on the exact URL step 5 will open, in a fresh browser context with no cookies or login. Its brief first asks it to report the cookies and storage it holds for the origin; a non-empty store fails the check as not cold (its chrome-devtools profile may keep an earlier agent login). It reports measured facts: the final URL, whether a sign-in form or login route is showing, and whether the text or element the guide's "What you should see" names is on the page.
2. **A wall is the agent's to fix, outside the commit.** Allowed: changes to the running preview only (seed a throwaway account in the dev data, start the server with the repository's existing dev-login switch, or pick a route that renders the change signed-out). With a throwaway account, the cold load signs in with exactly the credentials the guide's "Try it" step 1 gives. Never: a code change, or a session token in the URL, guide or PR body. A fix that needs code goes straight to Approach 4. Two rounds at most, then register (step 4) and open (step 5) once.
3. **The marked question is asked only when there is something to look at and the cold load passed.** Options stay exactly `Approve`, `Request changes`, `Hold`, as the register and the hook require. The `unchanged` path and the planned-evidence path ask nothing today and are left alone.
4. **When the cold load still fails after two rounds,** the agent asks the person one unmarked question: the preview needs a login it cannot provide, with what the cold load showed. Options: `I'll sign in or give a login`, `Skip the page, review the PR evidence`, `Hold`. The question carries no `[preview` marker and names no localhost URL (`ask-unopened-page` would otherwise require a fresh open before step 6). It is asked before step 4, so no registration is pending; after the answer the agent registers (step 4) and opens (step 5), then asks the marked question.
5. **The guide stops claiming a state only the agent had.** "Try it" step 1 states what sign-in the page needs and how it was provided, and never says "signed in" for a state that exists only in the agent's own browser profile.

## Non-goals

- Not changing `greenbelay`'s preview hook or `browser-check`'s brief.
- Not reviewing or changing the happier repository or its approval flow.
- Not reworking the guide template beyond the sign-in line.

## Source of truth (correction)

The skills live in the `greenharness/skills` repository (https://github.com/greenharness/skills), cloned at `~/Developer/Perso/skills` (done 2026-11-18, `main` at f20ae79). `~/.claude/skills/` is the installed copy; the two worktree-task files were byte-identical to the repo's at clone time, so the line numbers in this plan hold. Edits go into the repo through a branch in a task worktree and one pull request, never into `~/.claude/skills/` directly.

## Phases

1. Edit `parts/workflow/skills/worktree-task/SKILL.md` (F7: a new step 3b for the cold-load check and the fix-or-ask rule, and step 6 asking the marked question only when the cold load passed) and `parts/workflow/skills/worktree-task/preview-guide-template.md` ("Try it" step 1), in a worktree of the skills repo, with this plan landed as the first commit under `docs/plans/`. One PR, merged on green.

## Code review

- skills: none — markdown only

## Critical files

- `parts/workflow/skills/worktree-task/SKILL.md` — F7 new step 3b and step 6 (edit).
- `parts/workflow/skills/worktree-task/preview-guide-template.md` — add an optional "Sign in first" line in "Try it" step 1 (edit).
- `~/.claude/agents/browser-check.md` — no change in this plan; its brief stays headless, which is what the cold load needs: no cookies, no login.
- `greenbelay` 6.5.0 `preview register` — no change; out of scope.

## Verification

- In the skills repo, run `python3 -m unittest discover -s tests`. `tests/test_agent_model_fallback.py` requires `worktree-task/SKILL.md` to keep `model: "opus"` and the `agent-model-fallback` citation, so the edit must leave both in place.
- Read the edited F7 section end to end; confirm the marked question text and option list are unchanged.
- Dry-run in a throwaway worktree against a login-gated page. Expected: the cold load reports a wall before any register; the agent fixes the running preview with no commit; the second cold load passes; one register and one open follow; the marked question passes `ask-unopened-page` and binds.
- Cannot-fix path. Expected: after two rounds the unmarked question asks the person; no registration exists when it is asked; after the answer, one register and one open come before the marked question.
- A refactor whose before and after pair is unchanged. Expected: no question to the person and no new step, as today.

## Decisions (2026-11-18)

1. **Where the check lives:** in the F7 skill, run by the agent as a cold load. The person asked to automate as much as possible and be asked only when there is something to review; Playwright, Chrome DevTools or Claude in Chrome are acceptable for the agent's own checks. The person's own signed-in browser (Claude in Chrome) is not used for this check, because it would see the login and hide the wall.
2. **Scope:** steps 0 and 4 stay ungated; neither asks for an approval.
3. **Guide wording:** yes, state the sign-in need; never write "signed in" for a state only the agent's browser has.

<!-- panel: repos=skills reviewers=backend body-sha=41f39d3801a9 -->
