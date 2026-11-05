#!/usr/bin/env python3
"""Decide whether a failed named-agent launch may fall back to the root model.

The policy is in SKILL.md. This file holds its decision cases, so a launcher
and the tests read one definition.

    fallback.py classify <<< "<error text>"
    fallback.py decide --failed opus --root my-root-model <<< "<error text>"

`classify` prints `unavailable`, `excluded` or `ambiguous`. `decide` prints
`fallback` or `report` and a reason; its exit status is 0 for `fallback`.
"""
import argparse
import re
import sys
from dataclasses import dataclass, field

# A failure that is about the request or the account stays an error: another
# model would fail the same way, or switching would hide a real problem.
EXCLUDED = re.compile(
    r"context.{0,12}(length|window|overflow)|prompt is too long|too many tokens|"
    r"invalid[ _]request|\b(401|403)\b|unauthori[sz]ed|forbidden|authentication|"
    r"invalid[ _]api[ _]key|permission|insufficient[ _]quota|quota (exceeded|exhausted)|"
    r"billing|credit balance|payment|policy|content[ _]filter|safety",
    re.I,
)

# Only the model or its provider scope being unavailable counts.
UNAVAILABLE = re.compile(
    r"model[ _]not[ _]found|unknown model|unsupported model|"
    r"\bmodel\s+[`'\"]?[\w.:/-]+[`'\"]?\s+(is not available|is unavailable|does not exist|is not supported)|"
    r"no such model|"
    r"cooling down|cooldown|\b429\b|rate[ _-]?limit|too many requests|"
    r"\b(503|529)\b|overloaded|capacity|temporarily unavailable",
    re.I,
)


def classify(error: str) -> str:
    """`excluded` beats `unavailable`; anything else is `ambiguous`."""
    if EXCLUDED.search(error):
        return "excluded"
    if UNAVAILABLE.search(error):
        return "unavailable"
    return "ambiguous"


@dataclass
class Invocation:
    """State of one skill invocation. It is never persisted: a new invocation
    tries the preferred model again."""

    cooling: set = field(default_factory=set)  # models a failure named
    fallbacks: dict = field(default_factory=dict)  # task id -> launches used

    def skip_preferred(self, model: str) -> bool:
        """A later seat avoids a model this invocation already saw cooling down.
        Only that exact model: a failure of one model says nothing of another."""
        return model in self.cooling

    def decide(self, task: str, failed: str, root: str, error: str):
        """Return (`fallback`|`report`, reason). Records a positive cooldown."""
        kind = classify(error)
        if kind == "excluded":
            return "report", "excluded failure: another model would not help"
        if kind == "ambiguous":
            return "report", "ambiguous failure: not treated as unavailability"
        self.cooling.add(failed)
        if self.fallbacks.get(task, 0) >= 1:
            return "report", "fallback already used for this task"
        if not root or root == failed:
            return "report", "root model is unknown or is the failed model"
        self.fallbacks[task] = 1
        return "fallback", f"{failed} unavailable: relaunch the same agent with no model override"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("classify")
    decide_cmd = sub.add_parser("decide")
    decide_cmd.add_argument("--failed", required=True)
    decide_cmd.add_argument("--root", default="")
    decide_cmd.add_argument("--task", default="task")
    args = parser.parse_args(argv)
    error = sys.stdin.read()
    if args.cmd == "classify":
        print(classify(error))
        return 0
    verdict, reason = Invocation().decide(args.task, args.failed, args.root, error)
    print(f"{verdict}: {reason}")
    return 0 if verdict == "fallback" else 1


if __name__ == "__main__":
    sys.exit(main())
