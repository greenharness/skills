---
status: active
branch: fix/agent-model-fallback
repos: [greenharness-skills]
adrs: []
---
# Durable agent model fallback

## Review panel
📄 Full reviews: [reference](2026-11-04-durable-agent-model-fallback.reviews.md).
⚠ unreviewed: the person explicitly waived the unavailable panel for this fallback-skills prerequisite only.
📍 greenharness-skills · source-managed fix planned · next: implement and verify bounded root-model fallback.
**Verdicts:** none; all original panel launches failed. This waiver does not cover the deferred Qwen serving plan.

## Context
The required Qwen plan reviewers could not start: their pinned Opus model and the Sonnet retry both returned Claude-provider cooldown/rate-limit errors. The root session uses a different, working model. The person requested a permanent fallback for reviewers and other skills declaring models, not a one-time workaround, and waived the unavailable plan panel only for this prerequisite.

Keep model preferences without making them availability dependencies. Preserve named expert roles, independent reviews, tools, permissions and plan/tree/profile bindings. Work directly in this session, without relais, as requested. No serving, credentials or client-profile changes belong to this approval.

## Recommended approach
Implement in `greenharness-skills`; do not add a router to `amont-agent`. Existing review binding checks the named agent role, not a fixed model. The supported mechanism is:

1. First-party agent definitions use `model: inherit` as their safe default. Preserve their intended preferred model in launch guidance.
2. Launching skills explicitly supply the preferred `Agent.model` for the initial attempt.
3. On a classified model-availability failure, launch the **same named agent** once without a model override. Its definition inherits the root session model, including custom provider IDs that the Agent override enum cannot express.
4. Retain exactly the prompt, language/profile, tool restrictions, bindings and output contract. Record requested/effective models and fallback reason. Only a completed bound review counts.

Do not use a generic or fork agent as a substitute reviewer. Omitting an override is not fallback if that agent's definition still pins a model: audit definitions and tests together.

Claude Code's built-in `fallbackModel` chain is insufficient for this incident: its documented exclusions include rate-limit errors, and it does not document a dynamic root-model reference. Do not change the root session's model or global fallback settings.

## Bounded failure policy
- Permit fallback for explicit model-not-found/unsupported-model/unavailable responses and provider cooldown or transient rate-limit/capacity failures. Match the actual failure category, not any occurrence of a model name or HTTP error.
- Do not fallback on invalid request/context overflow, authentication, billing/quota exhaustion, policy denials, permission errors, ordinary reviewer findings, or successfully completed work. Ambiguous failures remain errors, not permission to switch providers.
- At most one fallback launch for each affected task. If root equals the failed model, cannot be resolved/used under policy, or also fails, report the blocker. No Opus → Sonnet → Haiku ladder and no replay of completed side effects.
- Reuse a positively identified model/provider cooldown within the current skill invocation, so subsequent seats do not all probe the same known-failing scope. Do not infer that all models share a cooldown from a model-specific error. No durable blacklist or invented recovery interval.
- Keep optional independent cross-vendor reviews distinct; never relabel them as successful named panel seats. No automatic paid escalation or changes to credential/model authorization.

## Source changes
- `parts/workflow/agents/*.md`: update the first-party pinned definitions to inherited defaults, preserving their role prompts, tools and preferred launch model. Include plan reviewers, implementation/profile reviewers and interface review.
- `parts/workflow/skills/plan-review/SKILL.md`: explicit preferred launch, bounded inherited fallback, invocation-local cooldown reuse, truthful model reporting, and replacement of the same-unavailable-model retry rule.
- `parts/workflow/skills/worktree-task/SKILL.md`: apply the same policy to implementation and declared code-review profiles.
- Audit other published skills for explicit model calls, including the plan-application helper, and apply the same policy where relevant. Do not patch unrelated bundled or third-party skills.
- Keep the canonical policy in one installed workflow reference, with concise references from launchers; do not copy divergent retry recipes. Update README and focused tests under `tests/`.

