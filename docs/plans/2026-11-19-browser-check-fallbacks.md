---
status: active
branch: feat/browser-check-fallbacks
repos: [greenharness-skills, grh]
programme: none
adrs: []
plan-id: p-01M7T7NBE88FGVA0M9RH7SCZEE
---
# browser-check falls back to Playwright, then Claude in Chrome

## Review panel

👉 **Decide:** none — approve if fixing the cold start (pre-step) plus a committed runner beats more agent prose. Both open decisions are settled in the body: grh release yes, allow entries in the pre-step.
📍 greenharness-skills, grh, dotfiles · 3 phases · 2 releases · next: the pre-step. Panel: backend, lang:python, lang:typescript, tui, unix (opus-5-5), codex.
**Changed by review:** the cold start fixed at its source; Playwright boilerplate in a committed, tested runner; proof (b) really fails Playwright.
**Verdicts:** person's delta: python approve, typescript approve, backend approve-with-changes (1 blocking, fixed); 20 carried; words 1199 → 1940 (×1.62: the runner spec and fixes to wrong statements; the person asked for the change); remove 0, merge 0.
📄 Full reviews: [2026-11-19-browser-check-fallbacks.reviews.md](2026-11-19-browser-check-fallbacks.reviews.md)

## Picture

```
 browser-check, one check
   |
   v
 chrome-devtools tools present, first call answers? --yes--> today
   | no (tools absent, or a connection error)
   v
 Playwright 1.60.0 via the committed run.mjs  --ok--> same report
 (the agent writes only a steps module; headless, fresh profile)
   | no (node missing, install or launch fails)
   v
 URL served from this machine (localhost, 127.0.0.1, [::1])?
   | yes                                   | no
   v                                       v
 Claude in Chrome: a new tab in the      `not checked: no browser
 person's Chrome, closed afterwards       available` + each failure
   |
   v
 report: `browser: <chrome-devtools | playwright | claude-in-chrome>`
