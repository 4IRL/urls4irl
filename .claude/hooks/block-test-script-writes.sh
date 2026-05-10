#!/usr/bin/env bash
# PreToolUse hook (Write|Edit): BLOCK writing test-runner wrapper scripts
# under .claude/scripts/ or /tmp/claude/. The Makefile already covers every
# test-running case via targets that are auto-unsandboxed through
# sandbox.excludedCommands (make test-file, test-file-parallel, test-marker,
# test-marker-parallel, etc.), so wrapper scripts add zero capability and
# require per-call user approval on first invocation.

set -eu

file_path=$(jq -r '.tool_input.file_path // empty')
[ -z "$file_path" ] && exit 0

if echo "$file_path" | grep -qE '(\.claude/scripts/|/tmp/claude/).*(test|pytest).*\.sh$'; then
  jq -n --arg p "$file_path" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: "Refusing to write \($p) — the project Makefile already covers test-running and is auto-unsandboxed. Use `make test-file f=<path>`, `make test-file-parallel f=<path> [n=4]`, `make test-marker m=<marker>`, or `make test-marker-parallel m=<marker> [n=4]` instead. Wrapper scripts under .claude/scripts/ or /tmp/claude/ require per-call user approval on first invocation, adding friction without adding capability."
    }
  }'
  exit 0
fi

exit 0
