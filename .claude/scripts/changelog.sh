#!/usr/bin/env bash
# Appends a timestamped changelog entry to tmp/<branch-name>.md
# Usage: .claude/scripts/changelog.sh "<skill-name>: <one-line summary>"
#
# To add changelog support to a new skill, copy the ## Changelog section
# from any existing skill's SKILL.md into the new skill.

set -euo pipefail

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

# Skip changelog on main/master — not associated with feature work
if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ]; then
  exit 0
fi

TIMESTAMP=$(date '+%Y-%m-%d %H:%M')
FILE="tmp/${BRANCH}.md"

mkdir -p "$(dirname "$FILE")"

# Create file with header if it doesn't exist
if [ ! -f "$FILE" ]; then
  echo "# Changelog: ${BRANCH}" > "$FILE"
  echo "" >> "$FILE"
fi

echo "- [${TIMESTAMP}] $1" >> "$FILE"
