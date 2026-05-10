#!/usr/bin/env bash
# PreToolUse hook: BLOCK Bash commands that should use dedicated tools.
# Instead of warning (which gets ignored), this hard-blocks the call
# and tells the model which tool to use instead.
#
# Mapping:
#   ls, find        → Glob
#   cat, head, tail → Read
#   grep, rg        → Grep
#   sed, awk        → Edit

set -eu

cmd=$(jq -r '.tool_input.command // empty')
[ -z "$cmd" ] && exit 0

first_full=$(echo "$cmd" | awk '{print $1}')

# Block ephemeral wrapper scripts in /tmp/claude/ (and the macOS variant under /private/tmp/claude/).
# These dodge hooks but aren't allowlisted, so each invocation prompts. Force the durable path.
case "$first_full" in
  /tmp/claude/*.sh|/private/tmp/claude/*.sh)
    jq -n '{
      "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "block",
        "permissionDecisionReason": "Do not run wrapper scripts from /tmp/claude/ — they are ephemeral and not allowlisted, so each invocation prompts. Use an existing make target (run `make help` or check the Makefile), or move the wrapper to .claude/scripts/<name>.sh and add a Bash(.claude/scripts/<name>.sh:*) allow rule. /tmp/claude/ is for transient OUTPUT files (test logs, intermediate JSON) only — never executable wrappers."
      }
    }'
    exit 0
    ;;
esac

first=$(echo "$first_full" | sed 's|.*/||')

case "$first" in
  ls)
    tool="Glob"
    ;;
  find)
    # find piped/exec'd into grep|rg is content search → Grep, not Glob
    if echo "$cmd" | grep -qE -- '-exec\s+(grep|rg)\b|\|\s*xargs\s+(grep|rg)\b|\|\s*(grep|rg)\b'; then
      tool="Grep"
    else
      tool="Glob"
    fi
    ;;
  cat)
    # Allow cat with redirects (>, >>, <<) — those are file writes, handled elsewhere
    if echo "$cmd" | grep -qE 'cat\s+(>|>>|<<)'; then
      exit 0
    fi
    tool="Read"
    ;;
  head|tail)
    tool="Read"
    ;;
  grep|rg)
    tool="Grep"
    ;;
  sed|awk)
    tool="Edit"
    ;;
  *)
    exit 0
    ;;
esac

jq -n --arg f "$first" --arg t "$tool" '{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "block",
    "permissionDecisionReason": "Do not use Bash(\($f)) — use the dedicated \($t) tool instead. Rewrite this action using the \($t) tool."
  }
}'
