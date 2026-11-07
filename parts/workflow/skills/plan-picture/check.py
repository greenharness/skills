#!/usr/bin/env python3
"""Check a plan's `## Picture` section.

    check.py <plan.md>      check the section
    check.py --hash <file>  print the short hash a linked picture carries

Exit 0: the picture holds. Exit 1: findings, one per line on stdout.
Exit 2: usage error or unreadable file, never a pass.
"""
from __future__ import annotations

import hashlib
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

MAX_COLUMNS = 76
MIN_SENTENCE_WORDS = 4
MIN_REASON_WORDS = 3

OPEN_FENCE = re.compile(r"^( {0,3})(`{3,}|~{3,})(.*)$")
HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$")
NONE_LINE = re.compile(r"^\s*none:\s*(.*)$", re.I)
# A stroke that draws a line. `--` or `|` inside a word or a flag
# (`--no-verify`, `a|b`) is a label, not a stroke.
ASCII_STROKE = re.compile(r"(?<![\w-])-{2,}(?![\w])|->|<-|\+[-=]|[-=]\+|(?<!\w)\|(?!\w)")
BOX_CHAR = re.compile("[─-╿▲-◁]")
TITLE = r"(?:\"[^\"]*\"|'[^']*'|\([^)]*\))"
INLINE_LINK = re.compile(r"\]\(\s*(<[^>]*>|[^)\s]+)(?:\s+" + TITLE + r")?\s*\)")
REF_USE = re.compile(r"\[([^\]]+)\]\[([^\]]*)\]|\[([^\]]+)\](?![(\[:])")
REF_DEF = re.compile(r"^ {0,3}\[([^\]]+)\]:\s*(<[^>]*>|\S+)")
HTML_SRC = re.compile(r"\b(?:src|href)\s*=\s*[\"']([^\"']+)[\"']", re.I)
HASH_AFTER = re.compile(r"\s*@([0-9a-f]{7})\b")
URL = re.compile(r"^(?:[a-z][a-z0-9+.-]*://|//|data:|mailto:)", re.I)
ABSOLUTE = re.compile(r"^(?:/|~|[a-z]:[\\/]|\\\\)", re.I)
NOT_PROSE = re.compile(r"<!--.*?-->|`[^`]*`|!?\[([^\]]*)\]\([^)]*\)", re.S)
PICTURE_SUFFIX = (".svg", ".html")


@dataclass
class Fence:
    line: int
    info: str
    body: list[str] = field(default_factory=list)
    closed: bool = False


@dataclass
class Heading:
    line: int
    level: int
    text: str


@dataclass
class Text:
    line: int
    text: str


def blocks(lines: list[str]) -> list[Fence | Heading | Text]:
    """Split markdown into fences, headings and text lines (CommonMark fences)."""
    out: list[Fence | Heading | Text] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = OPEN_FENCE.match(line)
        if m and not (m.group(2)[0] == "`" and "`" in m.group(3)):
            marker = m.group(2)
            fence = Fence(i + 1, m.group(3).strip())
            close = re.compile(r"^ {0,3}" + re.escape(marker[0]) + "{" + str(len(marker)) + r",}\s*$")
            i += 1
            while i < len(lines):
                if close.match(lines[i]):
                    fence.closed = True
                    break
                fence.body.append(lines[i])
                i += 1
            out.append(fence)
            i += 1
            continue
        h = HEADING.match(line)
        if h:
            out.append(Heading(i + 1, len(h.group(1)), (h.group(2) or "").strip()))
        else:
            out.append(Text(i + 1, line))
        i += 1
    return out


def picture_section(parsed: list) -> list | None:
    for n, b in enumerate(parsed):
        if isinstance(b, Heading) and b.level == 2 and b.text.lower() == "picture":
            body = []
            for rest in parsed[n + 1 :]:
                if isinstance(rest, Heading) and rest.level <= 2:
                    break
                body.append(rest)
            return body
    return None


def paragraphs(section: list) -> list[Text]:
    """Consecutive text lines joined, as Markdown renders them.

    An indented code block (a paragraph opening four spaces or a tab deep)
    is not a paragraph.
    """
    out: list[Text] = []
    current: Text | None = None
    for b in section:
        if isinstance(b, Text) and b.text.strip():
            if current is None:
                current = Text(b.line, b.text)
            else:
                current.text += " " + b.text.strip()
            continue
        if current is not None:
            out.append(current)
            current = None
    if current is not None:
        out.append(current)
    return [p for p in out if not re.match(r"^(?: {4}|\t)", p.text)]


def columns(line: str) -> int:
    """Display width: wide characters take two columns, marks and format none."""
    width = 0
    for c in line:
        if unicodedata.category(c) in ("Mn", "Me", "Cf"):
            continue
        width += 2 if unicodedata.east_asian_width(c) in "WF" else 1
    return width


