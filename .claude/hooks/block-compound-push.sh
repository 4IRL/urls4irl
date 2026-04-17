#!/bin/bash
# Block compound Bash commands that contain git push.
# Forces the agent to split into separate tool calls so each
# individual command can be evaluated by the existing hooks.

COMMAND=$(jq -r '.tool_input.command')

# If command contains git push AND a chain operator (&&, ;, |), deny it
if echo "$COMMAND" | grep -q 'git.*push' && \
   echo "$COMMAND" | grep -qE '&&|;|\|'; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: "Compound commands containing git push are not allowed. Split into separate tool calls: run cleanup/setup commands first, then run git push in its own Bash call."
    }
  }'
fi
