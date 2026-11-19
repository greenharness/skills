#!/usr/bin/env node
// Runs one headless Playwright check and prints one JSON report on stdout.
// Exit 0: a report (page-step failures are inside it). Exit 2: a runner-side
// failure, the reason on stderr. Exit 130/143: stopped by SIGINT/SIGTERM.
import { spawn, execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const PLAYWRIGHT_VERSION = "1.60.0";
const DEFAULT_TIMEOUT_SECONDS = 120;

class RunnerError extends Error {}

let browser = null;
let npmChild = null;

function parseArguments(argv) {
  const options = { url: null, viewport: "1280x800", steps: null, shots: null, timeoutSeconds: DEFAULT_TIMEOUT_SECONDS };
  const flags = { "--url": "url", "--viewport": "viewport", "--steps": "steps", "--shots": "shots", "--timeout": "timeoutSeconds" };
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    const eq = argument.indexOf("=");
    const flag = argument.startsWith("--") && eq > 0 ? argument.slice(0, eq) : argument;
    const key = flags[flag];
    if (!key) throw new RunnerError(`unknown argument: ${argument}`);
    let value;
    if (flag !== argument) value = argument.slice(eq + 1);
    else {
      index += 1;
      value = argv[index];
    }
    if (value === undefined) throw new RunnerError(`${flag} needs a value`);
    options[key] = value;
  }
  if (!options.url) throw new RunnerError("--url is required");
  const match = /^(\d+)x(\d+)$/.exec(options.viewport);
  if (!match) throw new RunnerError(`--viewport must look like 1280x800, got ${options.viewport}`);
  options.viewportSize = { width: Number(match[1]), height: Number(match[2]) };
  options.timeoutSeconds = Number(options.timeoutSeconds);
  if (!(options.timeoutSeconds > 0)) throw new RunnerError("--timeout must be a positive number of seconds");
  return options;
}

function cacheDirectory() {
  const cacheRoot = process.env.XDG_CACHE_HOME || path.join(os.homedir(), ".cache");
  return path.join(cacheRoot, "browser-check", `playwright-${PLAYWRIGHT_VERSION}`);
}

function installedVersion(directory) {
  try {
    return JSON.parse(fs.readFileSync(path.join(directory, "node_modules", "playwright", "package.json"), "utf8")).version;
  } catch {
    return null; // not installed or unreadable: treated as absent
  }
}

function runChild(command, args) {
  return new Promise((resolve, reject) => {
    // npm and the browser installer write only to stderr: stdout is the report.
    const child = spawn(command, args, { stdio: ["ignore", 2, 2] });
    npmChild = child;
    child.on("error", (error) => reject(new RunnerError(`${command} could not start: ${error.message}`)));
    child.on("close", (code, signal) => {
      npmChild = null;
      if (code === 0) resolve();
      else reject(new RunnerError(`${command} ${args[0] ?? ""} failed (${signal ?? `exit ${code}`})`));
    });
  });
}

async function installPlaywright(target) {
  const parent = path.dirname(target);
  fs.mkdirSync(parent, { recursive: true });
  const temporary = fs.mkdtempSync(path.join(parent, `playwright-${PLAYWRIGHT_VERSION}.tmp-`));
  try {
    await runChild("npm", [
      "install", `playwright@${PLAYWRIGHT_VERSION}`, "--prefix", temporary,
      "--no-save", "--ignore-scripts", "--no-fund", "--no-audit", "--loglevel=error",
    ]);
    if (installedVersion(temporary) !== PLAYWRIGHT_VERSION) {
      throw new RunnerError(`npm did not install playwright@${PLAYWRIGHT_VERSION}`);
    }
    try {
      fs.renameSync(temporary, target);
    } catch (firstError) {
      // Another run may have installed the target meanwhile: keep it when it is the right version.
      if (installedVersion(target) === PLAYWRIGHT_VERSION) {
        fs.rmSync(temporary, { recursive: true, force: true });
        return;
      }
      fs.rmSync(target, { recursive: true, force: true });
      try {
        fs.renameSync(temporary, target);
      } catch (secondError) {
        throw new RunnerError(`could not move the install into place: ${firstError.message}; ${secondError.message}`);
      }
    }
  } finally {
    fs.rmSync(temporary, { recursive: true, force: true });
  }
}

async function loadPlaywright(notes) {
  const target = cacheDirectory();
  if (installedVersion(target) !== PLAYWRIGHT_VERSION) {
    const started = Date.now();
    await installPlaywright(target);
    notes.push(`Playwright installed in ${Math.round((Date.now() - started) / 1000)} s`);
  }
  const require = createRequire(path.join(target, "package.json"));
  try {
    return { playwright: require("playwright"), target };
  } catch (error) {
    throw new RunnerError(`cannot import playwright from ${target}: ${error.message}`);
  }
}

