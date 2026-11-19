# browser-check falls back to Playwright, then Claude in Chrome: reviews


Round 1 (all opus-5-5): tui approve-with-changes (6 findings, 28k, 20 s); lang:python approve-with-changes (6, 32k, 37 s); unix approve-with-changes (4, 29k, 35 s); backend approve-with-changes (5, 33k, 53 s). Accepted: tui 1, 2, 3, 5, 6; python 2, 4, 5, 6; unix 1, 3, 4; backend 1–4. Rejected: tui 4 (covered by the `profile:` field), python 1 and unix 2 (duplicates of backend 1), python 3 (duplicate of tui 5 and backend 3), backend 5 (no merge: Phase 2 tags, Phase 3 is another repo).

Round 2: tui approve (33k, 17 s); lang:python approve-with-changes (38k, 17 s); unix approve-with-changes (44k, 41 s); backend approve-with-changes (38k, 24 s). Codex final (gpt, high effort): approve-with-changes, 1 high applied (grh compiles its catalog: install from the merged checkout), 1 medium carried. Backend delta on that edit: approve-with-changes (43k, 22 s), 1 medium → decision (1).

Carried into implementation:
- Install, rename and run happen inside `run.mjs` (mkdtemp + fs.rename, no `$$`); the stale-target retry is in the Change section (python, backend, unix).
- A failed install or browser download counts as "Playwright failed" (python).
- The local IPv6 hostname is `[::1]` with brackets, as `new URL().hostname` returns; the picture gets the `profile:` field (unix, backend).
- A SIGINT/SIGTERM handler closes Chromium, exit 130/143 (unix).
- Phase 1 says the allow entries come first and (c) fails Playwright like (b) (backend).
- The installed-copy row is a `diff` against the released file (backend).
- A redirect report names the host only and the tab closes at once; the Risks install line points at the `note:` line (tui).
- Playwright also collects `pageerror` and HTTP responses ≥ 400 (method, URL, status); proof (a) includes one of each (codex).
- Decision (2), the allow entries, is a permission change (unix 7): settled, in the pre-step.
- Person's delta ("quality without sacrifice"): the pre-step fixes the cold start; the Playwright boilerplate is a committed runner. Seats: backend, lang:python, lang:typescript (new seat), ≈ 290k tokens over two passes. Fixed: the runner's exit contract, signal handlers, ESM imports, stale-install retry (a blocking bug in the merged text, fixed). Rejected: `dotfiles` in `repos` (seats reviewers for a three-line template edit).
- Carried from it: the page test's skip checks the install dir and `chromium_headless_shell-1223`, never downloads; a SIGTERM unittest under the same skip (optional); the runner tests skip when `node` or `npm` is missing; `--timeout <s>`, default 120; the page test runs locally and in proof (a), not on CI (empty browser cache).

