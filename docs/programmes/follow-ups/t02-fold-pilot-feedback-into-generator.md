+++
type = "task"
mode = "afk"
status = "closed"
blocked_by = []
repos = ["greenharness-skills"]
+++
# Which pilot lessons belong in create-verify-skill's text

## Question

The two pilots (sre-agent #95, duro-app) each hit traps the generator's
text does not warn about. They are listed under "Generator feedback" in
`docs/plans/2026-11-19-create-verify-skill.md`'s Decision log. Which of
them go into `parts/workflow/skills/create-verify-skill/SKILL.md` now,
and which wait for a third repository (rule of three)? Process and signal
correctness is not a pattern to wait on: a known teardown defect would
repeat in every generated skill.

## Look at

- The plan's Decision log: Phase 2 feedback (1)–(5) and Phase 3
  feedback (1)–(7).
- `parts/workflow/skills/create-verify-skill/SKILL.md` § 1 Investigate
  (Isolate), § 2 Launch, Doctor and Drive, § 3 Map the features.
- `tests/test_create_verify_skill.py`: the sentences it pins.

## Answer looks like

One greenharness-skills PR that adds, now:

- every process and signal item (Phase 2 (3), Phase 3 (6)): hold HUP,
  INT and TERM across `Popen` and the `pgid` and pidfile writes (this
  also closes the recipe's one-syscall window) with a signal mask, not
  `SIG_IGN`, and unblock them in the child (`preexec_fn`), since a
  blocked mask survives exec and the server would ignore Cleanup's TERM;
  print the pidfile path
  before starting, keep the failure log outside the state directory,
  list a group with `pgrep -lg`, treat `EPERM` from `killpg` on an
  exiting group as gone when the group is empty;
- the lessons both pilots share: isolation covers credentials and config
  files a framework loads; Doctor checks what the app wired; a stdlib
  helper over inline shell; the skill is committable; feature files are
  written after driving the app, and a fresh-context F2 runs before the
  skill is called done.

The test still passes, and the plan gets a line for each lesson kept
back (launcher choice, untyped-config scan, role coverage) and why.

## Resolution

2026-11-19: folded into `create-verify-skill/SKILL.md` in one PR. In
now: every process and signal item (the mask across `Popen` and the
`pgid` and pidfile writes, unblocked in the child with `preexec_fn`;
HUP held; the second signal; the pidfile path printed before anything
starts; the pidfile written before slow calls with a `null` start time
until `ps` returns; the log outside the state directory; `pgrep -lg`;
`EPERM` as gone only for an empty group; the timeout naming its last
failed readiness check), and the shared lessons (isolation of
credentials, cluster config and framework-loaded files; Doctor checks
what was wired; a stdlib `scripts/verify.py` held to the repository's
lint rules; the skill is committable; feature files after driving; a
fresh-agent run before done). The test pins each; the one moved pin is
`trap - EXIT HUP INT TERM`, since HUP is now held. Kept back for a third
repository: launcher choice, the untyped-config scan, role coverage
(lines in the plan's Decision log).
