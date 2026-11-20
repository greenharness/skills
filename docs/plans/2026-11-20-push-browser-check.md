---
canonical: greenbelay:docs/plans/2026-11-20-push-browser-check.md
phases: [7, 8, 9]
status: active
---
# push-browser-check: a UI push carries a browser check of its own tree (pointer)

Canonical plan: [greenbelay/docs/plans/2026-11-20-push-browser-check.md](https://github.com/greenharness/greenbelay/blob/main/docs/plans/2026-11-20-push-browser-check.md).

This repository carries items 7–9 of its Changes: the `browser-check` agent's
brief may carry the `<<<TREE repo=… sha=…>>>` line and its report keeps
`browser:` first and `url:` second, with an unreachable URL as the one line
`unreachable: <url>`; worktree-task F2 and F7 3b put the tree block in the
brief and re-run the check when the tree changes; a test pins the report
lines greenbelay's `push-browser-check` parses.

## Code review

- greenharness-skills: backend (the browser-check brief and report become a contract greenbelay parses)
