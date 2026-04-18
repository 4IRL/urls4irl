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

# GH_TOKEN=$(...) or TOKEN=$(...) feeding gh/git — handled by dedicated push/gh hooks
# Covers: GH_TOKEN=$(...) gh ..., TOKEN=$(...) && GH_TOKEN=$TOKEN gh ..., etc.
if printf '%s' "$cmd" | grep -qE '(^|[;&|]+\s*)(GH_TOKEN|TOKEN)=\$\('; then
  exit 0
fi

# BRANCH=$(git branch --show-current) — handled by push script hooks
if printf '%s' "$cmd" | grep -qE '(^|[;&|]+\s*)BRANCH=\$\(git\s+branch'; then
  exit 0
fi

# gh-app-push.sh — the push script internally uses $(...)
if printf '%s' "$cmd" | grep -qE 'gh-app-push\.sh'; then
  exit 0
fi

# generate-gh-token.sh invoked directly
if printf '%s' "$cmd" | grep -qE 'generate-gh-token\.sh'; then
  exit 0
fi

# --- Block raw GitHub tokens (ghs_, ghp_, gho_, ghu_, ghr_) inlined in commands ---
# Prevents the model from working around $(...) blocks by resolving tokens first
if printf '%s' "$cmd" | grep -qE 'gh[spo ur]_[A-Za-z0-9]'; then
  jq -n '{
    "decision": "block",
    "reason": "Never inline raw GitHub tokens in commands — they leak secrets into logs. Use GH_TOKEN=$(/Users/ggpropersi/.claude/generate-gh-token.sh) as a prefix, or use the gh-app-push.sh script for pushes."
  }'
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
