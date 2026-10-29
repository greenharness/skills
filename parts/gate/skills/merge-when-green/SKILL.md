---
name: merge-when-green
description: Poll a PR's checks until they pass, then merge it. Use for EVERY PR merge: whenever asked to "merge", "merge when green" or "merge once CI passes", AND without being asked, for every implementation PR an agent opened (worktree-task F9) — never gh pr merge --auto, never a hand-written poll loop or curl to /merge.
---

# merge-when-green

Standing rule: **never use `gh pr merge --auto`** on a repository without branch protection that requires status checks. There `--auto` merges the PR *immediately*, before CI has even started, instead of waiting for checks as it would on a protected repo, so it merges on red or unfinished checks.

## Args

`args` = the PR number, or a branch/repo hint to find it. If omitted, resolve the PR for the current branch: `gh pr view --json number,url -q .number`.

## Steps

1. **Identify the PR.**
   ```bash
   gh pr view <n> --repo <owner>/<repo> --json number,url,headRefName
   ```

2. **Poll checks to completion — as a loop you can watch, not a single blind wait.** `gh run watch --exit-status` is unreliable (it has returned exit 0 for runs that actually concluded `failure` — see `~/.claude/CLAUDE.md` § Before pushing). Poll the PR's checks directly instead:
   ```bash
   gh pr checks <n> --repo <owner>/<repo>
   ```
   or, for a specific run:
   ```bash
   gh run view <run-id> --json status,conclusion --jq '{status,conclusion}'
   ```
   Loop until `status` is `completed` for all required checks. Use `until`/`sleep` in a single foreground command, or check back periodically — don't spin tightly.

2b. **Check the plan, warn only.** If the PR adds or changes a file under
   `docs/plans/`, read its front matter from the PR head: a plan still
   `active` whose phases are all ticked, or `done` with phases unticked, is
   worth one line to the person before merging. Never add a commit for it
   here — a commit re-runs CI; the status belongs in the branch's last
   commit (worktree-task F3).

3. **Read the result BEFORE deciding to merge — as its own step, not chained into the merge command.** Never write something like `cat <poll-result>; gh pr merge ...` in one compound command — a background poller's stale/wrong output has previously caused a merge to fire on red checks because the merge ran unconditionally regardless of what the `cat` printed. Inspect the actual conclusion first, THEN issue the merge as a separate tool call.

4. **If all required checks are `conclusion: success`:**
   ```bash
   gh pr merge <n> --repo <owner>/<repo> --squash
   ```
   (Squash is this user's default merge strategy unless told otherwise.)

5. **If any check failed or is still running when asked to report status:** don't merge. Report which check(s) are red/pending and stop — let the user decide whether to wait, fix, or override.

6. **After a merge, bring the live checkout up to date, but only by fast-forward.** This applies on GitHub and Forgejo alike. The live checkout is the repo's primary checkout (the first line of `git worktree list`), not a task worktree. The person works there, so touch it only when it is safe, and never with anything but a fast-forward. Run it as its own command:
   ```bash
   LIVE=$(git -C <any-worktree-of-the-repo> worktree list --porcelain | awk '/^worktree /{print $2; exit}')
   git -C "$LIVE" fetch origin -q
   DEF=$(git -C "$LIVE" symbolic-ref --short refs/remotes/origin/HEAD | sed 's#^origin/##')
   GD=$(git -C "$LIVE" rev-parse --absolute-git-dir)
   if [ "$(git -C "$LIVE" branch --show-current)" != "$DEF" ]; then echo "live: on $(git -C "$LIVE" branch --show-current), not $DEF; left alone"
   elif [ -n "$(git -C "$LIVE" status --porcelain --untracked-files=no)" ]; then echo "live: uncommitted changes; left alone"
   elif [ -e "$GD/MERGE_HEAD" ] || [ -d "$GD/rebase-merge" ] || [ -d "$GD/rebase-apply" ]; then echo "live: merge/rebase in progress; left alone"
   else git -C "$LIVE" merge --ff-only -q "origin/$DEF" && echo "live: fast-forwarded to $(git -C "$LIVE" rev-parse --short HEAD)" || echo "live: cannot fast-forward (local commits?); left alone"
   fi
   ```
   - Each "left alone" outcome is one line in your report. Never resolve it yourself: no stash, no reset, no rebase, no checkout of another branch.
   - `--ff-only` refuses rather than overwriting an untracked file, so untracked files are not checked first.
   - Use `git -C`, never `cd` into the live checkout: the session's cwd persists.

## Another forge

On a forge without `gh` (Forgejo, Gitea, GitLab), the rules are the same: poll
every check of the head commit to completion, read the result as its own step,
never use the forge's own "merge when checks succeed" switch, then merge. Keep
the forge's API recipe (host, credentials) in a local skill or note of your
own: it is machine-specific and does not belong here.

## Notes

- A self-hosted runner is often the slow part (image-build smoke tests can queue for many minutes) — the fast gating signal is usually the lint/typecheck/test job; don't mistake "one job green" for "all required checks green."
- This applies to your own repositories. For PRs into someone else's repo (upstream OSS, forks contributing back), merge timing/strategy is up to that repo's maintainers, not this workflow.