```

The picture shows the order the agent tries browsers in, and where a
non-local page stops instead of reaching the person's Chrome.

## Context

On 2026-11-19 a happier S5a side-by-side check stopped before it captured
anything. chrome-devtools MCP had timed out at session start (30 s connect limit;
a cold `npx chrome-devtools-mcp@1.13.0` start ran longer than that), a session
cannot reconnect it, and `browser-check` (`parts/workflow/agents/browser-check.md`)
knows no other browser. So the gate "web/UI work is done when the rendered result
is checked in a real browser" blocked on a connection failure, not on the page.

The person chose (2026-11-19):
- Playwright through a **Bash script** (not a second MCP server, which starts
  through npx too and can hit the same timeout);
- **Claude in Chrome** as the last fallback, **only for pages served from this
  machine**, because it drives the person's real profile and logins.

## Non-goals

- A Playwright MCP server, or Claude in Chrome for non-local pages (the person
  chose against both, 2026-11-19).

## Change (one commit, skill text and one test)

`parts/workflow/agents/browser-check.md`:
1. `description`: "Drives a real browser (Chrome DevTools; else Playwright; else
   Claude in Chrome for a local page) …".
2. `tools`: keep the chrome-devtools list; add the Claude in Chrome tools
   (`mcp__claude-in-chrome__tabs_context_mcp`, `tabs_create_mcp`, `navigate`,
   `read_page`, `get_page_text`, `find`, `form_input`, `computer`,
   `javascript_tool`, `read_console_messages`, `read_network_requests`,
   `resize_window`). Playwright needs only `Bash`, already listed.
3. A new section **Which browser**, before *How to work*:
   - chrome-devtools first. Fall back when no `mcp__chrome-devtools__*` tool is in
     the tool list, or the first call fails with a connection error (not when a
     page step fails: that is a finding, reported as today).
   - Playwright: the agent runs the committed runner (below) with Bash:
     `node ~/.claude/skills/browser-check-runner/run.mjs --url <u> --viewport
     <w>x<h> [--steps <file.mjs>] [--shots <dir>]` (Bash `timeout` 600000 for a
     first install). The agent writes only the steps module, `export default
     async (page) => <result>`, using role and name locators; everything else is
     the runner's. Exit 0: one JSON report on stdout (page-step failures inside
     it; a steps module that fails to import, throws or passes its timeout is a
     page-step failure inside the JSON, exit 0). Exit 2: any runner-side failure
     (install, browser download, Playwright import, launch, or an uncaught runner
     error: the top level maps it to 2), the reason on stderr; npm and the steps
     module write only to stderr. Any non-zero exit with no JSON on stdout is
     "Playwright failed" and moves to the next browser.
   - Claude in Chrome: only when Playwright failed and the parsed URL hostname equals exactly
     `localhost`, `127.0.0.1` or `[::1]` (what `new URL().hostname` returns;
     `localhost.evil.com` and
     `127.0.0.1@evil.com` are refused; the test pins this). Open a new tab (`tabs_create_mcp`),
     never read or touch the person's other tabs, close the tab at the end. After each
     navigation, check the tab's hostname again: not local (a redirect) means
     close the tab and report it under `not checked`. Any other host: stop with
     `not checked: no browser available. chrome-devtools: <err>; playwright:
     <err>. Next: restart the session to reconnect chrome-devtools, or serve the
     page on localhost.`
     Screenshots there go through its own tool; report it under `not checked` if a
     brief needs a file it cannot save.
4. *How to work*: the existing steps become "with chrome-devtools"; the
   Playwright and Claude in Chrome paths keep the same order (viewport → text
   first → screenshots only when asked → console and network once → close).
5. The browser rule ("headless and isolated") gains: except Claude in Chrome,
   which runs in the person's profile; say so in the report.
6. *What you report*: a new first line, before `url:`, `browser: <chrome-devtools
   | playwright | claude-in-chrome>   profile: <isolated | your Chrome
   (logged-in)>`; `not checked` names each fallback that failed with its error
   (one line each, the error cut to 120 characters).

`parts/workflow/skills/browser-check-runner/` (new; `SKILL.md` with
`disable-model-invocation: true`, like `agent-model-fallback`, plus `run.mjs`,
stdlib Node only). The boilerplate the panel found bugs in is written and
proven once here instead of re-authored by the agent on each run:
- installs pinned `playwright@1.60.0` (chromium-1223 is cached; the headless shell, `chromium_headless_shell-1223`, may download once) into
  `${XDG_CACHE_HOME:-~/.cache}/browser-check/playwright-1.60.0` when its
  `node_modules/playwright/package.json` does not read 1.60.0: `npm install
  --no-save --ignore-scripts --no-fund --no-audit --loglevel=error` into an
  `fs.mkdtemp` sibling (parent created first, npm given `--prefix <tmp>`), then
  `fs.rename`; on failure the target's `package.json` is re-read with the temp
  copy still in place: at 1.60.0 the temp copy is removed and the target used,
  otherwise the target is removed and the rename retried once (the temp copy is
  removed if that retry fails too); runs `playwright
  install chromium-headless-shell` when the browser is missing; reports
  `note: Playwright installed in <n> s`;
- imports Playwright through `createRequire(<cache dir>/package.json)` and the steps module through `pathToFileURL(path.resolve(file))`, launches headless with a fresh context,
  sets the viewport, collects `console`, `pageerror`, `requestfailed` and HTTP
  responses ≥ 400 (method, URL, status) from the start;
- runs the steps module under try/catch and a timeout, writes screenshots to
  `--shots` (default `~/.claude/greenbelay/attestations/<sha>/`, `<sha>` =
  `git rev-parse --short HEAD` in the cwd, `--shots` required outside a
  repository, created first), prints one JSON
  object, closes the browser in `finally` and on SIGINT/SIGTERM (exit 130/143), launching with `handleSIGINT`, `handleSIGTERM` and `handleSIGHUP` false so only the runner's handler acts (it also kills a running npm child).

`tests/test_browser_check.py` (new, stdlib unittest like the other tests):
`node --check` on `run.mjs` when `node` is on PATH; runner behaviour tests: with empty `XDG_CACHE_HOME`/`npm_config_cache` and `npm_config_offline=true`, `run.mjs --url http://127.0.0.1:1` exits 2 with empty stdout, ENOTCACHED on stderr and no `.tmp` sibling left; and, skipped visibly (`skipTest`) when the Playwright cache lacks 1.60.0, a `http.server` page that logs a console error, throws and fetches a 500 yields all three in the JSON with exit 0;
pins the contract text: the fallback order appears in that order inside the `## Which browser` section (sliced by heading, since the description names the browsers too), every `playwright@<v>` match equals `1.60.0`, the 12 named
`mcp__claude-in-chrome__` tools are listed once each (tools line split on
commas), the report block's first line starts with `browser:`, the three exact
local hostnames and a refused lookalike are named, and the frontmatter keeps
`model: inherit`.

Not changed: `worktree-task` and `create-verify-skill` (they launch the agent;
the fallback is inside it); worktree-task's rule that the person's page opens
through `greenbelay open`, never chrome-devtools or Playwright, stands.

## Phases

Before Phase 1, remove the trigger (machine config outside these two repos; the chezmoi template change goes as one
dotfiles PR; the MCP entry in the user config and the chezmoi settings template, the
laptop edited first):
  `npm install -g chrome-devtools-mcp@1.13.0`, the server's `command` set to
  the installed `chrome-devtools-mcp` binary instead of `npx -y` (no package
  resolve at each session start), and `MCP_TIMEOUT=60000` in the settings
  `env`. Also there: the allow entries for the Claude in Chrome tools the agent
  lists (8 missing today). Done when a fresh session lists `chrome-devtools`
  connected.
