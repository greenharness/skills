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
and which wait for a third repository (rule of three)?

## Look at

- The plan's Decision log: Phase 2 feedback (1)–(5) and Phase 3
  feedback (1)–(7).
- `parts/workflow/skills/create-verify-skill/SKILL.md` § 1 Investigate
  (Isolate), § 2 Launch, Doctor and Drive, § 3 Map the features.
- `tests/test_create_verify_skill.py`: the sentences it pins.

## Answer looks like

One greenharness-skills PR that adds the lessons both pilots share
(isolation covers credentials and config files a framework loads;
Doctor checks what the app wired; a stdlib helper over inline shell;
the skill is committable; feature files are written after driving the
app, not from reading it), with the test still passing, and a line in
the plan for each lesson kept back and why.
