---
canonical: github:fredericrous/decisions/docs/plans/2026-10-29-green-harness-bundle.md
phases: [4]
status: done
branch: feat/initial-content
---
# Green Harness bundle

Pointer. The plan and its review panel live in decisions, with ADR-0050
(harness.skills-source). This repository carries phase 4: the published
skills and agents, stripped of machine-specific content, with the leak and
NOTICE check in CI and a release that uploads an explicit tarball.

## Verification

| Check | Input | Expected | Actual |
|---|---|---|---|
| leak and NOTICE check, source | `scripts/check.sh` | exit 0 | exit 0 |
| leak check catches a planted line | unpacked tree + `mTLS` in README | exit 1 | exit 1 |
| a failed scan never reads clean | missing root | non-zero | exit 1 |
| sweep.py still runs | `python3 sweep.py --help` | usage | usage |

## Implementation review

approve-with-changes in round 1, delta 2 and delta 3 (62k + 77k + 86k). Fixed: anecdotes stripped, leak check case-insensitive with `.netrc` and an explicit allow marker, the release checks the shipped tarball, a failed scan exits 2, dash banners and a dated anecdote removed.
deliberate: Forgejo support in worktree-sweep stays generic and opt-in through `SWEEP_FORGEJO_HOST` (no host baked in); only the host goes in the private overlay, because removing the support would stop the laptop sweeping its own Forgejo repositories.
deliberate: the workflow part also ships interface, accessibility, layout, writing and motion-design, which interface-review loads.
