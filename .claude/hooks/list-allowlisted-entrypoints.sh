#!/usr/bin/env bash
# SessionStart hook: front-load the model with a list of allowlisted entry points
# (Makefile targets and .claude/scripts/) so it doesn't invent new wrappers in
# /tmp/claude/ that need fresh permission each session.

set -eu

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"

make_targets=""
if [ -f "$PROJECT_DIR/Makefile" ]; then
  make_targets=$(awk -F':.*?## ' '/^[a-zA-Z][a-zA-Z0-9_-]*:.*?##/ {printf "  make %-25s — %s\n", $1, $2}' "$PROJECT_DIR/Makefile")
fi

scripts_block="  (none)"
if [ -d "$PROJECT_DIR/.claude/scripts" ]; then
  found=$(find "$PROJECT_DIR/.claude/scripts" -maxdepth 1 -type f -name '*.sh' 2>/dev/null \
    | sed "s|$PROJECT_DIR/||" \
    | sort \
    | sed 's|^|  |')
  if [ -n "$found" ]; then
    scripts_block="$found"
  fi
fi

context="ALLOWLISTED BASH ENTRY POINTS — use these instead of composing new Bash commands or dropping wrappers in /tmp/claude/.

Make targets (auto-unsandboxed via sandbox.excludedCommands — never prompt):
${make_targets:-  (no Makefile found at $PROJECT_DIR/Makefile)}

Project scripts in .claude/scripts/ (durable, allowlisted via Bash(...:*) rules in settings):
${scripts_block}

RULE: before composing any Bash command (tests, docker, git, build), check this list first. If your task is not covered, propose either:
  1. a new Makefile target (preferred — make is already excluded), or
  2. a durable script in .claude/scripts/ + an allow rule.

Do NOT drop wrapper scripts in /tmp/claude/ to dodge hooks — those paths are ephemeral, not allowlisted, blocked at the harness, and create a fresh prompt each session."

jq -n --arg ctx "$context" '{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": $ctx
  }
}'
