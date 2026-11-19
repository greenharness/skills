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
  instance and reports a blocker. Isolation also covers what the app reads
  besides its port and data: credentials and cluster config (a client built
  from `KUBECONFIG` at boot reaches the real cluster), and files a framework
  loads over the environment (a dev server that copies `.env*` from the
  checkout over the process environment). Build the server's environment
  from nothing, add only what the recipe names, and refuse a non-loopback
  URL or remote server in it.

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

Put the steps in one stdlib-only helper beside the skill,
`scripts/verify.py`, with a subcommand for each (`launch`, `doctor`,
`drive`, `cleanup`), and have SKILL.md call it. Both pilots ran a helper
more reliably than inline shell, and their reviews found signal-window
bugs that inline shell would have hidden. The repository's own lint and
format rules apply to the helper (a ruff `S` or `T20` selection, say).

The skill is committed: before writing it, `git check-ignore -v
.claude/skills/verify-<app>/SKILL.md` must print nothing. If `.claude/` is
ignored, add a negation for the skill's directory in the same change.

### Launch

- The command from an empty data directory, and the readiness signal from
  step 1. Fail non-zero when it is not met within a deadline of 60 s or
  more: the first execution of a fresh binary can be slow.
- Non-interactive: `CI=1 NO_COLOR=1`, a free port (bind port 0, read it
  back, and retry Launch once on a new port if the bind then fails), no
  prompt that can stall. Output goes to a log file, never to the session.
  On a timeout print the last 20 log lines to stderr, the log path, and
  the last readiness check that failed.
- Say how a login is provided (a dev-login switch, a seeded throwaway
  account). Never a real password and never a session token. The preview
  guide's `Sign in:` line cites this.
- The state directory comes from `mktemp -d` and holds the server's data.
  The log lives outside it (beside the pidfile, `<pidfile>.log`): the
  teardown of a failed Launch removes the state directory (unless a member
  survives) and keeps the log on purpose, since it explains the failure.
  Launch opens the log only after the alive-group check passes, emptying
  what a failed attempt left; Cleanup removes it. The pidfile lives outside
  the repository at `${TMPDIR:-/tmp}/verify-<app>-<h>.json`, where `<h>` is
  the first 12 hex characters of the sha1 of the worktree's real path.
  Launch prints that path as its only stdout line, before it starts
  anything, and flushes it (`print(path, flush=True)`: a tool call's stdout
  is a pipe, which Python buffers), so a SIGKILLed Launch still leaves its
  caller the path; Cleanup takes it as its argument. If a pidfile is already
  there and its group is still alive, Launch stops with `fail:` and starts
  nothing. Two Launches started at the same instant are not guarded against;
  say so in the generated skill.
