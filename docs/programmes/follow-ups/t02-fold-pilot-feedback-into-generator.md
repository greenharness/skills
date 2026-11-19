+++
type = "task"
mode = "afk"
status = "open"
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
