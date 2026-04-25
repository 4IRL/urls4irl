#!/usr/bin/env bash
# PreToolUse hook: BLOCK redundant cwd prefixes on git commands.
# When `git -C <cwd>` or `cd <cwd> && git ...` is used, the prefix shifts
# the command past the allowlist (Bash(git commit:*), Bash(git add:*), etc.)
# and forces a permission prompt for no benefit. Block and educate.
#
# Allows: git -C <other-repo-path> ... (legitimate cross-repo use).

set -eu

cmd=$(jq -r '.tool_input.command // empty')
[ -z "$cmd" ] && exit 0

proj="${CLAUDE_PROJECT_DIR:-$PWD}"
proj_real=$(cd "$proj" 2>/dev/null && pwd -P) || proj_real="$proj"

resolve_target() {
  local path="$1"
  local target
  case "$path" in
    /*) target="$path" ;;
    *)  target="$proj_real/$path" ;;
  esac
  (cd "$target" 2>/dev/null && pwd -P) || echo "$target"
}

# Match: git -C <path> ...
path=$(echo "$cmd" | sed -nE 's|^[[:space:]]*git[[:space:]]+-C[[:space:]]+([^[:space:]]+).*|\1|p')
if [ -n "$path" ]; then
  target_real=$(resolve_target "$path")
  if [ "$target_real" = "$proj_real" ]; then
    jq -n --arg p "$path" '{
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: "Drop the `git -C \($p)` prefix — cwd is already the repo root, and the prefix shifts the command past allowlist rules like Bash(git commit:*), forcing a permission prompt. Re-issue the command without `-C`."
      }
    }'
    exit 0
  fi
fi

# Match: cd <path> && git ...   OR   cd <path> ; git ...
path=$(echo "$cmd" | sed -nE 's|^[[:space:]]*cd[[:space:]]+([^[:space:]]+)[[:space:]]*(&&|;)[[:space:]]*git[[:space:]].*|\1|p')
if [ -n "$path" ]; then
  target_real=$(resolve_target "$path")
  if [ "$target_real" = "$proj_real" ]; then
    jq -n --arg p "$path" '{
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: "Drop the `cd \($p) &&` prefix — cwd is already the repo root, and the prefix shifts the command past allowlist rules. Re-issue the git command without the cd."
      }
    }'
    exit 0
  fi
fi

exit 0
