+++
type = "task"
mode = "afk"
status = "open"
blocked_by = []
repos = ["greenharness-skills"]
+++
# Should a generated verify skill's Launch wait on progress, not a fixed deadline

## Question

Filed from the inbox (2026-11-20, session da7c0c30). The duro-app `verify`
skill's Launch (t05, `2f1d81b`) gives up on server-group CPU progress, not a
fixed wall deadline: it needs 2 CPU-seconds per 30 s, it stops below the
600 s Bash ceiling, and it tells callers to set the tool timeout to 600000.
Should `create-verify-skill` write every generated Launch that way, so a
slow, busy host is not taken for a server that never started?

## Look at

- `parts/workflow/skills/create-verify-skill/SKILL.md`: what it says about
  Launch and readiness today.
- duro-app commit `2f1d81b`: the wait loop.
- `tests/test_create_verify_skill.py`: what pins the generator's text.

## Answer looks like

Either `create-verify-skill` tells a generated Launch to wait on progress
(the signal, its floor, a cap below the Bash ceiling, the timeout callers
must set), with a test, or the reason a fixed deadline is enough.
