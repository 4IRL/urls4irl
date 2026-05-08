#!/usr/bin/env bash
# PreToolUse hook: BLOCK compound Bash commands containing certain patterns.
# When a configured regex matches alongside a chain operator, deny the call.
# Forces the agent to split into separate Bash calls so each is evaluated by
# the existing hooks/permissions individually.
#
# To add a new pattern: append one line to BLOCKED_PATTERNS.
# Format: "<regex>||<ops>||<reason>"  (delimiter is the literal `||`)
#   <regex>  — extended regex matched against the full command (single `|`
#              alternation is fine — only the literal `||` separates fields)
#   <ops>    — which chain ops trigger the block:
#                "and"  = &&             (only the and-chain operator)
#                "seq"  = && || ;        (sequence operators)
#                "pipe" = |              (pipe only)
#                "all"  = seq + pipe
#   <reason> — message shown when denied

set -eu

cmd=$(jq -r '.tool_input.command // empty')
[ -z "$cmd" ] && exit 0

BLOCKED_PATTERNS=(
  "git.*push||all||git push must run alone so existing hooks evaluate it independently. Split cleanup/setup into separate Bash calls and run git push by itself."
  "^[[:space:]]*sleep[[:space:]]+[^[:space:]&]+[[:space:]]*&&||and||Leading \`sleep N &&\` burns a blocked Bash turn. Use the Monitor tool to wait for a condition, or Bash with run_in_background for a fire-and-forget job. To just run the second command, drop the sleep."
)

deny() {
  jq -n --arg r "$1" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: $r
    }
  }'
  exit 0
}

# General rule (not table-driven): sandbox.excludedCommands only auto-runs
# when the command is JUST `make ...` or `docker ...` with no chaining or
# piping. ANY chain operator (&&, ||, ;, |) alongside a make/docker token
# breaks the auto-allow and triggers an unsandbox approval prompt — even
# when make/docker is itself the first token (e.g. `make x | tail && rm y`,
# `make a && make b`). Force a split.
#
# `make`/`docker` is matched only at command-start positions (start of
# string, or right after a chain op) so `echo make && ls` is not a false
# positive.
if printf '%s' "$cmd" | grep -qE '(^|&&|\|\||;|\|)[[:space:]]*(make|docker)([[:space:]]|$)' && \
   printf '%s' "$cmd" | grep -qE '(&&|\|\||;|\|)'; then
  deny "Any chain operator (\`&&\`, \`||\`, \`;\`, \`|\`) alongside a \`make\`/\`docker\` command defeats sandbox.excludedCommands and triggers an unsandbox approval prompt — even when make/docker is the first token (e.g. \`make x | tail\`, \`make a && make b\`). Split into separate Bash calls. Run independent inspection/setup commands as separate Bash tool calls in the same message (they execute in parallel); run the make/docker call alone so it auto-runs unsandboxed silently."
fi

for entry in "${BLOCKED_PATTERNS[@]}"; do
  pattern="${entry%%||*}"
  rest="${entry#*||}"
  ops="${rest%%||*}"
  reason="${rest#*||}"

  case "$ops" in
    and)  op_regex='&&' ;;
    seq)  op_regex='&&|\|\||;' ;;
    pipe) op_regex='\|' ;;
    all)  op_regex='&&|\|\||;|\|' ;;
    *)    continue ;;
  esac

  if echo "$cmd" | grep -qE "$pattern" && \
     echo "$cmd" | grep -qE "$op_regex"; then
    deny "$reason"
  fi
done

exit 0
