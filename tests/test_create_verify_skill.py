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
SIGN_IN = "**Sign in:** <how, from the repository's\n   `verify-<app>` skill Launch"


def frontmatter(text):
    """Stdlib only (CI has no PyYAML): split each line on its first `: `."""
    head = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if head is None:
        raise AssertionError("no frontmatter between two --- lines")
    fields = {}
    for line in head.group(1).splitlines():
        key, _, value = line.partition(": ")
        fields[key] = value
    return fields


class Generator(unittest.TestCase):
    def setUp(self):
        self.text = GENERATOR.read_text(encoding="utf-8")

    def test_frontmatter(self):
        fields = frontmatter(self.text)
        self.assertEqual(fields["name"], GENERATOR.parent.name)
        self.assertTrue(fields["description"].strip())

    def test_five_sections_are_headings_not_prose(self):
        for name in SECTIONS:
            with self.subTest(name):
                self.assertRegex(self.text, re.compile(rf"^#{{2,3}} {name}\b", re.M))

    def test_execute_once_rule_is_one_exact_sentence(self):
        self.assertEqual(self.text.count(EXECUTE_ONCE), 1)

    def test_per_call_shell_rules_are_stated(self):
        for needle in (
            "start_new_session=True",
            "trap - EXIT HUP INT TERM",
            "Never `pkill` or `killall` by name",
            "ok: <what>",
            "generated-from:",
            "stdin=subprocess.DEVNULL",
            "ps -o pgid= -p <pid>",
            "pgrep -g <pgid>",
        ):
            with self.subTest(needle):
                self.assertIn(needle, self.text)

    def test_pilot_process_rules_are_stated(self):
        """The two pilots' process and signal lessons (follow-ups t02)."""
        for needle in (
            "signal.pthread_sigmask(signal.SIG_BLOCK, held)",
            "never `SIG_IGN`",
            "preexec_fn=",
            "`Interrupted(signum)`",
            "`fail: <pgid> unverified, members <pids>",
            "ps -ww -o command=",
            '`" ".join(argv)`',
            "keep the pidfile, its log and the state directory",
            "skips Cleanup steps 1 and 2",
            "does not take step 4's exit codes",
            "print(path, flush=True)",
            "`<pidfile>.log`",
            "`pgrep -lg <pgid>`",
            "`PermissionError`",
            "`scripts/verify.py`",
            "git check-ignore -v",
            "Doctor checks what the app wired",
            "after driving the app",
            "credentials and cluster config",
        ):
            with self.subTest(needle):
                self.assertIn(needle, self.text)

    def test_no_machine_specific_text(self):
        for needle in ("/Users/", "homelab", "daddyshome"):
            with self.subTest(needle):
                self.assertNotIn(needle, self.text)


class WiringIntoWorktreeTask(unittest.TestCase):
    def test_f2_prefers_the_verify_skill(self):
        text = (SKILLS / "worktree-task/SKILL.md").read_text(encoding="utf-8")
        self.assertEqual(text.count(F2_PREFERENCE), 1)
        self.assertIn("create-verify-skill", text)

    def test_preview_guide_has_a_sign_in_line(self):
        text = (SKILLS / "worktree-task/preview-guide-template.md").read_text(encoding="utf-8")
        self.assertEqual(text.count(SIGN_IN), 1)

    def test_launcher_pins_still_hold(self):
        text = (SKILLS / "worktree-task/SKILL.md").read_text(encoding="utf-8")
        self.assertIn('model: "opus"', text)
        self.assertIn("agent-model-fallback", text)


class Listed(unittest.TestCase):
    def test_readme_lists_the_skill(self):
        self.assertIn("create-verify-skill", (ROOT / "README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
