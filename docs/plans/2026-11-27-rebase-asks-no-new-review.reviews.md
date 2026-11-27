# Full reviews: a rebase does not call a new implementation review

**backend, round 1 — approve-with-changes (34k tokens, 46 s).**
1. high, accepted: "asks for no new review" is false when main changed a rule
   file or a resolution puts an `## Unreleased` heading back (the hook hashes
   every non-blank changed `CHANGELOG.md` line and both keys must match).
2. medium, accepted: the Picture's carry branch omits the rule-file condition.
3. medium, accepted: "keep both" has no test; record it in the Decision log.
4. low, accepted: a refusal after `amont land` is expected, not a failed check.

**backend, round 2 (delta) — approve-with-changes (29k tokens, 34 s).**
1 and 4 resolved. 2 not resolved: the second Picture branch still says "code
resolved by hand"; relabel it "anything else". 3 partly resolved: cite
`greenbelay/tests/implementation_review.rs:1633` (the
`a_rebase_that_only_moves_changelog_context_keeps_the_review` test), and
make Phase 2 file the greenbelay issue and write its number in the Decision
log. Both carried into implementation: after round 2 only a high or
blocking finding may change the body.

**codex:** skipped. The CLI is installed, but the optional final review would
send the plan's project, repository and path names to an outside vendor, and
the person has not asked for that.
