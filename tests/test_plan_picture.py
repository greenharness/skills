"""plan-picture's check.py on small plan files."""
import contextlib
import importlib.util
import io
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
F = "```"
SENTENCE = "The push now goes through the gates first."
GOOD = f"""# A plan

## Picture

{F}
 agent --push--> remote
{F}

{SENTENCE}

## Phases
"""


class Plan:
    """A plan file in a scratch directory, with optional sibling files."""

    def __init__(self, text, files=None):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "plan.md"
        self.path.write_text(text, encoding="utf-8")
        for name, body in (files or {}).items():
            p = Path(self.dir.name) / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")

    def hash_of(self, name):
        return check.short_hash(Path(self.dir.name) / name)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.dir.cleanup()


def run(text, files=None):
    with Plan(text, files) as p:
        return check.check(p.path)


def has(findings, fragment):
    return any(fragment in f for f in findings)


class Section(unittest.TestCase):
    def test_good_picture_passes(self):
        self.assertEqual(run(GOOD), [])

    def test_missing_section(self):
        self.assertEqual(run("# A plan\n"), ["no `## Picture` section"])

    def test_heading_inside_a_code_example_is_not_the_section(self):
        text = f"````markdown\n## Picture\n\nnone: an example only here\n````\n"
        self.assertEqual(run(text), ["no `## Picture` section"])

    def test_closing_hashes_and_case(self):
        self.assertEqual(run(GOOD.replace("## Picture", "## picture ##")), [])

    def test_crlf_and_bom(self):
        self.assertEqual(run("﻿" + GOOD.replace("\n", "\r\n")), [])

    def test_level_three_heading_does_not_end_section_or_count_as_prose(self):
        text = GOOD.replace(SENTENCE, "### Details")
        self.assertTrue(has(run(text), "no sentence"))

    def test_empty_section(self):
        self.assertTrue(has(run("## Picture\n\n## Phases\n"), "is empty"))


class NoneOptOut(unittest.TestCase):
    def test_reason_passes(self):
        self.assertEqual(run("## Picture\n\nNone: a version bump only\n"), [])

    def test_bare_or_placeholder_reason_fails(self):
        for reason in ["none:", "none: bump", "none: <why> here now"]:
            self.assertTrue(has(run(f"## Picture\n\n{reason}\n"), "needs a reason"), reason)

    def test_none_holds_nothing_else(self):
        text = "## Picture\n\nnone: a version bump only\n[x](missing.svg)\n"
        self.assertTrue(has(run(text), "nothing else"))


class Fences(unittest.TestCase):
    def test_tilde_and_long_fences(self):
        self.assertEqual(run(GOOD.replace(F, "~~~")), [])
        self.assertEqual(run(GOOD.replace(F, "````")), [])

    def test_indented_fence(self):
        self.assertEqual(run(GOOD.replace(F, "   " + F)), [])

    def test_language_tag(self):
        text = GOOD.replace(f"{F}\n agent", f"{F}text\n agent")
        self.assertTrue(has(run(text), "language tag"))

    def test_tagged_line_does_not_close(self):
        text = f"## Picture\n\n{F}\nA --> B\n{F}python\n{SENTENCE}\n"
        found = run(text)
        self.assertTrue(has(found, "never closed"), found)
        self.assertTrue(has(found, "no sentence"), found)

    def test_second_block_is_flagged_and_not_prose(self):
        text = f"## Picture\n\n{F}\nA --> B\n{F}\n\n{F}\n{SENTENCE}\n{F}\n"
        found = run(text)
        self.assertTrue(has(found, "second fenced block"), found)
        self.assertTrue(has(found, "no sentence"), found)

    def test_empty_picture(self):
        self.assertTrue(has(run(f"## Picture\n\n{F}\n{F}\n\n{SENTENCE}\n"), "picture is empty"))


