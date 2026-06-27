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

# EXEMPT: known-good compounds — checked FIRST, before every block rule below.
# A match here means the command is allowed to proceed to the normal
# permission/sandbox flow even though it contains a chain operator. This is the
# escape hatch for documented patterns that legitimately chain commands.
# To add an exemption: append one extended-regex line (matched against the full
# command). Keep each pattern as specific as possible so it can't shelter an
# unrelated destructive command.
EXEMPT_PATTERNS=(
  # pytest inside the Docker web container (CLAUDE.md documented test invocation)
  'source /code/venv/bin/activate[[:space:]]*&&[[:space:]]*(python3?[[:space:]]+-m[[:space:]]+)?pytest'
  # flask CLI inside the Docker web container (CLAUDE.md documented migration/CLI invocation).
  # The trailing [^&|;]*$ anchors the exemption so any further chain operator
  # (&&/||/;) after the flask command falls through to the block (no shelter).
  'source /code/venv/bin/activate[[:space:]]*&&[[:space:]]*flask[[:space:]][^&|;]*$'
  # one-off python verification scripts inside the Docker web container (migration
  # testing). Same trailing anchor so no chained command can hide behind it.
  'source /code/venv/bin/activate[[:space:]]*&&[[:space:]]*python3?[[:space:]]+/(tmp|code)/[^&|;]*$'
  # GitHub App token prefix for gh / authenticated git push (command substitution)
  '^GH_TOKEN=\$\('
  # branch capture used by the push flow
  '^BRANCH=\$\(git branch --show-current\)'
)
for exempt in "${EXEMPT_PATTERNS[@]}"; do
  if printf '%s' "$cmd" | grep -qE "$exempt"; then
    exit 0
  fi
done

BLOCKED_PATTERNS=(
  "(^|[^[:alnum:]._/-])git[[:space:]]+push([[:space:]]|$)||all||git push must run alone so existing hooks evaluate it independently. Split cleanup/setup into separate Bash calls and run git push by itself."
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

# General sequence-compound block: any command joined with && || ; is denied so
# each piece is permission-checked on its own and destructive ops (e.g. rm -rf)
# can't hide mid-chain. Pipes (|) and command-substitution $(...) are NOT treated
# as compounds. The `\|\|` alternative matches a literal `||` only — a single `|`
# (pipe, or grep BRE `\|` alternation) never matches. `;` matches only when
# followed by whitespace or end-of-string, so a semicolon inside a quoted arg
# (grep 'a;b', sed 's/x/y/;...') is not a false positive. Known-good compounds
# are exempted at the top of this file.
if printf '%s' "$cmd" | grep -qE '&&|\|\||;[[:space:]]|;$'; then
  deny "Compound commands joined with \`&&\`, \`||\`, or \`;\` are blocked. Split into separate Bash tool calls — run independent ones in the same message to parallelize. This keeps each command individually permission-checked and stops destructive ops (e.g. \`rm -rf\`) from hiding inside a chain. Pipes (\`|\`) and \$(...) are fine. If this is a legitimate recurring pattern, add it to EXEMPT_PATTERNS in .claude/hooks/block-compound-commands.sh."
fi

exit 0
