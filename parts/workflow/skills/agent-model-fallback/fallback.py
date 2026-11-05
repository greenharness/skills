#!/usr/bin/env python3
"""Decide whether a failed named-agent launch may fall back to the root model.

The policy is in SKILL.md. This file holds its decision cases, so a launcher
and the tests read one definition. It keeps no state: the launcher passes in
what it knows (`--used`) and keeps the set of models seen cooling down.

    fallback.py classify <<'ERR'
    <error text>
    ERR
    fallback.py decide --failed opus --root <root model id> --used 0 <<'ERR'
    <error text>
    ERR

`classify` prints `cooldown`, `unavailable`, `excluded` or `ambiguous`.
`decide` prints `fallback` or `report` and a reason.
Exit status: 0 for `fallback` (and for `classify`), 1 for `report`, 2 for a
usage error or a crash.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from typing import Literal

Kind = Literal["cooldown", "unavailable", "excluded", "ambiguous"]
Verdict = Literal["fallback", "report"]

# A status code counts only beside a status marker, never as a bare number
# (`file.py:429` is not an HTTP status).
_STATUS = r"(?:http|status|error|code)[\s:=]*{c}\b|\({c}\)"

# A failure about the request or the account stays an error: another model
# would fail the same way, or switching would hide a real problem.
EXCLUDED = re.compile(
    r"context.{0,12}(length|window|overflow)|prompt is too long|too many tokens|"
    r"invalid[ _]request|" + _STATUS.format(c="40[13]") + r"|unauthori[sz]ed|forbidden|"
    r"authentication|invalid[ _]api[ _]key|permission|insufficient[ _]quota|"
    r"quota (exceeded|exhausted)|exceeded (your|the) (current )?quota|"
    r"billing|credit balance|payment|policy|content[ _]filter|safety",
    re.I,
)

# The provider says all credentials for a model are cooling down, or rate
# limits it: transient, and worth remembering for the invocation.
COOLDOWN = re.compile(
    r"cooling down|cooldown|" + _STATUS.format(c="429") + r"|rate[ _-]?limit|too many requests",
    re.I,
)

# The model itself, or the provider's capacity, is unavailable.
UNAVAILABLE = re.compile(
    r"model[ _]not[ _]found|unknown model|unsupported model|no such model|"
    r"\bmodel\s+[`'\"]?[\w.:/-]+[`'\"]?\s+(is not available|is unavailable|does not exist|is not supported)|"
    + _STATUS.format(c="(?:503|529)")
    + r"|overloaded|temporarily unavailable|at capacity",
    re.I,
)


def classify(error: str) -> Kind:
    """`excluded` beats the rest; anything unmatched is `ambiguous`."""
    if EXCLUDED.search(error):
        return "excluded"
    if COOLDOWN.search(error):
        return "cooldown"
    if UNAVAILABLE.search(error):
        return "unavailable"
    return "ambiguous"


def decide(failed: str, root: str, error: str, used: int) -> tuple[Verdict, str]:
    """Return (`fallback` | `report`, reason).

    `used` is the fallback launches already made for this task, including a
    seat that was launched on the fallback to skip a known cooldown.
    """
    kind = classify(error)
    if kind == "excluded":
        return "report", "excluded failure: another model would not help"
    if kind == "ambiguous":
        return "report", "ambiguous failure: not treated as unavailability"
    if used >= 1:
        return "report", "fallback already used for this task"
    if not root or root == failed:
        return "report", "root model is unknown or is the failed model"
    note = " and note this model as cooling down" if kind == "cooldown" else ""
    return "fallback", f"{failed} unavailable: relaunch the same agent with no model override{note}"


def read_error(parser: argparse.ArgumentParser) -> str:
    if sys.stdin.isatty():
        parser.error("the error text comes on stdin (use a quoted heredoc)")
    return sys.stdin.buffer.read().decode(errors="replace")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify a failed agent launch, or decide on a fallback.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("classify")
    decide_cmd = sub.add_parser("decide")
    decide_cmd.add_argument("--failed", required=True)
    decide_cmd.add_argument("--root", default="")
    decide_cmd.add_argument("--used", type=int, choices=(0, 1), default=0)
    args = parser.parse_args(argv)
    error = read_error(parser)
    if args.cmd == "classify":
        print(classify(error))
        return 0
    verdict, reason = decide(args.failed, args.root, error, args.used)
    print(f"{verdict}: {reason}")
    return 0 if verdict == "fallback" else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # a crash must not read as a deliberate `report`
        print(f"fallback.py: {exc!r}", file=sys.stderr)
        sys.exit(2)