class Art(unittest.TestCase):
    def test_width_boundary(self):
        self.assertEqual(run(GOOD.replace(" agent --push--> remote", "x" * 76)), [])
        self.assertTrue(has(run(GOOD.replace(" agent --push--> remote", "x" * 77)), "77 columns"))

    def test_trailing_spaces_do_not_count(self):
        self.assertEqual(run(GOOD.replace(" agent --push--> remote", "x" * 76 + "   ")), [])

    def test_wide_and_combining_characters(self):
        self.assertEqual(check.columns("漢字"), 4)
        self.assertEqual(check.columns("é" * 39), 39)
        self.assertTrue(has(run(GOOD.replace(" agent --push--> remote", "漢" * 39)), "78 columns"))

    def test_tab(self):
        self.assertTrue(has(run(GOOD.replace(" agent", "\tagent")), "a tab"))

    def test_mixed_charsets(self):
        for art in ["+--+ ┌─┐", "┌───┐ --> B", "A -> ▶ B"]:
            found = run(GOOD.replace(" agent --push--> remote", art))
            self.assertTrue(has(found, "mixed"), art)

    def test_one_charset_each_passes(self):
        self.assertEqual(run(GOOD.replace(" agent --push--> remote", "┌─┐ ──▶ └─┘")), [])

    def test_link_text_inside_art_is_not_a_link(self):
        self.assertEqual(run(GOOD.replace(" agent --push--> remote", "[p](missing.svg)")), [])


class Prose(unittest.TestCase):
    def test_no_sentence(self):
        self.assertTrue(has(run(GOOD.replace(SENTENCE, "")), "no sentence"))

    def test_short_line_or_rule_is_not_a_sentence(self):
        for line in ["---", ".", "</details>", "Gates first."]:
            self.assertTrue(has(run(GOOD.replace(SENTENCE, line)), "no sentence"), line)

    def test_link_alone_is_not_a_sentence(self):
        found = run(GOOD.replace(SENTENCE, "[the full picture](https://example.com/p.svg)"))
        self.assertTrue(has(found, "no sentence"))


class Links(unittest.TestCase):
    def with_link(self, link, files=None, hashed=True):
        with Plan("", files) as p:
            suffix = ""
            if hashed and files:
                suffix = " @" + p.hash_of(next(iter(files)))
            p.path.write_text(GOOD.replace(SENTENCE, f"{SENTENCE} Full picture: {link}{suffix}"), encoding="utf-8")
            return check.check(p.path)

    def test_existing_hashed_svg_passes(self):
        self.assertEqual(self.with_link("[p](p.svg)", {"p.svg": "<svg/>"}), [])

    def test_link_forms_are_checked(self):
        for link in ["[p](missing.svg#overview)", '[p](missing.html "Interactive")',
                     "[p](<missing.svg>)", "[p](MISSING.SVG)"]:
            self.assertTrue(has(self.with_link(link), "does not exist"), link)

    def test_reference_definition(self):
        text = GOOD.replace(SENTENCE, f"{SENTENCE} See [p][ref].\n\n[ref]: missing.svg")
        self.assertTrue(has(run(text), "does not exist"))

    def test_percent_encoded_name(self):
        self.assertEqual(self.with_link("[p](my%20plan.svg)", {"my plan.svg": "<svg/>"}), [])

    def test_absolute_and_outside(self):
        self.assertTrue(has(self.with_link("[p](/tmp/old.svg)"), "absolute"))
        self.assertTrue(has(self.with_link("[p](~/old.svg)"), "absolute"))
        self.assertTrue(has(self.with_link("[p](../old.svg)"), "outside"))

    def test_urls_are_skipped(self):
        self.assertEqual(self.with_link("[p](HTTPS://example.com/p.svg)"), [])
        self.assertEqual(self.with_link("[p](//cdn.example.com/p.svg)"), [])

    def test_hash_missing_and_stale(self):
        self.assertTrue(has(self.with_link("[p](p.svg)", {"p.svg": "<svg/>"}, hashed=False), "no hash"))
        found = self.with_link("[p](p.svg) @0000000", {"p.svg": "<svg/>"}, hashed=False)
        self.assertTrue(has(found, "is stale"), found)


