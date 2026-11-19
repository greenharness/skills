"""The verify-skill generator keeps its contract, and F2 prefers its output."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "parts/workflow/skills"
GENERATOR = SKILLS / "create-verify-skill/SKILL.md"
SECTIONS = ("Launch", "Doctor", "Drive", "Evidence", "Cleanup")
EXECUTE_ONCE = "Run the generated skill once, end to end, before you call it done."
F2_PREFERENCE = "When the repository has a `verify-*` skill, follow it for this check;"
SIGN_IN = "**Sign in:** <how, from the repository's `verify-<app>` skill Launch"


def frontmatter(text):
    """Stdlib only (CI has no PyYAML): split each line on its first `: `."""
    head = text.split("---")[1]
    fields = {}
    for line in head.strip().splitlines():
        key, _, value = line.partition(": ")
        fields[key] = value
    return fields


class Generator(unittest.TestCase):
    def setUp(self):
        self.text = GENERATOR.read_text()

    def test_frontmatter(self):
        fields = frontmatter(self.text)
        self.assertEqual(fields["name"], GENERATOR.parent.name)
        self.assertTrue(fields["description"].strip())

    def test_five_sections_are_headings_not_prose(self):
        for name in SECTIONS:
            self.assertRegex(self.text, re.compile(rf"^#{{2,3}} {name}\b", re.M), name)

    def test_headings_fail_when_a_section_is_removed(self):
        broken = re.sub(r"^### Doctor\n", "", self.text, flags=re.M)
        self.assertNotRegex(broken, re.compile(r"^#{2,3} Doctor\b", re.M))

    def test_execute_once_rule_is_one_exact_sentence(self):
        self.assertEqual(self.text.count(EXECUTE_ONCE), 1)

    def test_per_call_shell_rules_are_stated(self):
        for needle in (
            "start_new_session=True",
            "trap - EXIT INT TERM",
            "Never `pkill` or `killall` by name",
            "ok: <what>",
            "generated-from:",
        ):
            self.assertIn(needle, self.text, needle)

    def test_no_machine_specific_text(self):
        for needle in ("/Users/", "homelab", "daddyshome"):
            self.assertNotIn(needle, self.text, needle)


class WiringIntoWorktreeTask(unittest.TestCase):
    def test_f2_prefers_the_verify_skill(self):
        text = (SKILLS / "worktree-task/SKILL.md").read_text()
        self.assertEqual(text.count(F2_PREFERENCE), 1)
        self.assertIn("create-verify-skill", text)

    def test_preview_guide_has_a_sign_in_line(self):
        text = (SKILLS / "worktree-task/preview-guide-template.md").read_text()
        self.assertIn(SIGN_IN, text)

    def test_launcher_pins_still_hold(self):
        text = (SKILLS / "worktree-task/SKILL.md").read_text()
        self.assertIn('model: "opus"', text)
        self.assertIn("agent-model-fallback", text)


class Listed(unittest.TestCase):
    def test_readme_lists_the_skill(self):
        self.assertIn("create-verify-skill", (ROOT / "README.md").read_text())


if __name__ == "__main__":
    unittest.main()