- [x] Phase 1 (proof (b) open, see Verification) — the agent text, its runner and its test, 1 PR in
  greenharness-skills (worktree from `origin/main`, the plan landed as
  `docs/plans/2026-11-19-browser-check-fallbacks.md`):
  `parts/workflow/agents/browser-check.md`,
  `parts/workflow/skills/browser-check-runner/SKILL.md`,
  `parts/workflow/skills/browser-check-runner/run.mjs`,
  `tests/test_browser_check.py`.
  RED: the new test fails on today's agent; GREEN after the edit;
  `scripts/check.sh` exits 0; `python3 -m unittest discover tests` passes.
  Before the PR, the live proof, each path once, with the branch's agent and
  runner copied over the installed ones (the old copies kept aside and
  restored after; first confirm the running session loaded the new
  definition, else restart it) and the chrome-devtools server disabled for
  the session, so its tools are really absent (the shipped trigger, no brief
  override): (a) the runner alone on a throwaway local page that logs a
  console error, throws an uncaught error and fetches a 500: the JSON lists
  all three, exit 0; then the agent on happier's apps/web build (port 8095):
  `browser: playwright`, heading, line count, console count for `/settings`;
  (b) Playwright made to fail (`XDG_CACHE_HOME` and `npm_config_cache` set to
  empty `mktemp -d` directories with `npm_config_offline=true`, so the
  install fails with ENOTCACHED): `browser: claude-in-chrome` for the same
  page, its tab closed afterwards, the tab count unchanged; (c) a non-local
  URL with Playwright failing the same way: `not checked: no browser
  available`. (d) chrome-devtools itself, connected after the pre-step:
  `browser: chrome-devtools`. Then implementation review (F4b), PR, merge with
  merge-when-green.
- [x] Phase 2 — release and pin: a greenharness-skills release with
  tag-release (the next free minor; `v0.17.0` is the latest tag), then the pin
  in grh `catalog.toml` (`skills_version`, `skills_sha256`; it pins 0.16.0
  today) and `browser-check-runner` added to the workflow part's `skills`, 1
  PR in grh; then a grh patch release with tag-release (the catalog is
  compiled into the binary, so only a release keeps a later plain
  `grh install` from restoring the old agent), the released grh installed,
  and `grh install workflow`, so `~/.claude/agents/browser-check.md` and the
  runner are the released text (today's installed agent is older:
  `model: haiku`, no Catches line).
- [ ] Phase 3 — resume happier S5a step 1 with the new agent: no file in this
  plan (`docs/plans/2026-10-26-m3-shared-routes.md` in happier gets its
  Verification row there).

## Code review
- greenharness-skills: backend, lang:python, lang:typescript (the runner is Node)
- dotfiles: none — a settings-template edit (`command`, `MCP_TIMEOUT`, allow entries), no code; the pre-step's check is a fresh session listing chrome-devtools connected
- grh: none — a version and checksum bump plus one `skills` entry in `catalog.toml`, and a patch release (backend, lang:python, unix, tui left out: no code or command-line output changes)

## Verification

Phase 1 observed on 2026-11-19, tree 7ea5489 (the runner and test rows), and the agent proofs on 93e2bb2's agent text, which the fix commits left unchanged.