- Start the server as the leader of its own process group, so Cleanup can
  signal exactly the tree you started. macOS has no `setsid(1)`; use
  Python's `subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=log,
  stderr=subprocess.STDOUT, start_new_session=True)`, with `log` opened in
  append mode and closed in the launcher once `Popen` returns, so the tool
  call does not wait on a pipe. The group id is `proc.pid`.
- Right after `Popen`, write the group id to a file named `pgid` in the
  state directory, so an interrupt before the pidfile exists still has
  something to tear down. Then write the pidfile as JSON (group id, leader
  pid, the command as the argv list passed to `Popen` with no
  `shell=True`, the state directory and the log path) to a temporary
  name in the same directory, and move it into place with
  `os.replace(tmp, path)`, so no reader sees half a file. Write it before
  any slow call: the leader's start time (`ps -o lstart=`) is added in a
  second write once `ps` returns, and until then the start time is `null`.
- Hold HUP, INT and TERM from just before `Popen` until the pidfile is on
  disk: `signal.pthread_sigmask(signal.SIG_BLOCK, held)`, released in a
  `finally` that sits inside the guarded block below. A signal that arrives
  meanwhile is delivered when the mask is released, and its handler raises
  there, into the teardown; so no interrupt lands between `Popen` and the
  `pgid` write. Use a mask, never `SIG_IGN`: changing a disposition while a
  signal is pending races. A blocked mask survives exec, so pass
  `preexec_fn=<unblock the held signals>` to `Popen`; without it the server
  would ignore Cleanup's TERM. The launcher stays single-threaded:
  `preexec_fn` is not safe once a thread exists. HUP is held too: a closed
  tool-call shell must tear the attempt down, since the server runs in its
  own session and would outlive the launcher.
- Check readiness against your own tree: list the listeners with
  `lsof -nP -t -iTCP:<port> -sTCP:LISTEN`, map each pid to its group with
  `ps -o pgid= -p <pid>`, and require the recorded group id. A foreign
  server on the same port must never count as ready.
- Tear down a failed or interrupted launch from handlers for HUP, INT and
  TERM, installed before `Popen`, and a `try`/`except BaseException` around
  launch-until-ready. The handler raises once, an `Interrupted(signum)` that
  subclasses `BaseException`, so no `except Exception` around a tool call
  swallows it; a second signal re-blocks the held set and returns, so it
  never raises into the teardown, and each `except` clause blocks the held
  set before it tears down. Release the mask before a bind-failed retry. The
  teardown reads the group id from `pgid` and skips Cleanup steps 1 and 2:
  Launch spawned the group, so live members are its own. It runs step 3
  (TERM, poll, KILL) and keeps the log, printing its path. When the group is
  empty it removes the state directory and the pidfile if one was written.
  When a member survives it keeps the state directory and the pidfile, so a
  later Cleanup can finish, and prints
  `fail: <pgid> still has <pids> — check pgrep -lg <pgid>`.
  It does not take step 4's exit codes: it exits `128 + signum` (129 on
  HUP, 130 on INT, 143 on TERM), and 1 on a missed deadline or a survivor.
  It covers
  launch-until-ready only: once ready, the launcher exits and leaves the app
  up, since every agent tool call is a fresh process. A shell recipe (no
  helper) arms a `trap` on EXIT HUP INT TERM instead, exiting with the same
  codes, and clears it (`trap - EXIT HUP INT TERM`) once ready, or an EXIT
  trap left armed would kill the app before Drive runs; it cannot hold
  signals across the start, so say in the generated skill that it keeps that
  window.

### Doctor

One read-only command that says whether the app is usable now. It prints one
line, `ok: <what>` or `fail: <what> — run <command>`, with `fail:` lines on
stderr, and exits 0 when ready, 1 when not ready and 2 when a precondition
is missing. Keep the line under 80 columns and the command copy-pasteable.
Run it before Drive; a failing Doctor is a blocker report, not a repair.

Doctor checks what the app wired, not only that it answers: a health
route can stay 200 while the app fell back to a do-nothing stand-in (an
empty cluster config gave one pilot a no-op orchestrator behind a green
`/readyz`). Read the evidence that the real component is in place, from a
status route, a startup log line or a first real request.

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

1. Read the pidfile. If it is missing, remove a lone `<pidfile>.log` left
   by a failed Launch, print `fail: no pidfile at <path> — nothing to
   stop` and exit 1. (A Launch interrupted before the pidfile
   existed is torn down by its own handlers, or its trap in a shell
   recipe, from `pgid`.)
2. Decide whether the group is ours, in this order:
   - Recorded start time, leader alive, start time differs: the id was
     reused by someone else. Signal nothing, remove the pidfile, its log
     and the state directory, print `ok: <pgid> reused, nothing
     signalled` and exit 0.
   - Start time `null` (Launch was stopped before `ps` returned), which
     cannot show reuse: the group is ours only when the leader pid is
     alive, `ps -o pgid= -p <pid>` is the recorded group id and
     `ps -ww -o command= -p <pid>` (full width), stripped, equals the
     recorded argv joined with single spaces, `" ".join(argv)`, which is
     how `ps` prints it, unquoted. A script started through its `#!` line
     shows its interpreter first, so record the argv with the interpreter
     written out. Otherwise, if `pgrep -g <pgid>` lists
     members, they may be our server behind an exited wrapper: signal
     nothing, keep the pidfile, its log and the state directory, print
     `fail: <pgid> unverified, members <pids> — check pgrep -lg <pgid>`
     and exit 1. An empty group goes to the empty-group branch below.
   - Else if `pgrep -g <pgid>` lists members, the group is ours: a group
     id is not reused while any member lives, even after a wrapper leader
     exited.
   - Else the group is empty: signal nothing and remove the state
     directory, the pidfile and its log.

   To show a person what a group holds, `pgrep -lg <pgid>` lists its
   members with their names; `ps -g` does not select by group on macOS.
3. `kill -TERM -<pgid>`; poll `pgrep -g <pgid>` for up to 5 s; then
   `kill -KILL -<pgid>`. Treat "no such process" (`ProcessLookupError`)
   as already gone. macOS
   can answer `EPERM` (`PermissionError` from `os.killpg`) for a group
   whose leader has just exited: treat it as gone only when
   `pgrep -g <pgid>` then lists nothing, and as a failure otherwise.
   Never `pkill` or `killall` by name: another session's server may share
   the name.
4. If members survive the KILL, print `fail: <pgid> still has <pids>`,
   keep the state directory and exit 1. Otherwise remove the state
   directory, the pidfile and its log, print
   `ok: stopped <pgid>, removed <dir>` and exit 0.

Evidence must survive cleanup: copy it out first.

## 3. Map the features

Add `features/README.md` as an index and one file for each of the three to
five most important features. Write them after driving the app, from what it
showed: feature files written from reading the code alone were wrong in
three of four in a pilot (seed names, a button only one role sees, a panel
no route opens, tab names). Each file has four parts: sub-features, how to
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
A second Launch while the first is up exits non-zero with `fail:` and
starts nothing. Interrupt a Launch before it is ready: no listener, no
state directory and no pidfile may remain. Run Cleanup after a failed
attempt too.

Then hand the skill to a fresh agent with only the skill in hand, as
`worktree-task` F2 would read it, on one feature. The skill is done when
that run passes; a failure is fixed in the skill or its feature files,
and the fresh run is repeated.

A generated skill that was never executed is a draft: say so. If you ran it
in a stand-in environment, list every setup step that stayed unverified on
the real target.

## 5. Report

One short message: the path written, what the run showed (the Doctor line,
the evidence path, the cleanup check), and the unverified list. Commit the
skill with the task that needed it. When a recipe goes stale, the next F2 run
fails on the stale step and fixes it in that pull request.
