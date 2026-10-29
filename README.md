# Green Harness skills

The skills and agents that Green Harness parts add to Claude Code. You do not
copy them by hand: `grh install <part>` places the files of the parts you pick
in `~/.claude/skills` and `~/.claude/agents`, and `grh uninstall` takes them
back out.

| Part | Skills | Agents |
|---|---|---|
| decisions | relais-architecture-conflict | — |
| gate | relais-verified-push, merge-when-green, tag-release | — |
| workflow | plan-review, worktree-task, worktree-sweep, diagnosing-bugs, retro, interface-review, interface, accessibility, layout, writing, motion-design | implementation-review, interface-review, 9 plan-review panel agents |

The router part (relais) places its own skill and agents, so it can install
without grh.

Several skills drive harness commands: `plan-review` and `worktree-task` call
guardrails (`amont-agent`) and gate (`amont`), which is why `workflow` needs
both parts.

## Layout

`parts/<part>/skills/<name>/` and `parts/<part>/agents/<name>.md`. A release
is a tarball asset with its `SHA256SUMS`, which grh pins.

## Rules for content

`scripts/check.sh` runs in CI. It fails on anything that belongs to one
machine (private hosts, home paths, private decision ids) and on a forked
skill without its `NOTICE.md`. Keep machine-specific recipes in a local skill
of your own.

## Licence

MIT, see `LICENSE`. Forked skills keep their upstream notice in their own
`NOTICE.md`: jakubkrehel/skills (interface, interface-review, accessibility,
layout, writing), mattpocock/skills (diagnosing-bugs) and LottieFiles
(motion-design); `retro/NOTICE.md` names its own source.
