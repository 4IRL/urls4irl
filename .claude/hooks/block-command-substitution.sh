#!/usr/bin/env bash
# PreToolUse hook: BLOCK Bash commands that contain command substitution.
# $(...) and backticks trigger the "Contains command_substitution" security
# prompt. Split into separate sequential Bash calls instead.
#
# Exemptions:
#   - git commit -m "$(cat <<'EOF' ...)" — the standard heredoc commit pattern
#   - GH_TOKEN=$(...) — handled by dedicated push/gh hooks
#   - BRANCH=$(git branch --show-current) — handled by push script hooks

set -eu

cmd=$(jq -r '.tool_input.command // empty')
[ -z "$cmd" ] && exit 0

# --- Exemptions ---

# git commit with heredoc message: git commit -m "$(cat <<'EOF' ...)"
if printf '%s' "$cmd" | grep -qE 'git\s+commit\s.*\$\(cat\s+<<'; then
  exit 0
fi

# GH_TOKEN=$(...) — already handled by push/gh hooks
if printf '%s' "$cmd" | grep -qE '^GH_TOKEN=\$\('; then
  exit 0
fi

# BRANCH=$(git branch --show-current) — already handled by push hooks
if printf '%s' "$cmd" | grep -qE '^BRANCH=\$\(git\s+branch'; then
  exit 0
fi

# --- Block $(...) ---
if printf '%s' "$cmd" | grep -qF '$('; then
  jq -n '{
    "decision": "block",
    "reason": "Command substitution $(...) triggers a security prompt. Split into sequential Bash calls: first run the inner command to get its output, then use the result in the next call."
  }'
  exit 0
fi

# --- Block backticks ---
if printf '%s' "$cmd" | grep -qF '`'; then
  jq -n '{
    "decision": "block",
    "reason": "Backtick command substitution triggers a security prompt. Split into sequential Bash calls: first run the inner command to get its output, then use the result in the next call."
  }'
  exit 0
fi

exit 0
