---
status: active
plan-id: p-01M8EAE319E0Q6DEDASTGR4FXX
branch: docs/rebase-carries-review
repos: [skills]
adrs: []
---
# A rebase does not call a new implementation review

## Review panel

👉 **Decide:** none — approve if wording the push-as-check rule into the skill is enough, with no hook change.
📍 skills · 2 phases · 1 PR · 2 steps for you · next: Phase 1. Panel: backend (opus); codex skipped.
**Changed by review:** "asks no review" became "usually, the push decides"; rule-file and heading cases named; a refusal is expected.
**Verdicts:** backend approve-with-changes, then delta approve-with-changes; 2 medium carried (Picture's second branch, keep-both issue and the `:1633` citation); words 981 → 1052 (×1.07); remove 0, merge 0.
📄 Full reviews: [2026-11-27-rebase-asks-no-new-review.reviews.md](2026-11-27-rebase-asks-no-new-review.reviews.md)

## Context

PR #636 (an-t38) had to be rebased after #638 merged: the only conflict was
`CHANGELOG.md`. The session wanted a rebase, a fresh round of checks and "a
fresh run of the implementation review", and asked the person whether to
proceed. A review of a rebased tree is wasted when nothing the reviewer read
changed.

The hook already knows this. greenbelay's `implementation-review` rule
(`greenbelay/crates/greenbelay-process/src/implementation_review.rs`) carries
a pass onto a rebased tree in two cases:

- the branch patch (merge-base to head, `docs/plans/` left out) is unchanged
  and the repository's rule files (`AGENTS.md`, `CLAUDE.md`, `.adr.yaml`,
  `.adr/`, `.claude/`) are unchanged: journalled `reviewed-by-patch`;
- only the context or blank lines of the root `CHANGELOG.md` moved: journalled
  `reviewed-by-patch-notes-moved`. A conflict resolved by keeping both
  entries leaves the branch's own added lines the same, so it lands here.

The `worktree-task` skill does not say so. F8 reads "Any code change or rebase
after F4 returns to F1", F1 says nothing about the review, and the carry is
named only for the step 2c profiles, in one clause of F4b step 6. A model
reading it takes every rebase as a new F4b round. So the wording is the
defect; the hook needs no change.

## Non-goals

- No change to the greenbelay hook or its stances. If a real push is refused
  after a conflict-only rebase, that is a separate bug to file against
  greenbelay, with the refusal text.
- No new exemption for "docs-only branches". A branch that carries a plan
  still owes a review of its own first diff; only the rebase is addressed.
- The sibling clone `greenharness-skills` is not touched (the person removes it).

## Code review
- skills: none — no reviewed file type (markdown wording in one skill file).

## Behaviour

After this change `worktree-task` tells the model, for a rebase after F4:

1. **F1.** Record the head before the rebase (`old=$(git rev-parse HEAD)`) and,
   after it, the review is not re-run by default. Whether the earlier pass
   still holds is the hook's judgement at the push, not the model's: continue
   to F6 and let `amont land` / `git push` answer. A refusal that names the
   review is an expected answer, not a failed check, and sends the session
   back to F4b; a push that goes through (the
   hook journals `reviewed-by-patch` or `reviewed-by-patch-notes-moved`)
   needed none.
2. **F1, conflicts.** A conflict whose resolution only keeps both sides of
   release notes (`CHANGELOG.md` and nothing else) usually changes no line the
   reviewer read: launch no new review, brief or Delta, and let the push
   decide. It still misses when main changed a rule file (`AGENTS.md`,
   `CLAUDE.md`, `.adr.yaml`, `.adr/`, `.claude/`) or when the resolution adds a
   line of its own (an `## Unreleased` heading put back after a release). Anything else resolved by hand (code, tests,
   a rule file) changes the patch: F2 runs again on the touched area and the
   hook will ask for the review it is owed.
3. **F8.** Reworded: a code change after F4 returns to F1. A rebase returns
   to F1 only to re-run F2 when the conflict resolution touched something
   beyond `CHANGELOG.md`; the review follows the hook's answer, per F1.
4. **F4b step 6.** The sentence "A rebase carries nothing by ancestry, so its
   profiles re-run unless …" is kept and made general: the same carry rule
   covers `implementation-review` itself, not only the step 2c profiles.
   The model never launches a round to learn whether a pass carries.

What the model must not do: assert in prose that a pass carries. The push is
the check (this matches the skill's existing rule "Never assert in prose that
something is unchanged").

## Picture

```
rebase onto moved main
   │
   ├─ clean, or CHANGELOG.md only, rule files unchanged on main
   │     └─▶ push ─▶ hook: same patch, or notes moved
   │                   └─ pass carried ─▶ lands, no review
   │
   └─ code resolved by hand
         └─▶ F2 again ─▶ push ─▶ hook refuses: review owed
                                   └─▶ F4b, round 1 on the new patch
```

The push is the question put to the hook: a carried pass lands with no
review, and only a refusal that names the review sends the session back.

## Phases

- [ ] Phase 1 — reword F1, F8 and F4b step 6 of the worktree-task skill:
  `parts/workflow/skills/worktree-task/SKILL.md`. The published text carries
  no ADR numbers and no `work.*` rule ids (`scripts/check.sh` refuses both);
  name the journal words `reviewed-by-patch` and `reviewed-by-patch-notes-moved`
  instead. Becomes one commit, `docs(workflow): a rebase asks no new review`.
- [ ] Phase 2 — close the plan and the changelog line if the repository keeps
  one: `docs/plans/2026-11-27-rebase-asks-no-new-review.md`. Becomes the
  closing commit.

### 🧑 Your steps
- `rm -rf ~/Developer/Perso/greenharness-skills` — the duplicate clone of this repository; a session cannot delete a registered workspace directory
- install the next skills release into `~/.claude/skills` (your usual bundle update) — the live copy in `~/.claude/skills/worktree-task/SKILL.md` is not a link, so the wording applies only after a release is installed; the agent does not cut releases unasked

## Decision log

- 2026-11-27 — fix the wording, not the hook, because the hook already carries a
  pass over a conflict-only rebase and over a CHANGELOG-context move (read in
  `implementation_review.rs`; its tests are in `greenbelay/tests/implementation_review.rs`).
  The "keep both" case has no fixture (the notes-moved test at
  `greenbelay/tests/implementation_review.rs:1601` moves an intro line only); a
  test for it is filed against greenbelay as a follow-up.
  Not run against a real #636 push: the first real push after this change is
  the live check (see Verification).

## Verification

Phase 1 is wording, so its check is a focused one plus one live check:

1. `sh scripts/check.sh` exits 0 (no machine-specific pattern in `parts/`).
2. `git diff origin/main -- parts` shows only the three passages above, and
   `grep -n 'reviewed-by-patch' parts/workflow/skills/worktree-task/SKILL.md`
   finds the journal words in F1 and F4b.
3. Read-through against the hook source: every claim in the new text
   (what carries, what does not) is in `implementation_review.rs` lines 32–43
   and `notes_patch`; nothing is claimed beyond them.
4. Live, after the release is installed: the next conflict-only CHANGELOG
   rebase pushes with no review round, and `greenbelay` journals
   `reviewed-by-patch-notes-moved`. Until then it is recorded as unobserved.

<!-- panel: repos=skills adds= reviewers=backend body-sha=f8dc56758ad6 -->
