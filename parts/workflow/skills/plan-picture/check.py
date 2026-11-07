#!/usr/bin/env python3
"""Check a plan's `## Picture` section.

    check.py <plan.md>

Exit 0: the picture holds. Exit 1: findings, one per line on stdout.
Exit 2: usage error or unreadable file, never a pass.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

MAX_COLUMNS = 76
ASCII_CORNER = re.compile(r"\+[-=]|[-=]\+")
BOX_DRAWING = re.compile("[─-╿]")
LINK = re.compile(r"\]\(([^)\s]+\.(?:svg|html))\)")


def columns(line: str) -> int:
    """Display width: wide and full-width characters take two columns."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in line)


def picture_section(text: str) -> list[str] | None:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.fullmatch(r"##\s+Picture\s*", line):
            body = []
            fenced = False
            for rest in lines[i + 1 :]:
                if rest.startswith("```"):
                    fenced = not fenced
                elif not fenced and re.match(r"#{1,2}\s", rest):
                    break
                body.append(rest)
            return body
    return None


def check(plan: Path) -> list[str]:
    section = picture_section(plan.read_text(encoding="utf-8"))
    if section is None:
        return ["no `## Picture` section"]
    first = next((l for l in section if l.strip()), "")
    if first.strip().startswith("none:") and len(first.strip()) > len("none:"):
        return []

    findings = []
    starts = [i for i, l in enumerate(section) if l.startswith("```")]
    if len(starts) < 2:
        return ["no fenced block in `## Picture` (or `none: <why>` for no picture)"]
    open_i, close_i = starts[0], starts[1]
    if section[open_i].strip() != "```":
        findings.append("the picture's fence carries a language tag")
    art = section[open_i + 1 : close_i]
    for n, line in enumerate(art, 1):
        if "\t" in line:
            findings.append(f"picture line {n}: a tab")
        width = columns(line)
        if width > MAX_COLUMNS:
            findings.append(f"picture line {n}: {width} columns, over {MAX_COLUMNS}")
    joined = "\n".join(art)
    if ASCII_CORNER.search(joined) and BOX_DRAWING.search(joined):
        findings.append("ASCII corners and box-drawing characters mixed")

    after = [l for l in section[close_i + 1 :] if l.strip() and not l.startswith("```")]
    prose = [l for l in after if not LINK.search(l) or len(LINK.sub("", l).split()) > 3]
    if not prose:
        findings.append("no sentence after the picture saying what it shows")

    for target in LINK.findall("\n".join(section)):
        if re.match(r"[a-z]+://", target):
            continue
        if not (plan.parent / target).is_file():
            findings.append(f"linked picture {target} does not exist")
    return findings


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    plan = Path(argv[1])
    try:
        findings = check(plan)
    except (OSError, UnicodeDecodeError) as err:
        print(f"check.py: {err}", file=sys.stderr)
        return 2
    for f in findings:
        print(f"{plan}: {f}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
