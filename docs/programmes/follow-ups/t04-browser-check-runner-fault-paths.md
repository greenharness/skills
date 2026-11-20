+++
type = "task"
mode = "afk"
status = "open"
blocked_by = []
repos = ["greenharness-skills"]
+++
# Does the browser-check runner lose or leak anything on its fault paths

## Question

The browser-check-fallbacks review (2026-11-19) kept three of the
Playwright runner's fault paths as deliberate. Is each worth fixing now?

- A fault after the report is printed is lost: nothing reaches stderr.
- A fault before a report skips what `stopOnSignal` does on a signal:
  stopping npm and removing the temporary directory. One shutdown helper
  would serve both.
- A crash between the aside rename and the second rename of the
  Playwright install leaves a `.stale-<pid>` sibling behind, which nothing
  sweeps.

## Look at

- `parts/workflow/skills/browser-check-runner/run.mjs`: the install
  (`mkdtempSync` near l.99, the `.stale-${process.pid}` aside near
  l.116), `stopOnSignal` (l.270) and its `SIGINT`/`SIGTERM` handlers.
- `docs/plans/2026-11-19-browser-check-fallbacks.md`, where the review
  findings were kept deliberate.

## Answer looks like

Per fault path: fixed with a test that fails first, or closed as not worth
doing, with the reason. A fix writes a late fault to stderr, routes a fault
before the report through the same shutdown as a signal, and either sweeps
`.stale-*` siblings at the next install or names the aside with `mkdtemp`.