## Implementation and delivery
1. Fresh board/fetch check; create a per-task worktree from origin/main. Preserve unrelated work. Commit this approved prerequisite plan first.
2. Implement canonical policy, agent defaults and skill launch instructions together; add regression fixtures before claiming the failure fixed.
3. Verify source and real named-agent inheritance using controlled, credential-free local fixtures. Do not run a nine-seat paid probe to test availability.
4. Bootstrap the updated source-managed agent definitions through a supported, ownership-preserving installation path so independent implementation reviewers can inherit this working root model. Do not hand-patch unrelated installed guidance or overwrite user-owned agents. Verify installed content against source, preserve a rollback, and stop if no safe supported bootstrap path is available.
5. Run independent implementation/profile reviews with actual bound evidence, repository checks and CI. Land through a PR; release and install the workflow guidance through the normal managed path. Verify the installed versions/content and one real failed-preference → root-fallback review.
6. Resume the deferred Qwen serving plan with the full required panel using the durable fallback. This prerequisite's waiver does not authorize skipping that panel or deploying any serving configuration.

## Non-goals
No LiteLLM/llama.cpp/KV/cache/deadline changes, Qwen profile installation, secret or credential changes, CLIProxy fork, new model router, broad `amont-agent` changes, review-role aliases, forced global subagent model, disabled hooks, or weakened review requirements. No unrelated tool release.

## Code review
- greenharness-skills: backend, lang:python, unix

Python covers regression tests and Unix covers launch/environment semantics. Other implementation profiles are omitted because this prerequisite changes guidance and its focused tests, not a service, interface or new language implementation.

## Verification
Observed on branch `fix/agent-model-fallback` (62 tests, `scripts/check.sh` clean; helper also run under system Python 3.9.6).
- Preferred model succeeds → no fallback call exists; `decide` is only run on a failure. Observed: launchers carry `model: "opus"` (tests).
- Preference unavailable/cooldown → `decide` exits 0 `fallback`, relaunch with no `model`. Observed: `Decide`, `Cli` tests. Effective custom root model: **deferred**, `holds-until:` first real fallback review after the managed install.
- Still-pinned definition → `pinned_models` helper; `test_no_agent_pins_a_model` covers all 18 agents. Observed.
- Shared cooldown → only `classify` = `cooldown` asks the launcher to note the model; other models and new invocations are unaffected because the helper keeps no state. Observed: `test_only_a_cooldown_asks_to_note_the_model`.
- Root equals failed, `--used 1`, excluded or ambiguous error → exit 1 `report`. Observed: `Decide`, `Cli`.
- Real CLI/named-agent fixture → **not run**; `holds-until:` the first real fallback review after install.
- Repository checks → `scripts/check.sh` exit 0 (25 checks); `python3 -I -m unittest discover -s tests`: Ran 62 tests, OK. CI conclusion and remote merged SHA: **pending**, next phase (land).
- Managed installation → **pending**, next phase (release, install, one real failed-preference → root-fallback review).

## Implementation review
- implementation-review: approve-with-changes; 4 round-1 findings fixed, delta ruled the print candidates fine; the unrun runtime fixture is named above (deferred); about 50k tokens.
- backend: approve-with-changes; plan-apply relaunch guard and `--used` bounds fixed; delta found step 3 wording, fixed.
- lang:python: approve-with-changes; pure `decide`, typed Literals, shared helper; low items fixed.
- unix: approve-with-changes; heredoc examples, exit codes, Python 3.9 import crash fixed.

## Deferred Qwen work
The original serving investigation and draft remain recorded in this session. After this prerequisite, restore that draft as its own plan: two fixed 200K total-context slots with measured FP16 KV/memory headroom; whole-stream shared admission; bounded FIFO/deadlines and no nested retries; source-managed client controls; measured warm-prefix TTFT; security-preserving GitOps rollout. No part of that serving work is approved by this prerequisite plan.


<!-- panel: repos=greenharness-skills adds=cli reviewers=none body-sha=c2f1b36f9ecc -->
