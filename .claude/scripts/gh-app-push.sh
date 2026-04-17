#!/bin/bash
# gh-app-push.sh — safely push a branch to 4IRL/urls4irl as u4i-claude-code[bot].
#
# Why this exists:
#   The project's .claude/settings.local.json injects a stale GH_TOKEN (a PAT
#   belonging to user u4i-bot) into every Bash process's environment. The
#   conventional one-liner
#       GH_TOKEN=$(token-gen) git ... "https://x-access-token:$GH_TOKEN@..."
#   has a bash evaluation bug: the parent shell expands $GH_TOKEN inside the
#   URL BEFORE the command-prefix assignment takes effect, so git pushes with
#   the stale PAT — not the fresh App token. This script sidesteps the issue
#   by storing the fresh token in a local variable named APP_TOKEN (so nothing
#   in the environment can shadow it) and unsetting GH_TOKEN so no subprocess
#   accidentally inherits the stale PAT.
#
# Usage:
#   .claude/scripts/gh-app-push.sh [branch-name]
#
# Arguments:
#   branch-name  Optional. Defaults to the current branch. Must not be
#                main or master. Must not contain any force-push flag.
#
# Exit codes:
#   0  Push succeeded.
#   2  Bad arguments (too many, or detached HEAD with no branch given).
#   3  Refused: target is main/master or a force flag was supplied.
#   4  Token generator missing or not executable.
#   5  Token generator returned an invalid value.
#   other  git push failed (its own exit code is propagated).

set -euo pipefail

REPO_URL="github.com/4IRL/urls4irl.git"
TOKEN_GENERATOR="$HOME/.claude/generate-gh-token.sh"

if [ $# -gt 1 ]; then
  echo "Error: too many arguments. Usage: $0 [branch-name]" >&2
  exit 2
fi

BRANCH="${1:-$(git branch --show-current)}"

if [ -z "$BRANCH" ]; then
  echo "Error: no branch name given and git branch --show-current is empty (detached HEAD?)." >&2
  exit 2
fi

case "$BRANCH" in
  main|master)
    echo "Error: refusing to push to '$BRANCH'. Feature branches only." >&2
    exit 3
    ;;
  --force|-f|--force-with-lease|--force-with-lease=*|*\ --force*|*\ -f*)
    echo "Error: branch name looks like a force-push flag: '$BRANCH'. Refused." >&2
    exit 3
    ;;
esac

if [ ! -x "$TOKEN_GENERATOR" ]; then
  echo "Error: token generator not found or not executable: $TOKEN_GENERATOR" >&2
  exit 4
fi

# Remove the stale GH_TOKEN injected by Claude Code so nothing downstream can
# accidentally use it. We deliberately do NOT name our own variable GH_TOKEN.
unset GH_TOKEN

APP_TOKEN=$("$TOKEN_GENERATOR")

if [ -z "$APP_TOKEN" ] || [ "${APP_TOKEN:0:4}" != "ghs_" ]; then
  echo "Error: token generator did not return a valid installation token (expected 'ghs_' prefix)." >&2
  exit 5
fi

echo "Pushing '$BRANCH' to $REPO_URL as u4i-claude-code[bot]..."

# credential.helper= disables the osxkeychain helper so the URL-embedded token
# is the only credential consulted. GIT_TERMINAL_PROMPT=0 prevents any
# interactive fallback if the token is rejected.
GIT_TERMINAL_PROMPT=0 git \
  -c credential.helper= \
  push -u "https://x-access-token:${APP_TOKEN}@${REPO_URL}" \
  "$BRANCH"

# `git push -u` tries to persist upstream tracking in .git/config, but the
# Claude Code sandbox blocks writes to that path. Re-run set-upstream-to so
# the caller gets a clear warning if it didn't stick — rerun the script
# (or this single line) with dangerouslyDisableSandbox: true to fix.
if git branch --set-upstream-to="origin/${BRANCH}" "$BRANCH" >/dev/null 2>&1; then
  echo "Upstream tracking set: origin/${BRANCH}"
else
  echo "Warning: could not set upstream tracking — likely sandbox-blocked .git/config write." >&2
  echo "Re-run with dangerouslyDisableSandbox: true to persist it:" >&2
  echo "  git branch --set-upstream-to=origin/${BRANCH} ${BRANCH}" >&2
fi

echo "Push complete: $BRANCH"
