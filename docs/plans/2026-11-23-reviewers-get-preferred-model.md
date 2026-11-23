---
status: active
branch: feat/agent-preferred-model
repos: [greenharness-skills, greenbelay, relais]
adrs: []
plan-id: p-01M82MJ8RTDEJ9PBSJZ3AE0AZ8
---
# Reviewers get their preferred model wherever they are launched

## Review panel
📄 Full reviews: [reference](2026-11-23-reviewers-get-preferred-model.reviews.md).
👉 **Decide:** none — approve if a deny on bare reviewer launches is an acceptable price for Opus everywhere.
📍 greenharness-skills, greenbelay, relais · 3 PRs · next: skills marker + key. Panel: architect, backend, rust, po, tui, unix (opus), codex.
**Changed by review:** lookup moved to the hook (repo then config, no plugin dirs); `Agent|Task` matcher; marker only for agents declaring a preference (plan-apply's `<<<APPLY` intact).
**Verdicts:** 5 approve, 1 approve-with-changes (unix, applied); 2 carried; words 899 → 1422 (×1.58, person kept growth); remove 0, merge 0.

## Picture

```
 today (Sonnet session)              after this plan
 ----------------------              ---------------
 Agent(implementation-review)        Agent(implementation-review)
   no model                            no model
     |                                   |
     v                                   v
 definition: model: inherit          [agent-preferred-model rule]
     |                                 reads preferred-model: opus
     v                                   |            |
 runs on Sonnet                       denied ->    model: "opus" -> Opus
                                      relaunch     model-fallback: line
                                                     -> root (once)
```

A reviewer launched without a model used to inherit the session's Sonnet;
after this plan the greenbelay rule sends it back for its declared
preferred model, and only a marked fallback relaunch runs on the root model.

## Context
Since the 2026-11-04 fallback plan, the first-party reviewer and planner agents say `model: inherit` (so Codex and custom root models can run them), and the `plan-review` and `worktree-task` skills launch them with `model: "opus"`, falling back once to the root model through `agent-model-fallback`. Two gaps remain:

1. **A launch outside those skills inherits the session model.** An ad-hoc `Agent` call to `implementation-review` or a `plan-review-*` seat with no `model` runs on Sonnet in a Sonnet session.
2. **`relais-review` is pinned `model: opus`** in the template `relais install` writes (`relais/crates/relais/src/install/mod.rs`, `agent_review()`), so it cannot fall back when Opus is unavailable.

Outcome: in a Sonnet session, every launch of these agents gets Opus when Opus is available, and the root model only through the bounded fallback.

## Approach
Each agent definition declares its own preference; a greenbelay rule reads it. No tool names another's agents (every Green Harness part stays optional).

- **Frontmatter key.** Beside `model: inherit`, an agent declares `preferred-model: opus`. Added to every reviewer/planner in `greenharness-skills/parts/workflow/agents/` (implementation-review, interface-review, plan-review-*, code-review-*) and to relais's `agent_review()` template, which becomes `model: inherit` + `preferred-model: opus`. `browser-check`, `relais-research`, `relais-implementation` and the runner's pinned `relais:relais-reviewer-<model>-<effort>` agents are untouched.
- **Fallback marker.** `agent-model-fallback` step 3/4: for a named agent whose definition declares `preferred-model`, the one fallback launch without `model` starts its prompt with a line `model-fallback: <preferred> -> root (<category>)`; the rest of the prompt is unchanged. This includes later seats launched directly on fallback under the existing invocation-local cooldown policy. For agents without that declaration, preserve the entire prompt unchanged, including the plan-apply helper's leading `<<<APPLY …>>>` block. This is also the truthful model record the skill already asks for. Add regression coverage for both a marked named-reviewer fallback and an unmarked plan-apply fallback whose completed launch remains discoverable by `--record-fallback`.
- **greenbelay rule `agent-preferred-model`.** PreToolUse on `Agent` (and `Task`). It reads `subagent_type`, finds the definition in the hook path (guard cannot depend on `greenbelay-process`), by Claude Code's precedence for a bare type: the repository's `.claude/agents/` (root from the payload's top-level `cwd`), then `$CLAUDE_CONFIG_DIR`/`~/.claude` `agents/`, the first file that exists winning. It reuses `agents.rs`' directory helpers but not `agent_files` itself, whose plugin `agents/` dirs do not apply (a plugin agent loads only as `plugin:name`) and which returns `None` when the plugin list is unreadable. Tests: repo vs user files that disagree; a plugin file vs a user file that disagree (the user file counts). Plugin-namespaced types are skipped; managed and `--agents` definitions are not seen. It reads regular files only, at most 8 KiB, up to the closing `---`; anything else passes. `judge` in guard is pure over the parsed values and the call. It fires when: the definition says `model: inherit`, declares `preferred-model: X`, the call has no `model`, and the prompt has no `model-fallback:` first line (a BOM and leading whitespace trimmed, a trailing `\r` ignored; unit tests for each). Message, through `crate::decision::phrase`, names only greenbelay's own terms. What: `<subagent_type> declares preferred-model: X but this call has no model, so it would run on the session model.` Fix: `Pass model: "X". Only after a model-availability failure, relaunch without model and make the prompt's first line exactly: model-fallback: X -> root (<why X was unavailable>)`. The marker is spelled out in full, with no ellipsis, so the agent can copy it. An explicit `model` of any value passes (a deliberate choice). A missing or unreadable definition passes (no guess).
- **Stance.** Ships `default_stance: Advise`, `max_stance: Deny`, as every new greenbelay rule does; on this Mac it is set to deny with `git config --global greenbelay.agent-preferred-model.stance deny` once installed, since advice alone does not close gap 1.

## Files
- greenharness-skills: `parts/workflow/agents/*.md` (key added), `parts/workflow/skills/agent-model-fallback/SKILL.md` (marker), `tests/test_agent_model_fallback.py` (every agent with a preference says `inherit`; every reviewer declares `preferred-model: opus`; the skill documents the marker), README, CHANGELOG.
- greenbelay, wired like `relais_run_forks`: new `crates/greenbelay-guard/src/rules/agent_preferred_model.rs` (rule, frontmatter line parse between the `---` fences with no new crate, tested on quoted values and CRLF; pure `judge`; unit tests), `rules/mod.rs`, `payload.rs` (`Event::PreAgent`), `settings.rs` matcher `("PreToolUse", Some("Agent|Task"))`, `src/hook.rs` dispatch, `src/rule_table.rs`, `backtest.rs`, `corpus.rs` + `tests/corpus/agent-preferred-model.cases`, `tests/hook.rs`, `docs/rules.md`, CHANGELOG.
- relais: `crates/relais/src/install/mod.rs` `agent_review()` and its tests; README line on the advisory agents, stating that without greenbelay's `agent-preferred-model` rule `relais-review` runs on the session model; CHANGELOG says the same. `relais install` updates the untouched installed file (`plan()` → `Action::Update` when the block's sha is unchanged and the template moved).

## Delivery (order matters)
Board checked: no overlapping work in the three repos. One worktree + PR per repo, each from `origin/main`.
1. **greenharness-skills** first (marker + key): harmless alone. Release, `grh` install; check `~/.claude/agents/implementation-review.md` carries `preferred-model: opus` and an agent with the new key still launches (Claude Code ignores the unknown key).
2. **greenbelay** next (`crates/greenbelay-guard/src/rules/agent_preferred_model.rs`, `crates/greenbelay-guard/src/settings.rs`): before the marker exists, a deny would block legitimate fallbacks. Release, install, `greenbelay install` re-merges the hook matcher; set the stance to deny on this Mac.
3. **relais** last: before the rule, `relais-review` as `inherit` would silently run on Sonnet. Release, preview with `relais install --claude --user`, then apply with `relais install --claude --user --write`; check `~/.claude/agents/relais-review.md` says `inherit` + `preferred-model: opus`. If install prints `keep agents/relais-review.md (owned but modified since install — NOT overwritten)`, diff the file against the template, carry the local edit into the template or drop it, remove the file, preview with `relais install --claude --user`, and apply with `relais install --claude --user --write`; verify the user-level file was recreated with the intended contents. Until then the pinned `model: opus` file stays and the rule passes it.

## Code review
- greenharness-skills: lang:python (proposal said none: no language area, but the Python test helper changes)
- greenbelay: backend, lang:rust, unix, architect (tui left out: the rule's message goes to the agent, not a terminal screen)
- relais: backend, lang:rust (unix, tui, architect left out: one template string and its test change)

## Verification
- greenharness-skills: `scripts/check.sh`; `python3 -I -m unittest discover -s tests`; with one reviewer's `preferred-model:` line removed, `test_agent_model_fallback.py` fails naming that file (expected 1 failure).
  - Observed (phase 1): 20 reviewer definitions carry `preferred-model: opus`, `browser-check` none → suite OK (140 tests), `scripts/check.sh` exit 0; `code-review-tui` key removed → 1 failure `test_every_reviewer_declares_opus` naming `code-review-tui.md`. No CHANGELOG in this repo. `--record-fallback` discoverability is greenbelay's `tests/plan_apply.rs` (phase 2).
- greenbelay: `cargo test` (rule unit tests: inherit+pref+no model → fires; explicit model → passes; marker → passes; pinned definition → passes; missing definition → passes; `relais:relais-reviewer-opus-high` → passes; `Task` alias); `tests/hook.rs` end-to-end on a PreToolUse Agent payload of the real shape (`subagent_type`, `model`, `prompt`, `description`), and the same payload with `tool_name: "Task"` → denied; corpus cases; the backtester sees only Bash (`relais_run_forks.rs`), so instead the pure `judge` runs over the last 14 days of transcripts' `Agent`/`Task` inputs, reported as a count: fires / reviewer launches without `model`, expected equal and 0 on any other agent type.
- relais: `cargo test -p relais --lib install::`.
- Live, after the three installs, in this session: an `Agent` call to `implementation-review` with no `model` is denied with the message, and a relaunch built only from that message's text runs; the same call with `model: "opus"` runs; a call with the `model-fallback:` first line and no `model` runs; an `Agent` call to `relais-review` with no `model` is denied the same way, and with `model: "opus"` it runs on Opus.

## After release (7 days, from transcripts)
- Share of reviewer/planner launches in Sonnet sessions that ran on Opus: target 100% excluding `model-fallback:` launches.
- `agent-preferred-model` denies per 100 reviewer launches: above 20 means the skills do not pass `model`; fix the launcher.
- `agent-preferred-model` lines in `~/.claude/greenbelay/journal.log` and `model-fallback:` prompts, counted.
- Rollback to Advise: any `model-fallback:` launch with no preceding availability error (marker used as a bypass), or a deny that blocks a launch the rule should pass.

## Non-goals
No auto-injection of `model` through `updatedInput` (the deny keeps the launch's model visible in the agent's own record, which `agent-model-fallback` reports, and greenbelay has no input-rewrite path); no change to `browser-check`, the plan-apply helper, the relais runner's pinned reviewer agents, or relais model tiers; no Codex placement change.

## Implementation review
- Phase 1 (greenharness-skills) implementation-review: approve-with-changes → delta approve; 3 fixed (test scope, step 4 wording, all non-reviewers checked); 47k+34k, 46+112 s.
- Phase 1 lang:python: approve-with-changes → delta approve; 4 fixed (helpers, utf-8, messages); 1 low left (anchor assertIn); 35k+23k, 33+29 s.

<!-- panel: repos=greenharness-skills,greenbelay,relais adds= reviewers=architect,backend,language,po,tui,unix,codex body-sha=f4566d37a9d6 -->
