#!/usr/bin/env bash
# PreToolUse hook: auto-allow Bash commands that are read-only.
# Detects commands composed entirely of safe, non-destructive utilities
# (grep, echo, head, tail, basename, dirname, wc, sort, find, ls, cat without
# redirect, for loops, etc.) and auto-allows them so shell expansions ($(), $var)
# don't trigger the "simple_expansion" permission prompt.
#
# Returns allow decision only for clearly safe commands; exits silently otherwise
# to let other hooks and the default permission system handle the rest.

set -eu

cmd=$(jq -r '.tool_input.command // empty')
[ -z "$cmd" ] && exit 0

allow() {
  jq -n --arg r "$1" '{
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "allow",
      "permissionDecisionReason": $r
    }
  }'
  exit 0
}

# ── Quick reject: commands that write, mutate, or are dangerous ──
# If ANY of these appear anywhere in the command, bail out immediately.
# This is intentionally conservative — false negatives are fine (the default
# permission system handles them), false positives would be a security gap.
if printf '%s' "$cmd" | grep -qEi '(^|[[:space:]|;&])(rm|mv|cp|chmod|chown|chgrp|mkfifo|mknod|truncate|dd|install|rsync|scp|ssh|curl|wget|apt|brew|pip|npm|npx|yarn|pnpm|docker|podman|kill|pkill|systemctl|launchctl|diskutil|mount|umount|fdisk|mkfs|git[[:space:]]+(push|reset|checkout|clean|rebase|merge|cherry-pick|stash|branch[[:space:]]+-[dD])|flask|python|node|ruby|perl|php|make|cmake|cargo|go[[:space:]]+(run|build|install))([[:space:]]|$|[|;&])'; then
  exit 0
fi

# Reject if there are any file-write redirects (>, >>)
# But allow > /dev/null and > /dev/stderr, > /dev/stdout
if printf '%s' "$cmd" | sed -E -e 's|>[[:space:]]*/dev/null||g' -e 's|>[[:space:]]*/dev/stderr||g' -e 's|>[[:space:]]*/dev/stdout||g' | grep -qE '>>?[[:space:]]*[^[:space:]|;&]'; then
  exit 0
fi

# ── Allow list: commands built from read-only utilities ──
# Extract all "first words" from the command (after pipes, semicolons, &&, ||,
# subshells, for/do/then/else keywords).
# If every first-word is in the safe set, allow it.
readonly SAFE_CMDS='grep|egrep|fgrep|rg|ag|ack|echo|printf|cat|head|tail|less|more|wc|sort|uniq|tr|cut|paste|column|fold|rev|tac|nl|basename|dirname|realpath|readlink|stat|file|find|ls|tree|du|df|pwd|date|uname|hostname|whoami|id|groups|env|printenv|set|test|\[|true|false|seq|yes|sleep|tee|xargs|awk|sed|jq|yq|diff|comm|join|md5|md5sum|sha256sum|shasum|openssl[[:space:]]+dgst|hexdump|xxd|od|strings|nm|ldd|otool|which|where|whereis|type|command|hash|for|while|do|done|if|then|else|elif|fi|case|esac|in|\{|\}|\(|\)|select'

# Tokenize: split on pipes, semicolons, &&, ||, and newlines; grab first word of each segment.
first_words=$(printf '%s\n' "$cmd" | tr '\n' ';' | sed -E 's/[|;&]+/\n/g' | awk '{
  # Skip leading shell keywords that are not actual commands
  i = 1
  while (i <= NF && ($i == "do" || $i == "done" || $i == "then" || $i == "else" || $i == "elif" || $i == "fi" || $i == "esac" || $i == "in" || $i == "{" || $i == "}" || $i == "(" || $i == ")")) i++
  if (i <= NF) { sub(".*/", "", $i); print $i }
}')

# Check every first-word against the safe list
while IFS= read -r word; do
  [ -z "$word" ] && continue
  if ! printf '%s' "$word" | grep -qxE "$SAFE_CMDS"; then
    # Found a command not in the safe list — bail out
    exit 0
  fi
done <<< "$first_words"

allow "Read-only command using only safe utilities — no writes or mutations detected"