class RoundTwo(unittest.TestCase):
    """Findings of the second review round."""

    def suffix(self, extra, files=None):
        return run(GOOD.replace("\n\n## Phases", f"\n{extra}\n\n## Phases"), files)

    def test_link_in_a_subheading_is_checked(self):
        self.assertTrue(has(self.suffix("### [p](missing.svg) @0000000"), "does not exist"))

    def test_reference_defined_outside_the_section(self):
        text = GOOD.replace(SENTENCE, f"{SENTENCE} Full: [p][diagram] @0000000") + "\n[diagram]: missing.svg\n"
        self.assertTrue(has(run(text), "does not exist"))

    def test_parenthesised_title_and_html_src(self):
        self.assertTrue(has(self.suffix("[p](missing.svg (Overview))"), "does not exist"))
        self.assertTrue(has(self.suffix('<img src="missing.svg" alt="p">'), "does not exist"))

    def test_wrapped_sentence_passes(self):
        self.assertEqual(run(GOOD.replace(SENTENCE, "The gates\nnow precede push.")), [])

    def test_code_and_comments_are_not_prose(self):
        for line in ["    The gates now precede push.", f"`{SENTENCE}`",
                     "<!-- todo write the sentence here -->"]:
            self.assertTrue(has(run(GOOD.replace(SENTENCE, line)), "no sentence"), line)

    def test_cjk_sentence(self):
        self.assertEqual(run(GOOD.replace(SENTENCE, "推送现在先经过检查关卡。")), [])

    def test_none_with_a_link_on_its_line(self):
        found = run("## Picture\n\nnone: a version bump only [p](missing.svg)\n")
        self.assertTrue(has(found, "nothing else"), found)

    def test_nul_in_target_is_a_finding_not_a_crash(self):
        self.assertTrue(has(self.suffix("[x](a%00.svg) @abc1234"), "not a valid path"))

    def test_colon_in_name_is_checked_and_windows_path_is_absolute(self):
        self.assertTrue(has(self.suffix("[p](plan:v2.svg)"), "does not exist"))
        self.assertTrue(has(self.suffix("[p](C:/x.svg)"), "absolute"))

    def test_flag_labels_in_a_box_picture_are_not_strokes(self):
        art = "┌──────────────────────┐\n│ git push --no-verify │\n└──────────────────────┘"
        self.assertEqual(run(GOOD.replace(" agent --push--> remote", art)), [])

    def test_hash_ignores_line_endings(self):
        with Plan(GOOD, {"a.svg": "<svg>\n</svg>\n", "b.svg": "<svg>\r\n</svg>\r\n"}) as p:
            self.assertEqual(p.hash_of("a.svg"), p.hash_of("b.svg"))


class Main(unittest.TestCase):
    def run_main(self, args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = check.main(["check.py", *args])
        return rc, out.getvalue()

    def test_exit_codes(self):
        with Plan(GOOD) as good, Plan("# no picture\n") as bad:
            self.assertEqual(self.run_main([str(good.path)]), (0, ""))
            rc, out = self.run_main([str(bad.path)])
            self.assertEqual(rc, 1)
            self.assertIn("no `## Picture` section", out)
            self.assertEqual(self.run_main([str(good.path), "extra"])[0], 2)
            self.assertEqual(self.run_main(["--bogus"])[0], 2)
            self.assertEqual(self.run_main([good.dir.name])[0], 2)
        self.assertEqual(self.run_main([])[0], 2)
        self.assertEqual(self.run_main(["/nonexistent/plan.md"])[0], 2)

    def test_invalid_utf8_is_exit_2(self):
        with Plan("") as p:
            p.path.write_bytes(b"## Picture\n\xff\xfe\n")
            self.assertEqual(self.run_main([str(p.path)])[0], 2)

    def test_hash_mode(self):
        with Plan(GOOD, {"p.svg": "<svg/>"}) as p:
            rc, out = self.run_main(["--hash", str(Path(p.dir.name) / "p.svg")])
            self.assertEqual((rc, out.strip()), (0, p.hash_of("p.svg")))


if __name__ == "__main__":
    unittest.main()
