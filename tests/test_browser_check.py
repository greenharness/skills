"""browser-check falls back to Playwright, then Claude in Chrome (local pages only)."""
import http.server
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENT = ROOT / "parts/workflow/agents/browser-check.md"
RUNNER_DIR = ROOT / "parts/workflow/skills/browser-check-runner"
RUNNER = RUNNER_DIR / "run.mjs"
SKILL = RUNNER_DIR / "SKILL.md"

PLAYWRIGHT_VERSION = "1.60.0"
HEADLESS_SHELL = "chromium_headless_shell-1223"
CHROME_TOOLS = [
    "tabs_context_mcp", "tabs_create_mcp", "navigate", "read_page", "get_page_text",
    "find", "form_input", "computer", "javascript_tool", "read_console_messages",
    "read_network_requests", "resize_window",
]


def frontmatter(text):
    return text.split("---")[1]


def which_browser_section(text):
    start = text.index("## Which browser")
    return text[start:text.index("\n## ", start + 1)]


class AgentText(unittest.TestCase):
    text = AGENT.read_text()

    def test_fallback_order_inside_the_section(self):
        section = which_browser_section(self.text)
        positions = [section.index(name) for name in ("chrome-devtools", "Playwright", "Claude in Chrome")]
        self.assertEqual(positions, sorted(positions))

    def test_which_browser_precedes_how_to_work(self):
        self.assertLess(self.text.index("## Which browser"), self.text.index("## How to work"))

    def test_every_playwright_pin_is_the_runner_version(self):
        for text in (self.text, SKILL.read_text(), RUNNER.read_text()):
            self.assertEqual(set(re.findall(r"playwright@([\w.\-]+)", text)) - {PLAYWRIGHT_VERSION, "${PLAYWRIGHT_VERSION}"}, set())
        self.assertIn("playwright@" + PLAYWRIGHT_VERSION, self.text)
        self.assertIn(f'PLAYWRIGHT_VERSION = "{PLAYWRIGHT_VERSION}"', RUNNER.read_text())

    def test_claude_in_chrome_tools_listed_once_each(self):
        tools_line = next(l for l in frontmatter(self.text).splitlines() if l.startswith("tools:"))
        tools = [t.strip() for t in tools_line[len("tools:"):].split(",")]
        chrome = [t for t in tools if t.startswith("mcp__claude-in-chrome__")]
        self.assertEqual(sorted(chrome), sorted("mcp__claude-in-chrome__" + n for n in CHROME_TOOLS))
        self.assertIn("Bash", tools)

    def test_report_block_starts_with_browser(self):
        block = re.search(r"## What you report\n\nA short block, no prose around it:\n\n```\n(.*?)```", self.text, re.S)
        self.assertTrue(block)
        self.assertTrue(block.group(1).startswith("browser:"))

    def test_local_hostnames_exact_and_lookalike_refused(self):
        section = which_browser_section(self.text)
        for host in ("`localhost`", "`127.0.0.1`", "`[::1]`"):
            self.assertIn(host, section)
        self.assertIn("localhost.evil.com", section)

    def test_model_is_inherited(self):
        self.assertIn("\nmodel: inherit\n", frontmatter(self.text))


class SkillText(unittest.TestCase):
    def test_skill_is_not_model_invocable(self):
        head = frontmatter(SKILL.read_text())
        self.assertIn("name: browser-check-runner", head)
        self.assertRegex(head, r"(?m)^description: \S")
        self.assertIn("disable-model-invocation: true", head)


NODE = shutil.which("node")
NPM = shutil.which("npm")


def need_node(test):
    if not NODE or not NPM:
        test.skipTest("node or npm is not on PATH")


class Runner(unittest.TestCase):
    def test_syntax(self):
        if not NODE:
            self.skipTest("node is not on PATH")
        done = subprocess.run([NODE, "--check", str(RUNNER)], capture_output=True, text=True)
        self.assertEqual((done.returncode, done.stderr), (0, ""))

    def test_offline_install_fails_with_exit_2_and_leaves_nothing(self):
        need_node(self)
        with tempfile.TemporaryDirectory() as cache, tempfile.TemporaryDirectory() as npm_cache:
            env = {**os.environ, "XDG_CACHE_HOME": cache, "npm_config_cache": npm_cache, "npm_config_offline": "true"}
            done = subprocess.run(
                [NODE, str(RUNNER), "--url", "http://127.0.0.1:1"],
                env=env, capture_output=True, text=True, timeout=300,
            )
            self.assertEqual(done.returncode, 2, done.stderr)
            self.assertEqual(done.stdout, "")
            self.assertIn("npm error", done.stderr)
            parent = Path(cache) / "browser-check"
            self.assertEqual([p.name for p in parent.iterdir()] if parent.exists() else [], [])

    def test_unknown_argument_exits_2(self):
        need_node(self)
        done = subprocess.run([NODE, str(RUNNER), "--bogus"], capture_output=True, text=True)
        self.assertEqual((done.returncode, done.stdout), (2, ""))


def cache_home():
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")


def browser_cache():
    configured = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if configured:
        return Path(configured)
    mac = Path.home() / "Library/Caches/ms-playwright"
    return mac if mac.exists() else Path.home() / ".cache/ms-playwright"


def installed_version():
    package = cache_home() / f"browser-check/playwright-{PLAYWRIGHT_VERSION}/node_modules/playwright/package.json"
    try:
        return json.loads(package.read_text())["version"]
    except (OSError, ValueError, KeyError):
        return None


PAGE = b"""<!doctype html><title>t</title><h1>probe</h1><script>
console.error('probe console error');
setTimeout(() => { throw new Error('probe uncaught'); }, 0);
fetch('/boom');
</script>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        status, body = (500, b"no") if self.path == "/boom" else (200, PAGE)
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class RunnerPage(unittest.TestCase):
    def test_console_error_uncaught_error_and_500_are_reported(self):
        need_node(self)
        if installed_version() != PLAYWRIGHT_VERSION:
            self.skipTest(f"Playwright {PLAYWRIGHT_VERSION} is not installed in the browser-check cache")
        if not (browser_cache() / HEADLESS_SHELL).exists():
            self.skipTest(f"{HEADLESS_SHELL} is not in the Playwright browser cache")
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            done = subprocess.run(
                [NODE, str(RUNNER), "--url", f"http://127.0.0.1:{server.server_port}/", "--timeout", "60"],
                capture_output=True, text=True, timeout=120,
            )
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual(done.returncode, 0, done.stderr)
        report = json.loads(done.stdout)
        self.assertTrue(any("probe console error" in m["text"] for m in report["console"]))
        self.assertTrue(any("probe uncaught" in e for e in report["pageErrors"]))
        self.assertTrue(any(r["status"] == 500 for r in report["httpErrors"]))


if __name__ == "__main__":
    unittest.main()
