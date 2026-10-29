#!/bin/sh
# Fails when published content carries something only one machine knows, or
# when a forked skill lost the notice its licence requires.
set -eu
cd "$(dirname "$0")/.."

PATTERN='daddyshome|/Users/|mtls|homelab|fredericrous/decisions|\bwork\.[a-z][a-z-]+|ADR-[0-9]{4}|~/\.claude/tools/|relais:begin'
rc=0
if grep -rnEI "$PATTERN" parts; then
    echo "check: machine-specific content above (pattern: $PATTERN)" >&2
    rc=1
fi

# Skills forked from another repository keep its NOTICE.md.
for d in interface interface-review accessibility layout writing motion-design diagnosing-bugs retro; do
    f="parts/workflow/skills/$d/NOTICE.md"
    if [ ! -f "$f" ]; then
        echo "check: $f is missing" >&2
        rc=1
    fi
done
exit "$rc"
