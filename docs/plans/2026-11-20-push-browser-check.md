---
canonical: greenbelay:docs/plans/2026-11-20-push-browser-check.md
phases: [7, 8, 9]
status: done
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

## Verification

- Item 7: `python3 -m unittest discover -s tests` → `AgentText.test_report_contract_greenbelay_reads` pins `browser:` first, `url:` second, the one-line `unreachable: <url>` with no `browser:` line, `chrome-error://`, `about:blank`, the failing-step sentence and the `<<<TREE repo=… sha=…>>>` line; the existing `test_report_block_starts_with_browser` still matches → observed 2026-11-20: 136 tests, OK (the first wording broke the existing regex and was moved below the block).
- Item 8: F2 and F7 read against each other → F7 step 2 takes `<sha>` from a `tree-sha --block` run at the start of F7 and 3b reuses it; a commit after step 2 re-runs both → observed: reviewers' round-2 finding (two directories per commit) resolved on tree `4facbaaf`.
- Item 9 (release, grh pin bump): after this PR merges, once greenbelay's release is installed; not observed here.

## Implementation review

- implementation-review: approve (round 1 8914e204, Delta 07eac763, Delta 4facbaaf); lows: this Verification row (now here), `about:blank` pinned (fixed). 33k/26k/30k tokens, 23/16/28 s.
- backend profile: approve-with-changes → approve on 4facbaaf; fixed: "unreachable" defined, 12 hex after `sha=`, 3b re-runs tree-sha, one evidence directory, whitespace-safe test. 43k/26k/24k, 52/17/10 s.
- Carried to greenbelay: the parser must reject `unreachable:` reports and a `url: chrome-error:` line, with a fixture copied from this report block (`profile:` suffix included).
