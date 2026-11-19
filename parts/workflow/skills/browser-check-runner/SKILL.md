---
name: browser-check-runner
description: The Playwright fallback of the browser-check agent: one committed Node runner that installs a pinned Playwright, loads a page headless and prints one JSON report. Read by browser-check; not invoked on its own.
disable-model-invocation: true
---

# browser-check-runner

`run.mjs` is the second browser `browser-check` tries, when chrome-devtools
is absent or cannot connect. It needs only `node` and `npm`.

```sh
node ~/.claude/skills/browser-check-runner/run.mjs --url <url> \
  --viewport <w>x<h> [--steps <file.mjs>] [--shots <dir>] [--timeout <s>]
```

Give the Bash call a `timeout` of 600000: a first run installs
`playwright@1.60.0` into `${XDG_CACHE_HOME:-~/.cache}/browser-check/` and may
download the headless shell once. The JSON then carries a `notes` line saying
how long that took.

## Steps module

The agent writes only this file:

```js
export default async (page, { shot }) => {
  await page.getByRole("heading").first().waitFor();
  await page.screenshot({ path: shot("settings-1280.png") });
  return { heading: await page.getByRole("heading").first().innerText() };
};
```

Use role and name locators. `shot(name)` returns an absolute path in the
`--shots` directory (default `~/.claude/greenbelay/attestations/<sha>/`, with
`<sha>` from `git rev-parse --short HEAD`; `--shots` is required outside a
repository). What the function returns is the report's `result`.

## Exit status and output

- 0: one JSON object on stdout and nothing else: `url`, `viewport`, `title`,
  `result`, `navigationError`, `stepsError`, `console`, `pageErrors`,
  `failedRequests`, `httpErrors` (status 400 and up), `shots`, `notes`. A
  steps module that fails to import, throws, rejects without a handler,
  returns a result JSON cannot serialise, or passes `--timeout` (default
  120 s) is a `stepsError` inside the report, still exit 0. `console.log`,
  `console.info` and `console.debug` in a steps module go to stderr, so
  stdout stays the one JSON report. `shots` lists only files that exist.
- 2: any runner-side failure (bad or unknown arguments, install, browser download,
  import, launch); the reason is on stderr. Treat it as "Playwright failed".
- 130 / 143: stopped by SIGINT / SIGTERM; the browser and a running npm are
  closed first, and an unfinished install directory is removed.
