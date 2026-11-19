---
name: create-verify-skill
description: Write a repository's own `verify-<app>` skill by investigating how the app starts, is driven and is observed, then run it once. Use when asked to make an app verifiable or to write a verify skill, and when worktree-task F2 finds the repository has no `verify-*` skill.
---

# create-verify-skill

Write `.claude/skills/verify-<app>/` for the repository you are in, so that
the next session starts the app, drives a feature and collects proof from a
recipe instead of working it out again. The reader of the result is an agent
that has never seen this app.

The skill is a generator: it investigates, writes, and runs what it wrote.
It does not verify the change in front of you. That is `worktree-task` F2,
which reads the skill this one produces.

## 1. Investigate

Read the repository; ask the person only for what it cannot show. Write down
five facts, each with the file it came from:

- **Surface**: what a user touches (web UI, CLI, service API, desktop,
  mobile, library).
- **Run**: the exact command that starts it from an empty data directory,
  and the signal that it is usable (a route answering with content, a log
  line, a socket), not just that a process exists.
- **Drive**: how an agent operates it. An existing test harness or e2e
  runner first, then a generic handle (browser protocol, a pty, HTTP).
- **Observe**: what evidence can be captured (screenshot, response body,
  log, exit code, database row).
- **Isolate**: whether two instances can run side by side (own port, own
  data directory). If they cannot, the skill declines to drive a shared
  instance and reports a blocker.

If the checkout does not build or start, report that as a blocker before
writing anything. Scaffolding you add to get it running is labelled and
removed in the cleanup of this task.

## 2. Write the skill

Create `.claude/skills/verify-<app>/SKILL.md` with frontmatter (`name`
equal to the directory, one-line `description`) and, as its first lines
after the title, a `generated-from:` list: each file the recipe was read
from with its blob hash (`git hash-object <file>`). A later session can then
see by hand which source moved since the recipe was written.

Write for an agent with only this file in hand. Keep lines under 80
columns. Five sections, named exactly as below.

### Launch

- The command from an empty data directory, and the readiness signal from
  step 1. Fail non-zero when it is not met within a deadline of 60 s or
  more: the first execution of a fresh binary can be slow.
- Non-interactive: `CI=1 NO_COLOR=1`, an explicit free port (bind port 0 and
  read it back), no prompt that can stall. Output goes to a log file in
  the state directory, never to the session. On a timeout print the last 20
  log lines and the log path.
- The state directory comes from `mktemp -d`. Its path is written into the
  pidfile, so a later call can find it.
- Start the server as the leader of its own process group, so Cleanup can
  signal exactly the tree you started. macOS has no `setsid(1)`; use
  Python's `subprocess.Popen(..., start_new_session=True)` with stdout and
  stderr opened on the log file, so the tool call does not wait on a pipe.
  Write the pidfile as JSON: the process-group id, the leader pid, the
  command and the state directory.
- Check readiness against your own tree: the listener on the port must
  belong to your process group (`lsof -t -iTCP:<port> -sTCP:LISTEN`). A
  foreign server on the same port must never count as ready.
- A `trap` on EXIT INT TERM tears down a failed or interrupted launch. It
  covers launch-until-ready only and is cleared (`trap - EXIT INT TERM`)
  once ready: every agent tool call is a fresh shell, and an EXIT trap left
  armed would kill the app before Drive runs.

### Doctor

One read-only command that says whether the app is usable now. It prints one
line, `ok: <what>` or `fail: <what> — run <command>`, with `fail:` lines on
stderr, and exits 0 when ready, 1 when not ready and 2 when a precondition
is missing. Keep the line under 80 columns and the command copy-pasteable.
Run it before Drive; a failing Doctor is a blocker report, not a repair.

### Drive

The real selectors, routes or commands for the top features, with stable
handles (roles, labels, test ids, flags) in preference to coordinates. For a
user interface, say to hand the browser work to the `browser-check` agent
with the route, login and seed; add a fallback line for a checkout that does
not have that agent (drive it with the project's own e2e runner). Every step
that needs another Green Harness part carries a fallback line.

Say how a login is provided (a dev-login switch, a seeded throwaway
account). Never a real password and never a session token.

### Evidence

Proof that the feature works, taken through the real user path: record the
action and the resulting state, check side effects, and say what a dry run
skips. Files go to the directory `worktree-task` F3 names, outside the
worktree: never a repository-relative path, never a literal home path in the
skill. A skipped precondition is a failure, not a pass.

### Cleanup

Its own step, run from a fresh shell with only the pidfile in hand:

1. Read the pidfile. If it is missing, print `fail: no pidfile at <path> —
   nothing to stop` and exit non-zero.
2. Check the process-group leader still matches the recorded pid and
   command (`ps -o pid=,command= -p <leader>`). If it does not, signal
   nothing: the group id may have been reused. Only remove the state
   directory.
3. `kill -TERM -<pgid>`, wait a few seconds, then `kill -KILL -<pgid>`.
   Never `pkill` or `killall` by name: another session's server may share
   the name.
4. Remove the state directory. Print `ok: stopped <pgid>, removed <dir>`.

Evidence must survive cleanup: copy it out first.

## 3. Map the features

Add `features/README.md` as an index and one file for each of the three to
five most important features. Each file has four parts: sub-features, how to
get to it, driving it, and gotchas (the traps the repository's prose already
warns about, such as a cold-start reload or a flag that must be set). A
missing precondition is reported as a failure; never weaken a journey to
make it pass.

## 4. Run it

Run the generated skill once, end to end, before you call it done.

Launch, Drive and Cleanup as three separate tool calls, with the app still
up between them. Then confirm: Doctor exits 0 while the app is up; the
evidence file exists and `git status` shows nothing new; after Cleanup the
process group is empty (`pgrep -g <pgid>`), a decoy process with the same
name as the server is still alive, and the state directory is gone. Run
Cleanup after a failed attempt too.

A generated skill that was never executed is a draft: say so. If you ran it
in a stand-in environment, list every setup step that stayed unverified on
the real target.

## 5. Report

One short message: the path written, what the run showed (the Doctor line,
the evidence path, the cleanup check), and the unverified list. Commit the
skill with the task that needed it. When a recipe goes stale, the next F2 run
fails on the stale step and fixes it in that pull request.