def short_hash(path: Path) -> str:
    """sha256 prefix of the file, with CRLF read as LF so a checkout's line
    endings do not make it stale."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:7]


def ref_defs(parsed: list) -> dict[str, str]:
    defs = {}
    for b in parsed:
        if isinstance(b, Text):
            m = REF_DEF.match(b.text)
            if m:
                defs.setdefault(m.group(1).strip().lower(), m.group(2))
    return defs


def link_targets(text: str, defs: dict[str, str]) -> list[tuple[str, str | None]]:
    """(raw target, the @hash written right after the link, if any)."""
    found = []

    def add(target, end):
        h = HASH_AFTER.match(text, end)
        found.append((target, h.group(1) if h else None))

    for m in INLINE_LINK.finditer(text):
        add(m.group(1), m.end())
    m = REF_DEF.match(text)
    if m:
        add(m.group(2), m.end())
    else:
        for m in REF_USE.finditer(text):
            label = (m.group(2) or m.group(1) or m.group(3) or "").strip().lower()
            if label in defs:
                add(defs[label], m.end())
    for m in HTML_SRC.finditer(text):
        add(m.group(1), m.end())
    return found


def check_links(plan: Path, lines: list[Text | Heading], defs: dict[str, str]) -> list[str]:
    root = plan.parent.resolve()
    seen: dict[str, tuple[int, list[str | None], str]] = {}
    for b in lines:
        for raw, written in link_targets(b.text, defs):
            target = raw[1:-1] if raw.startswith("<") and raw.endswith(">") else raw
            target = unquote(re.split(r"[#?]", target, maxsplit=1)[0])
            if not target.lower().endswith(PICTURE_SUFFIX) or URL.match(target):
                continue
            entry = seen.setdefault(target, (b.line, [], target))
            entry[1].append(written)

    findings = []
    for target, (line, written, _) in seen.items():
        where = f"line {line}: linked picture {target}"
        if "\x00" in target:
            findings.append(f"{where} is not a valid path")
            continue
        if ABSOLUTE.match(target):
            findings.append(f"{where} is absolute; keep it beside the plan")
            continue
        try:
            resolved = (root / target).resolve()
            resolved.relative_to(root)
        except ValueError:
            findings.append(f"{where} is outside the plan's directory")
            continue
        if not resolved.is_file():
            findings.append(f"{where} does not exist")
            continue
        actual = short_hash(resolved)
        hashes = {w for w in written if w}
        if not hashes:
            findings.append(f"{where} carries no hash; write `@{actual}` after the link")
        elif actual not in hashes:
            stale = ", ".join(f"@{h}" for h in sorted(hashes))
            findings.append(f"{where} {stale} is stale: the file is @{actual}; review the redraw")
    return findings


def is_sentence(text: str) -> bool:
    prose = NOT_PROSE.sub(lambda m: m.group(1) or " ", text)
    words = re.findall(r"[^\W\d_][\w'’-]*", prose)
    wide = sum(1 for c in prose if unicodedata.east_asian_width(c) in "WF" and c.isalpha())
    return len(words) + wide // 2 >= MIN_SENTENCE_WORDS


def check(plan: Path) -> list[str]:
    text = plan.read_text(encoding="utf-8-sig")
    parsed = blocks(text.splitlines())
    section = picture_section(parsed)
    if section is None:
        return ["no `## Picture` section"]
    content = [b for b in section if not (isinstance(b, Text) and not b.text.strip())]
    if not content:
        return ["`## Picture` is empty: draw it, or write `none: <why>`"]
    defs = ref_defs(parsed)

    first = content[0]
    if isinstance(first, Text) and NONE_LINE.match(first.text):
        reason = NONE_LINE.match(first.text).group(1).strip()
        if len(reason.split()) < MIN_REASON_WORDS or "<why>" in reason:
            return [f"line {first.line}: `none:` needs a reason of {MIN_REASON_WORDS} words or more"]
        if len(content) > 1 or link_targets(first.text, defs):
            return [f"line {first.line}: a `none:` section holds its reason and nothing else"]
        return []

    findings = []
    fences = [b for b in content if isinstance(b, Fence)]
    if not fences:
        return ["no fenced block in `## Picture` (or `none: <why>` for no picture)"]
    if len(fences) > 1:
        findings.append(f"line {fences[1].line}: a second fenced block; the section holds one picture")
    art = fences[0]
    if not art.closed:
        findings.append(f"line {art.line}: the picture's fence is never closed")
    if art.info:
        findings.append(f"line {art.line}: the picture's fence carries a language tag")
    if not any(l.strip() for l in art.body):
        findings.append(f"line {art.line}: the picture is empty")
    for n, line in enumerate(art.body, art.line + 1):
        if "\t" in line:
            findings.append(f"line {n}: a tab in the picture")
        width = columns(line.rstrip())
        if width > MAX_COLUMNS:
            findings.append(f"line {n}: {width} columns, over {MAX_COLUMNS}")
    joined = "\n".join(art.body)
    if ASCII_STROKE.search(joined) and BOX_CHAR.search(joined):
        findings.append("ASCII strokes and box-drawing characters mixed in the picture")

    after = [p for p in paragraphs(section) if p.line > art.line]
    if not any(is_sentence(p.text) for p in after):
        findings.append("no sentence after the picture saying what it shows")
    scanned = [b for b in section if isinstance(b, (Text, Heading))]
    findings.extend(check_links(plan, scanned, defs))
    return findings


def main(argv: list[str]) -> int:
    args = argv[1:]
    try:
        if len(args) == 2 and args[0] == "--hash":
            print(short_hash(Path(args[1])))
            return 0
        if len(args) != 1 or args[0].startswith("-"):
            print(__doc__.strip(), file=sys.stderr)
            return 2
        plan = Path(args[0])
        findings = check(plan)
    except (OSError, UnicodeDecodeError) as err:
        print(f"check.py: {err}", file=sys.stderr)
        return 2
    for f in findings:
        print(f"{plan}: {f}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
