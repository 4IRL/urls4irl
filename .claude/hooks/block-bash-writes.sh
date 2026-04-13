#!/usr/bin/env bash
# PreToolUse hook for the Bash tool.
# Blocks file-write patterns whose content (JSON / Python dicts / code)
# trips Claude Code's built-in brace+quote security prompt.
# Returns {"decision":"block","reason":"..."} so the calling model sees the
# reason and retries with the Write tool (no user prompt in the loop).

set -eu

cmd=$(jq -r '.tool_input.command // empty')
[ -z "$cmd" ] && exit 0

block() {
  jq -n --arg reason "$1" '{"decision":"block","reason":$reason}'
  exit 0
}

# ----- cat redirects/heredocs ---------------------------------------------
# Matches: cat > file, cat >> file, cat file > out, cat << 'EOF', cat <<- EOF,
# cat <<<"string", and combined forms like: cat > file << 'EOF'
if printf '%s' "$cmd" | grep -qE 'cat[[:space:]]+([^|;&]*[[:space:]])?(>>?|<<-?|<<<)'; then
  block "Use the Write tool instead of cat redirects/heredocs. Content containing { or quotes triggers the brace+quote security prompt; the Write tool bypasses this. Write the file with the Write tool and continue."
fi

# ----- tee with file argument ---------------------------------------------
# Matches: tee file, tee -a file, ... | tee file
# Does NOT match tee used only as a diagnostic (rare) — requires a file arg.
if printf '%s' "$cmd" | grep -qE '(^|[[:space:]]|\|)[[:space:]]*tee([[:space:]]+-a)?[[:space:]]+[^[:space:]|;&]'; then
  block "Use the Write tool instead of tee. Tee with a file argument and structured content trips security prompts; Write bypasses this."
fi

# ----- echo redirects -----------------------------------------------------
if printf '%s' "$cmd" | grep -qE '(^|[[:space:]]|\|)[[:space:]]*echo[[:space:]]+.*[[:space:]]>>?[[:space:]]+[^[:space:]|;&]'; then
  block "Use the Write tool instead of echo redirects."
fi

# ----- printf redirects ---------------------------------------------------
if printf '%s' "$cmd" | grep -qE '(^|[[:space:]]|\|)[[:space:]]*printf[[:space:]]+.*[[:space:]]>>?[[:space:]]+[^[:space:]|;&]'; then
  block "Use the Write tool instead of printf redirects."
fi

# ----- inline python -c with braces --------------------------------------
# Any dict, set, or f-string inside -c content trips the brace+quote check.
if printf '%s' "$cmd" | grep -qE '(^|[[:space:]]|\|)[[:space:]]*python3?[[:space:]]+([^|;&]*[[:space:]])?-c[[:space:]]' \
   && printf '%s' "$cmd" | grep -qE '[{}]'; then
  block "Inline python -c with braces triggers security prompts. Write the script to a temp file (via the Write tool) and execute the file instead."
fi

exit 0
