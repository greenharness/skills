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
    spec = importlib.util.spec_from_file_location("fallback", FALLBACK)
    module = importlib.util.module_from_spec(spec)
    sys.modules["fallback"] = module
    spec.loader.exec_module(module)
    return module


fb = load()


class AgentDefinitions(unittest.TestCase):
    def test_no_agent_pins_a_model(self):
        # Omitting the override is a fallback only when the definition inherits.
        files = sorted(AGENTS.glob("*.md"))
        self.assertTrue(files)
        for f in files:
            head = f.read_text().split("---")[1]
            models = re.findall(r"^model:\s*(\S+)\s*$", head, re.M)
            self.assertEqual(models, ["inherit"], f.name)

    def test_pinned_definition_is_caught(self):
        head = "name: x\nmodel: opus\n"
        self.assertNotEqual(re.findall(r"^model:\s*(\S+)\s*$", head, re.M), ["inherit"])


class Launchers(unittest.TestCase):
    def test_launchers_pass_the_preference_and_cite_the_policy(self):
        for skill in ("plan-review", "worktree-task"):
            text = (SKILLS / skill / "SKILL.md").read_text()
            self.assertIn('model: "opus"', text, skill)
            self.assertIn("agent-model-fallback", text, skill)

    def test_policy_skill_is_not_model_invocable(self):
        text = (SKILLS / "agent-model-fallback/SKILL.md").read_text()
        self.assertIn("disable-model-invocation: true", text)


class Classify(unittest.TestCase):
    def test_unavailable(self):
        for e in (
            "API Error: Request rejected (429) · All credentials for model claude-opus are cooling down",
            "model_not_found: the model `x` does not exist",
            "503 overloaded_error",
            "unsupported model: foo",
        ):
            self.assertEqual(fb.classify(e), "unavailable", e)

    def test_excluded_beats_unavailable(self):
        for e in (
            "400 invalid_request_error: prompt is too long (429 tokens over)",
            "401 Unauthorized",
            "403 permission denied",
            "429 insufficient_quota: check your billing details",
            "blocked by content policy",
            "context length exceeded",
        ):
            self.assertEqual(fb.classify(e), "excluded", e)

    def test_ambiguous(self):
        for e in ("", "Error: something went wrong", "the model said it is unavailable to chat"):
            self.assertEqual(fb.classify(e), "ambiguous", e)


class Decide(unittest.TestCase):
    COOL = "429 all credentials for model opus are cooling down"

    def test_preferred_succeeds_means_no_decision(self):
        # No failure, no call: a fresh invocation holds no cooldown or fallback.
        inv = fb.Invocation()
        self.assertFalse(inv.skip_preferred("opus"))
        self.assertEqual(inv.fallbacks, {})

    def test_unavailable_falls_back_once(self):
        inv = fb.Invocation()
        self.assertEqual(inv.decide("backend", "opus", "root", self.COOL)[0], "fallback")
        # The fallback itself failing is reported, never a second launch.
        self.assertEqual(inv.decide("backend", "opus", "root", self.COOL)[0], "report")

    def test_root_equal_or_unknown_reports(self):
        self.assertEqual(fb.Invocation().decide("t", "opus", "opus", self.COOL)[0], "report")
        self.assertEqual(fb.Invocation().decide("t", "opus", "", self.COOL)[0], "report")

    def test_excluded_and_ambiguous_report_and_record_no_cooldown(self):
        inv = fb.Invocation()
        for e in ("401 unauthorized", "weird failure"):
            self.assertEqual(inv.decide("t", "opus", "root", e)[0], "report")
        self.assertFalse(inv.skip_preferred("opus"))
        self.assertEqual(inv.fallbacks, {})

    def test_cooldown_is_shared_but_scoped_and_not_persistent(self):
        inv = fb.Invocation()
        inv.decide("backend", "opus", "root", self.COOL)
        self.assertTrue(inv.skip_preferred("opus"))
        self.assertFalse(inv.skip_preferred("sonnet"))
        self.assertFalse(fb.Invocation().skip_preferred("opus"))
        # Another seat gets its own single fallback.
        self.assertEqual(inv.decide("unix", "opus", "root", self.COOL)[0], "fallback")


class Cli(unittest.TestCase):
    def run_cli(self, *args, stdin=""):
        return subprocess.run(
            [sys.executable, "-I", str(FALLBACK), *args],
            input=stdin, capture_output=True, text=True, check=False,
        )

    def test_exit_status(self):
        ok = self.run_cli("decide", "--failed", "opus", "--root", "r", stdin="429 cooldown")
        self.assertEqual((ok.returncode, ok.stdout.split(":")[0]), (0, "fallback"))
        no = self.run_cli("decide", "--failed", "opus", "--root", "r", stdin="401")
        self.assertEqual((no.returncode, no.stdout.split(":")[0]), (1, "report"))
        self.assertEqual(self.run_cli("classify", stdin="503").stdout.strip(), "unavailable")


if __name__ == "__main__":
    unittest.main()
