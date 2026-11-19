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
- Non-interactive: `CI=1 NO_COLOR=1`, a free port (bind port 0, read it
  back, and retry Launch once on a new port if the bind then fails), no
  prompt that can stall. Output goes to a log file, never to the session.
  On a timeout print the last 20 log lines to stderr, and the log path.
- Say how a login is provided (a dev-login switch, a seeded throwaway
  account). Never a real password and never a session token. The preview
  guide's `Sign in:` line cites this.
- The state directory comes from `mktemp -d` and holds the log. The pidfile
  lives outside the repository at a path keyed by the worktree, for example
  `${TMPDIR:-/tmp}/verify-<app>-<hash of the worktree path>.json`. Launch
  prints that path as its only stdout line and Cleanup takes it as its
  argument. If a pidfile is already there and its group is still alive,
  Launch stops with `fail:` and does not start a second server.
- Start the server as the leader of its own process group, so Cleanup can
  signal exactly the tree you started. macOS has no `setsid(1)`; use
  Python's `subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=log,
  stderr=subprocess.STDOUT, start_new_session=True)`, with `log` opened in
  append mode and closed in the launcher once `Popen` returns, so the tool
  call does not wait on a pipe. The group id is `proc.pid`.
- Write the pidfile as JSON (group id, leader pid, the leader's start time
  from `ps -o lstart=`, the command and the state directory) to a temporary
  name, then rename it into place, so no reader sees half a file.
- Check readiness against your own tree: list the listeners with
  `lsof -nP -t -iTCP:<port> -sTCP:LISTEN`, map each pid to its group with
  `ps -o pgid= -p <pid>`, and require the recorded group id. A foreign
  server on the same port must never count as ready.
- A `trap` on EXIT INT TERM tears down a failed or interrupted launch. Arm
  it before `Popen`, exit 130 on INT, 143 on TERM and 1 on a missed
  deadline. It covers launch-until-ready only and is cleared
  (`trap - EXIT INT TERM`) once ready: every agent tool call is a fresh
  shell, and an EXIT trap left armed would kill the app before Drive runs.

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

### Evidence

Proof that the feature works, taken through the real user path: record the
action and the resulting state, check side effects, and say what a dry run
skips. Files go to the directory `worktree-task` F3 names, outside the
worktree: never a repository-relative path, never a literal home path in the
skill. A skipped precondition is a failure, not a pass.

### Cleanup

Its own step, run from a fresh shell with only the pidfile path in hand:

1. Read the pidfile. If it is missing, print `fail: no pidfile at <path> —
   nothing to stop` and exit 1.
2. Decide whether the group is ours. If `pgrep -g <pgid>` lists members, it
   is: a group id is not reused while any member lives, even after a wrapper
   leader exited. If the group is empty, signal nothing and only remove the
   state directory. If the leader pid is alive but its start time differs
   from the recorded one, it belongs to someone else: signal nothing.
3. `kill -TERM -<pgid>`; poll `pgrep -g <pgid>` for up to 5 s; then
   `kill -KILL -<pgid>`. Treat "no such process" as already gone.
   Never `pkill` or `killall` by name: another session's server may share
   the name.
4. If members survive the KILL, print `fail: <pgid> still has <pids>`,
   keep the state directory and exit 1. Otherwise remove the state
   directory and the pidfile, print `ok: stopped <pgid>, removed <dir>` and
   exit 0.

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
name as the server is still alive, and the state directory is gone.
Interrupt a second Launch before it is ready: no listener and no state
directory may remain. Run Cleanup after a failed attempt too.

A generated skill that was never executed is a draft: say so. If you ran it
in a stand-in environment, list every setup step that stayed unverified on
the real target.

## 5. Report

One short message: the path written, what the run showed (the Doctor line,
the evidence path, the cleanup check), and the unverified list. Commit the
skill with the task that needed it. When a recipe goes stale, the next F2 run
fails on the stale step and fixes it in that pull request.
