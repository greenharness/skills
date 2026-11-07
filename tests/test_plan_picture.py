"""plan-picture's check.py on small plan files."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

CHECK = Path(__file__).resolve().parent.parent / "parts/workflow/skills/plan-picture/check.py"


def load():
    spec = importlib.util.spec_from_file_location("plan_picture_check", CHECK)
    module = importlib.util.module_from_spec(spec)
    sys.modules["plan_picture_check"] = module
    spec.loader.exec_module(module)
    return module


check = load()
FENCE = "```"
GOOD = f"""# A plan

## Picture

{FENCE}
 agent --push--> remote
{FENCE}

The push now goes through the gates first.

## Phases
"""


class Check(unittest.TestCase):
    def run_on(self, text, extra=None):
        with tempfile.TemporaryDirectory() as d:
            plan = Path(d) / "plan.md"
            plan.write_text(text, encoding="utf-8")
            for name in extra or []:
                (Path(d) / name).write_text("<svg/>", encoding="utf-8")
            return check.check(plan)

    def test_good_picture_passes(self):
        self.assertEqual(self.run_on(GOOD), [])

    def test_none_with_reason_passes(self):
        self.assertEqual(self.run_on("## Picture\n\nnone: a version bump\n"), [])

    def test_missing_section(self):
        self.assertEqual(self.run_on("# A plan\n"), ["no `## Picture` section"])

    def test_bare_none_is_not_a_reason(self):
        self.assertTrue(self.run_on("## Picture\n\nnone:\n"))

    def test_wide_line(self):
        found = self.run_on(GOOD.replace("agent --push", "x" * 80))
        self.assertTrue(any("columns" in f for f in found), found)

    def test_wide_characters_count_twice(self):
        self.assertEqual(check.columns("漢字"), 4)

    def test_tab(self):
        found = self.run_on(GOOD.replace(" agent", "\tagent"))
        self.assertTrue(any("tab" in f for f in found), found)

    def test_mixed_charsets(self):
        found = self.run_on(GOOD.replace("agent --push", "+--+ ┌─┐"))
        self.assertIn("ASCII corners and box-drawing characters mixed", found)

    def test_language_tag(self):
        found = self.run_on(GOOD.replace(f"{FENCE}\n agent", f"{FENCE}text\n agent"))
        self.assertIn("the picture's fence carries a language tag", found)

    def test_no_sentence(self):
        found = self.run_on(GOOD.replace("The push now goes through the gates first.\n", ""))
        self.assertIn("no sentence after the picture saying what it shows", found)

    def test_link_alone_is_not_a_sentence(self):
        text = GOOD.replace("The push now goes through the gates first.", "[p.svg](p.svg)")
        found = self.run_on(text, extra=["p.svg"])
        self.assertIn("no sentence after the picture saying what it shows", found)

    def test_missing_svg(self):
        text = GOOD.replace("first.", "first. Full picture: [p.svg](p.svg)")
        self.assertIn("linked picture p.svg does not exist", self.run_on(text))
        self.assertEqual(self.run_on(text, extra=["p.svg"]), [])

    def test_hash_inside_fence_is_not_a_heading(self):
        text = GOOD.replace(" agent --push", "## not a heading\n agent --push")
        self.assertEqual(self.run_on(text), [])

    def test_usage_error_is_exit_2(self):
        self.assertEqual(check.main(["check.py"]), 2)
        self.assertEqual(check.main(["check.py", "/nonexistent/plan.md"]), 2)


if __name__ == "__main__":
    unittest.main()
