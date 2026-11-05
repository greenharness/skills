"""Named agents inherit the root model, and the fallback policy is bounded."""
import importlib.util
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "parts/workflow/skills"
AGENTS = ROOT / "parts/workflow/agents"
FALLBACK = SKILLS / "agent-model-fallback/fallback.py"


def load():
    spec = importlib.util.spec_from_file_location("agent_model_fallback", FALLBACK)
    module = importlib.util.module_from_spec(spec)
    sys.modules["agent_model_fallback"] = module
    spec.loader.exec_module(module)
    return module


fb = load()


def pinned_models(head):
    """The `model:` values a definition's frontmatter declares."""
    return re.findall(r"^model:\s*(\S+)\s*$", head, re.M)


class AgentDefinitions(unittest.TestCase):
    def test_no_agent_pins_a_model(self):
        # Omitting the override is a fallback only when the definition inherits.
        files = sorted(AGENTS.glob("*.md"))
        self.assertTrue(files)
        for f in files:
            self.assertEqual(pinned_models(f.read_text().split("---")[1]), ["inherit"], f.name)

    def test_pinned_definition_is_caught(self):
        self.assertEqual(pinned_models("name: x\nmodel: opus\n"), ["opus"])
        self.assertEqual(pinned_models("name: x\n"), [])


class Launchers(unittest.TestCase):
    def test_launchers_pass_the_preference_and_cite_the_policy(self):
        for skill in ("plan-review", "worktree-task"):
            text = (SKILLS / skill / "SKILL.md").read_text()
            self.assertIn('model: "opus"', text, skill)
            self.assertIn("agent-model-fallback", text, skill)

    def test_plan_review_rule_precedes_the_first_launch(self):
        text = (SKILLS / "plan-review/SKILL.md").read_text()
        self.assertLess(text.index('model: "opus"'), text.index("## 3. Round 1"))

    def test_policy_skill_is_not_model_invocable(self):
        text = (SKILLS / "agent-model-fallback/SKILL.md").read_text()
        self.assertIn("disable-model-invocation: true", text)


class Classify(unittest.TestCase):
    def test_cooldown(self):
        for e in (
            "API Error: Request rejected (429) \u00b7 All credentials for model claude-opus are cooling down",
            "HTTP 429 Too Many Requests",
            "rate_limit_error",
        ):
            self.assertEqual(fb.classify(e), "cooldown", e)

    def test_unavailable(self):
        for e in (
            "model_not_found: the model `x` does not exist",
            "Error 503 overloaded_error",
            "unsupported model: foo",
            "status: 529",
        ):
            self.assertEqual(fb.classify(e), "unavailable", e)

    def test_excluded_beats_the_rest(self):
        for e in (
            "400 invalid_request_error: prompt is too long (429 tokens over)",
            "401 Unauthorized",
            "403 permission denied",
            "429 insufficient_quota: check your billing details",
            "429 You exceeded your current quota",
            "blocked by content policy",
            "context length exceeded",
        ):
            self.assertEqual(fb.classify(e), "excluded", e)

    def test_ambiguous(self):
        for e in (
            "",
            "Error: something went wrong",
            "the model said it is unavailable to chat",
            "failed at line 429",
            "see file.py:503",
        ):
            self.assertEqual(fb.classify(e), "ambiguous", e)


class Decide(unittest.TestCase):
    COOL = "429 all credentials for model opus are cooling down"

    def test_unavailable_falls_back_once(self):
        self.assertEqual(fb.decide("opus", "root", self.COOL, 0)[0], "fallback")
        # The fallback itself failing, or a seat launched on it, is reported.
        self.assertEqual(fb.decide("opus", "root", self.COOL, 1)[0], "report")

    def test_root_equal_or_unknown_reports(self):
        self.assertEqual(fb.decide("opus", "opus", self.COOL, 0)[0], "report")
        self.assertEqual(fb.decide("opus", "", self.COOL, 0)[0], "report")

    def test_excluded_and_ambiguous_report(self):
        for e in ("401 unauthorized", "weird failure"):
            self.assertEqual(fb.decide("opus", "root", e, 0)[0], "report", e)

    def test_only_a_cooldown_asks_to_note_the_model(self):
        self.assertIn("cooling down", fb.decide("opus", "root", self.COOL, 0)[1])
        self.assertNotIn("cooling down", fb.decide("opus", "root", "Error 503", 0)[1])


class Cli(unittest.TestCase):
    def run_cli(self, *args, stdin=""):
        return subprocess.run(
            [sys.executable, "-I", str(FALLBACK), *args],
            input=stdin.encode() if isinstance(stdin, str) else stdin,
            capture_output=True, check=False,
        )

    def test_exit_status(self):
        ok = self.run_cli("decide", "--failed", "opus", "--root", "r", stdin="429 cooldown")
        self.assertEqual((ok.returncode, ok.stdout.split(b":")[0]), (0, b"fallback"))
        no = self.run_cli("decide", "--failed", "opus", "--root", "r", stdin="401")
        self.assertEqual((no.returncode, no.stdout.split(b":")[0]), (1, b"report"))
        self.assertEqual(self.run_cli("classify", stdin="Error 503").stdout.strip(), b"unavailable")

    def test_second_call_for_the_task_reports(self):
        again = self.run_cli(
            "decide", "--failed", "opus", "--root", "r", "--used", "1", stdin="429 cooldown"
        )
        self.assertEqual((again.returncode, again.stdout.split(b":")[0]), (1, b"report"))

    def test_non_utf8_stdin_is_classified_not_a_crash(self):
        out = self.run_cli("classify", stdin=b"\xff\xfe 429 cooldown")
        self.assertEqual((out.returncode, out.stdout.strip()), (0, b"cooldown"))

    def test_usage_error_exits_2(self):
        self.assertEqual(self.run_cli("decide", stdin="x").returncode, 2)


if __name__ == "__main__":
    unittest.main()