async function launchBrowser({ playwright, target }, notes) {
  const launchOptions = { headless: true, handleSIGINT: false, handleSIGTERM: false, handleSIGHUP: false };
  try {
    return await playwright.chromium.launch(launchOptions);
  } catch (error) {
    if (!/Executable doesn't exist/i.test(String(error.message))) {
      throw new RunnerError(`cannot launch the browser: ${error.message}`);
    }
  }
  const started = Date.now();
  await runChild(process.execPath, [path.join(target, "node_modules", "playwright", "cli.js"), "install", "chromium-headless-shell"]);
  notes.push(`browser downloaded in ${Math.round((Date.now() - started) / 1000)} s`);
  try {
    return await playwright.chromium.launch(launchOptions);
  } catch (error) {
    throw new RunnerError(`cannot launch the browser: ${error.message}`);
  }
}

function shotsDirectory(option) {
  if (option) return path.resolve(option);
  let sha;
  try {
    sha = execFileSync("git", ["rev-parse", "--short", "HEAD"], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
  } catch {
    throw new RunnerError("--shots is required outside a git repository"); // git failed: no sha to file under
  }
  return path.join(os.homedir(), ".claude", "greenbelay", "attestations", sha);
}

function withDeadline(pending, seconds) {
  let timer;
  const deadline = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(`timed out after ${seconds} s`)), seconds * 1000);
  });
  pending.catch(() => {}); // a step still running after the deadline is torn down with the browser; its late error is not news
  return Promise.race([pending, deadline]).finally(() => clearTimeout(timer));
}

async function check(options, notes) {
  const loaded = await loadPlaywright(notes);
  browser = await launchBrowser(loaded, notes);
  const report = {
    url: options.url,
    viewport: options.viewport,
    title: null,
    result: null,
    navigationError: null,
    stepsError: null,
    console: [],
    pageErrors: [],
    failedRequests: [],
    httpErrors: [],
    shots: [],
    notes,
  };
  const context = await browser.newContext({ viewport: options.viewportSize });
  const page = await context.newPage();
  page.on("console", (message) => report.console.push({ type: message.type(), text: message.text() }));
  page.on("pageerror", (error) => report.pageErrors.push(String(error && error.stack ? error.stack : error)));
  page.on("requestfailed", (request) =>
    report.failedRequests.push({ method: request.method(), url: request.url(), failure: request.failure()?.errorText ?? "" }));
  page.on("response", (response) => {
    if (response.status() >= 400) {
      report.httpErrors.push({ method: response.request().method(), url: response.url(), status: response.status() });
    }
  });

  const shot = (name) => {
    const directory = shotsDirectory(options.shots);
    fs.mkdirSync(directory, { recursive: true });
    const file = path.join(directory, name);
    report.shots.push(file);
    return file;
  };

  const run = async () => {
    try {
      await page.goto(options.url, { waitUntil: "load" });
      await page.waitForLoadState("networkidle", { timeout: 5000 }).catch(() => {}); // a page that never idles is still reported as loaded
    } catch (error) {
      report.navigationError = String(error.message);
      return;
    }
    if (options.steps) {
      const steps = await import(pathToFileURL(path.resolve(options.steps)).href);
      report.result = (await steps.default(page, { shot })) ?? null;
    }
  };
  try {
    await withDeadline(run(), options.timeoutSeconds);
  } catch (error) {
    report.stepsError = String(error && error.stack ? error.stack : error);
  }
  report.url = page.url();
  try {
    report.title = await page.title();
  } catch {
    report.title = null; // the page may be gone after a failed step
  }
  return report;
}

async function stopOnSignal(name, code) {
  process.stderr.write(`${name}: closing the browser\n`);
  if (npmChild) npmChild.kill("SIGTERM");
  try {
    if (browser) await browser.close();
  } catch (error) {
    process.stderr.write(`close failed: ${error.message}\n`);
  }
  process.exit(code);
}

async function main() {
  const options = parseArguments(process.argv.slice(2));
  process.on("SIGINT", () => void stopOnSignal("SIGINT", 130));
  process.on("SIGTERM", () => void stopOnSignal("SIGTERM", 143));
  const notes = [];
  let report;
  try {
    report = await check(options, notes);
  } finally {
    if (browser) {
      try {
        await browser.close();
      } catch (error) {
        process.stderr.write(`close failed: ${error.message}\n`);
      }
    }
  }
  process.stdout.write(`${JSON.stringify(report)}\n`);
}

main().catch((error) => {
  process.stderr.write(`browser-check-runner: ${error && error.message ? error.message : error}\n`);
  process.exitCode = 2;
});
