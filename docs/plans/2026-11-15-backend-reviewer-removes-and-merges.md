---
status: done
branch: feat/reviewer-remove-merge
repos: [greenharness-skills, grh]
adrs: [ADR-0070]
---
# The backend reviewer removes and merges

## Review panel
👉 **Decide:** none — approve if a severity bracket plus a bare `remove:`/`merge:` word is enough until greenpiste counts kinds.
📍 greenharness-skills, grh · nothing built · next: Phase 1 skill text, built by a background agent. Panel: backend (opus-5-5). codex: not installed.
**Changed by review:** blocking findings exempt from the ×1.25 cap; baseline = body as presented; rollback safeguards not removable on "whom" alone.
📄 Full reviews: [2026-11-15-backend-reviewer-removes-and-merges.reviews.md](2026-11-15-backend-reviewer-removes-and-merges.reviews.md)
**Verdicts:** backend approve-with-changes ×2 (7 accepted in round 1, the test-pin later reversed); 5 carried into implementation (below).

Carried into implementation (round 2, medium/low): use one term, "the body as presented", in §4 and §7; the §7 check greps `Verdicts:.*words`, not `×1.25`; if `plan-apply` rejects an empty `new_string`, use one space and file a follow-up; the reversal line says the phrases are checked once, at release; drop the blank line in the Decision log. Words: 776 presented → 900 (×1.16).

## Picture
none: no mechanism changes shape; two text files gain rules a reviewer and the merge step follow.

## Goal
The plan panel adds but rarely removes. The t00 audit found 62 add-only lines against 7 remove-only, and a median ×1.59 word growth per review. The backend seat sits on every plan, so it now asks three subtracting questions of every phase and every safeguard, and reports `remove` and `merge` findings. The merge step makes a round's growth visible: a round that would push the body past ×1.25 of round 1's words turns its additions into one decision for the person. This is B3 of the time-to-done programme (decisions `docs/programmes/time-to-done/t02-who-subtracts.md`, ADR-0070 `work.plan-subtraction`).

## Non-goals
- The `counts=` panel line (B5, greenpiste) and the time measure (B1).
- A greenpiste parser change: a `remove` or `merge` finding keeps its severity bracket. `findings_of` (`amont-agent/crates/greenpiste-process/src/review_outcomes.rs:327`) parses only `[blocking|high|medium|low]`, so the kind goes in the text right after the bracket. The ledger therefore counts these findings by severity, with no kind; `plan-review stats` cannot count `remove` and `merge` findings until a later greenpiste change.
- `work.findings-one-per-line`: it already lists the two kinds (decisions `docs/principles/work.md:201-204`, landed with ADR-0070).
- The product owner seat: its "what not to build" bullet stays as written.

## Code review
- greenharness-skills: none — markdown only. The text is held to `scripts/check.sh` (no `work.*` keys or ADR numbers under `parts/`) and to `tests/test_agent_model_fallback.py`.
- grh: none — a two-line catalog pin.

## Behaviour
- `plan-review-backend.md` gains a "Then subtract" list after the "Then look for" list. For each phase and each safeguard (a migration, a fallback read, a reversibility path, a dual write, a census window, an extra check):
  1. **Whom does it protect?** If it protects no present user (the plan's `users=` line or the repository's known consumers), report a `remove` finding. A safeguard for an irreversible step, or for data already written, is not removable on this test alone.
  2. **Which phases can go?** A phase whose value the Goal does not name gets a `remove` finding.
  3. **Which adjacent slices merge?** Two slices meeting all of these get a `merge` finding, which states the PRs, releases and previews saved:
     - same repositories and review profiles;
     - no 🧑 step between them;
     - neither useful alone;
     - combined diff within the review budget;
     - same kind of risk, so an irreversible step stays alone.

  The output format line becomes `[blocking|high|medium|low] [remove: |merge: ]<the problem>`: the kind is a bare word after the severity bracket. The finding's patch removes or merges the text, so `plan-apply` applies it like any other.
- `plan-review` §4 (Merge) gains a bullet before the record step. Count the body's words (`wc -w` on the scratch copy against the planned edit) against the body as presented to the panel; every round compares to that same number.
  - A round that would add a phase, or grow the body past ×1.25 of round 1, states for each addition what it protects.
  - Past ×1.25, the additions become one 👉 decision for the person instead of edits. `[blocking]` findings and findings that fix a wrong or unverifiable statement are exempt and stay edits.
  - A `remove` or `merge` finding is accepted or rejected like any other. Rejecting one needs a reason that names whom the phase protects.
