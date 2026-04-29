#!/usr/bin/env bash
# PreToolUse hook: BLOCK Bash polling loops and redirect to the Monitor tool.
#
# Patterns blocked: `until <check>; do ... sleep N; done`,
# `while <check>; do ... sleep N; done` (incl. `while true`, `while :`),
# `for i in {1..N}; do ... sleep N; done`.
#
# The harness Monitor tool runs until-loops natively and notifies on exit,
# avoiding a blocked Bash turn on sleep.

set -eu

cmd=$(jq -r '.tool_input.command // empty')
[ -z "$cmd" ] && exit 0

flat=$(echo "$cmd" | tr '\n' ' ')

if echo "$flat" | grep -qE '\b(until|while|for)\b.*\bdo\b.*\bsleep\b[[:space:]]+[0-9]+.*\bdone\b'; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: "Polling loop detected (until/while/for + sleep + done). Use the harness Monitor tool instead — it runs an until-loop natively and notifies when the check passes, rather than burning a Bash turn on a blocked sleep. If you only need a one-shot wait on a background process you started, use Bash with run_in_background and read its output when notified."
    }
  }'
  exit 0
fi

exit 0
