#!/bin/sh
# Fails when published content carries something only one machine knows, or
# when a forked skill lost the notice its licence requires.
#
#   scripts/check.sh            the source tree
#   scripts/check.sh <dir>      an unpacked release, the same way
#
# A line that must name a pattern for a generic reason ends with
# `check: allow (<why>)`.
set -eu
root=$(cd "${1:-$(dirname "$0")/..}" && pwd)

PATTERN='daddyshome|/Users/|\.netrc|mtls|homelab|fredericrous/decisions|\bwork\.[a-z][a-z-]+|ADR-[0-9]{4}|~/\.claude/tools/|relais:begin'
rc=0
hits=$(grep -rnEIi "$PATTERN" "$root/parts" "$root/README.md" "$root/LICENSE" | grep -v 'check: allow (' || true)
if [ -n "$hits" ]; then
    printf '%s\n' "$hits"
    echo "check: machine-specific content above (pattern: $PATTERN)" >&2
    rc=1
fi

# Skills forked from another repository keep its NOTICE.md.
for d in interface interface-review accessibility layout writing motion-design diagnosing-bugs retro; do
    f="$root/parts/workflow/skills/$d/NOTICE.md"
    if [ ! -f "$f" ]; then
        echo "check: $f is missing" >&2
        rc=1
    fi
done
exit "$rc"