- `plan-review` §7: the `**Verdicts:**` line also gives the word count, round 1 → final (×ratio), and the number of `remove` and `merge` findings accepted.

## Phases
- [x] Phase 1 — skill text: `parts/workflow/agents/plan-review-backend.md`, `parts/workflow/skills/plan-review/SKILL.md`. Checks: `scripts/check.sh` and `python3 -m unittest discover -s tests -v` pass. Check that `plan-apply` accepts a removal patch (empty `new_string`). One commit, one PR, merge on green.
- [x] Phase 2 — release the next free tag after checking `git tag` and the data-names plan (`v0.8.0` if free) (tag-release skill), then pin it in grh `catalog.toml` (`skills_version`, `skills_sha256` from the release's `SHA256SUMS`) in its own PR. Then install the new grh on this machine (do-all memory). Check that `~/.claude/agents/plan-review-backend.md` contains "Then subtract".

## Decision log
- 2026-11-15 — Use the severity bracket plus a kind word, not a new bracket label, because greenpiste's `findings_of` and `record` validation reject unknown labels. A first-class kind is a later greenpiste change, not part of B3.
- 2026-11-15 — The ×1.25 bar on words, not phases, because t00 found that reviews add phases rarely (3 of 23) but words at ×1.59 (t01 resolution 1).
- 2026-11-15 — No new test pin for the added phrases: the test-pin finding was accepted in round 1, then reversed, because naming the Python test file seats three more reviewers (python, tui, unix) for two phrases the Verification greps check once, at release. The existing pin test still guards SKILL.md.
- 2026-11-15 — `plan-apply` accepts an empty `new_string` (checked on a sandboxed copy, applied, rc 0), so no follow-up is needed for a removal patch.

## Verification
- Phase 1: `scripts/check.sh` → exit 0, with no `work.` or `ADR-` hit under `parts/` → observed: "25 check(s) passed", exit 0. `python3 -m unittest discover -s tests` → observed: "Ran 109 tests … OK". `grep -c "Then subtract" parts/workflow/agents/plan-review-backend.md` → observed: 1. `grep -c "×1.25" parts/workflow/skills/plan-review/SKILL.md` → observed: 2 (both in §4). `grep -n "Verdicts:.*words" parts/workflow/skills/plan-review/SKILL.md` → observed: 1 (§7). `plan-apply` with an empty `new_string` on a sandboxed copy → observed: "applied 1, unmatched 0", rc 0.
- Phase 2: the release asset's sha256 equals the grh pin. After the install, `grep -c "Then subtract" ~/.claude/agents/plan-review-backend.md` prints 1. → Observed: v0.8.0 asset sha256 191ad87a…c442 equals SHA256SUMS and the grh 0.6.1 pin (grh#41); after `brew upgrade` to grh 0.6.1 and `grh install workflow --yes`, the grep prints 1, and "body as presented" occurs 2× in the installed plan-review skill.
- Live: the next plan panel run under it shows a §7 Verdicts line with words r1 → final. This is checked at the t10 done check, not here.

## Implementation review
- backend (opus, round 1): approve; one low finding, the §7 grep, fixed above by checking `Verdicts:.*words`. ~27k tokens, ~14 s. No findings kept as deliberate. Watch: the 350-word cap on backend output may tighten with the added "Then subtract" list.
- implementation-review (opus, main session, tree 9f6881de47e3): approve, ~31k tokens, 29 s. One low finding was kept as deliberate: the template line's `[remove: |merge: ]` brackets could be copied literally. The prose and the examples at plan-review-backend.md:97-99 already show the bare word.

## Outcome
Shipped: skills v0.8.0 (#23) and grh 0.6.1 (#41), installed here 2026-11-15. The backend seat now asks whom each phase and safeguard protects, which phases can go, and which slices merge. Plan-review §4 caps a round's growth at ×1.25 of the body as presented. Surprise: the implementation-review push hook counts only reviews launched from the pushing session, so a forked builder cannot push; the main session ran F4b and every push. Not yet seen: a live panel under the new text (the t10 done check).

<!-- panel: repos=greenharness-skills,grh adds= reviewers=backend body-sha=3a7dc15edcc4 -->