| Input | Expected | Actual |
|---|---|---|
| `python3 -m unittest discover tests` | the new test RED before the edit, all GREEN after | `tests/test_browser_check.py` absent on the base (RED by absence); 16/16 browser-check tests ran with no skip on this machine, full suite OK. On CI the two page tests skip with a printed reason (empty browser cache) |
| `scripts/check.sh` | exit 0 (no machine paths: the cache dir is `$XDG_CACHE_HOME`/`$HOME` based) | exit 0 |
| fresh session after the pre-step | `chrome-devtools` connected, no timeout | `claude mcp list` from a fresh process: `chrome-devtools: … ✔ Connected`, 4.3 s for every server (global `chrome-devtools-mcp@1.13.0`, `MCP_TIMEOUT=60000`, dotfiles#70) |
| runner on the throwaway page | console error, uncaught error and the 500 in its JSON, exit 0; no Chromium process left | `console` 2 (the error and the 500's resource line), `pageErrors` 1, `httpErrors` 1 (`GET /boom 500`), exit 0; cold run 9.7 s (`Playwright installed in 2 s`, `browser downloaded in 7 s`); after the exit `pgrep -f chromium_headless_shell-1223` counted 0 |
| `kill -TERM` mid-run (a 30 s steps module) | exit 143, no Chromium left, stdout empty | 4 Chromium processes before, exit 143, 0 after, 0 bytes on stdout (twice: on 93e2bb2 and on 7ea5489) |
| live (a) playwright | `browser: playwright`, measured heading and lines, console count, browser closed | `browser: playwright   profile: isolated`; heading "Happier", 4 lines (the sign-in screen: that origin has no session), 0 console errors, 0 HTTP ≥ 400. Run in a fresh headless `claude -p` with no MCP server, because a running session keeps the agent text it loaded at start |
| live (b) claude-in-chrome | `browser: claude-in-chrome`, tab opened and closed, Playwright's failure under `not checked` | **not verified.** The chain reached the step and reported cleanly (Playwright: exit 2, ENOTCACHED; Claude in Chrome tools absent), but `mcp__claude-in-chrome__*` tools load neither in this session nor in `claude -p --chrome`; the native host running belongs to the Claude desktop app. Open check, owner: the agent, in the next interactive Claude Code session with the extension connected, by 2026-11-26 |
| live (c) non-local URL | `not checked: no browser available`, both failures listed | `https://example.com/`: both failures named, Claude in Chrome not tried (not a local host), no temp install left in the cache |
| live (d) chrome-devtools | `browser: chrome-devtools` | `browser: chrome-devtools   profile: isolated`; the same heading and 4 lines as (a), 33 requests all 200/204 |
| installed copies, after `grh install workflow` from the released grh | `diff` of the installed agent and runner against the released files: empty | skills v0.18.0 (release run success; tarball matched `SHA256SUMS` 71d88f4b…; it holds the runner and the new agent text), grh#57 merged, grh v0.14.0 released (5 archives, the tap bumped itself), `brew upgrade` → grh 0.14.0, `grh install workflow -y --replace`: `diff` of the installed agent, `run.mjs` and `SKILL.md` against the release: empty, all three |

## Risks

- A Claude in Chrome tool name in the list that does not exist is ignored by the
  harness, so a wrong name fails quietly: live proof (b) is the check.
- Claude in Chrome needs Chrome open with the extension connected; when it is not,
  the agent reports `claude-in-chrome: extension not connected (open Chrome, then
  retry)` under `not checked`, which is today's outcome.
- Playwright's first install downloads the package (and Chromium if the cache
  lacks it): a first fallback can take minutes; the runner's `note:` line says so.
- `MCP_TIMEOUT` is read by Claude Code at startup; if a fresh session still
  times out, the global binary alone is the fix and the row says which.

## Decision log

- 2026-11-19: grh already pinned skills 0.17.0 (grh#56, after the plan was written from a stale checkout); Phase 2 bumps it from there.
- 2026-11-19: the agent proofs ran in fresh headless `claude -p` sessions (`--strict-mcp-config` with an empty MCP config for real chrome-devtools absence), since a running session does not reload agent definitions.
- 2026-11-19: proof (b) could not drive Claude in Chrome here; Phase 1 closes with it as a dated open check rather than holding the runner, which (a), (c) and (d) prove.
- 2026-11-19: grh released as 0.14.0, a minor rather than the planned patch, because the workflow part gains a skill.
- 2026-11-19: the installed `browser-check.md` was a hand-placed copy grh did not own (`model: haiku`, older text), so `grh install` skipped it; `--replace` took it over, with grh's backup under `~/.local/state/grh/backup/1795112794/`.

## Implementation review

- implementation-review: approve-with-changes ×3 (47k + 40k + 35k, 44 + 57 + 52 s). Fixed: steps output off stdout, test pins (ENOTCACHED, `127.0.0.1@evil.com`), launch failure during stop logged, run-wide fault handlers. Deliberate: a fault after the report is printed, a fault before a report skipping cleanup (both low, filed as a follow-up).
- backend: approve-with-changes ×3 (46k + 38k + 31k, 69 + 55 + 43 s). Fixed: title deadline, temp dir on a signal, existing shots only, stale target renamed aside, npm close awaited. Deliberate: a `.stale-<pid>` left by a crash mid-rename; hung-title and missing-shot tests (low, follow-up).
- lang:python: approve-with-changes, approve-with-changes, approve (34k + 28k + 25k). Fixed: timeouts, temp env helper, `setUpClass`, the exists guard. Deliberate: frontmatter split (repository's pattern), `offline_environment` as a class.
- lang:typescript: approve-with-changes, approve (34k + 28k). Fixed: signals vs Playwright's own handlers, parseArgs, bounded timeout, unserialisable result, RunnerError cause.

<!-- panel: repos=greenharness-skills,grh adds=lang:typescript reviewers=backend,lang:python,lang:typescript,tui,unix,codex body-sha=24cb6fb1986c -->
