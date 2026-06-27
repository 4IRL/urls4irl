#!/usr/bin/env bash
#
# playwright-unlock.sh
#
# Clears the recurring Playwright-MCP "Browser is already in use" lock.
#
# Symptom (from a browser_navigate / browser_snapshot / etc. call):
#   Browser is already in use for
#   /Users/<you>/Library/Caches/ms-playwright-mcp/mcp-chrome-XXXXXXX,
#   use --isolated to run multiple instances of the same browser
#
# Cause: a previous Playwright-MCP session left a Chrome process alive holding
# the singleton lock on the shared profile dir. The MCP server refuses to reuse
# a locked profile, so every later call fails until the orphan is killed.
#
# This script ONLY targets processes whose command line contains
# "mcp-chrome-" (the Playwright-MCP profile dir marker) — it can never touch a
# normal Chrome/Chromium you have open. After killing, it removes stale
# Singleton* lock files so the next MCP call acquires the profile cleanly.
#
# Idempotent: when nothing is locked it reports "nothing to do" and exits 0.

set -u

# The Playwright-MCP profile marker. Appears in the chrome --user-data-dir path
# (e.g. .../ms-playwright-mcp/mcp-chrome-3db2391). Specific to Playwright-MCP,
# so matching on it cannot catch an ordinary browser process.
readonly PROFILE_MARKER="mcp-chrome-"

# Profile cache roots where stale Singleton* lock files may linger.
readonly PROFILE_ROOTS=(
  "${HOME}/Library/Caches/ms-playwright-mcp"
  "${HOME}/Library/Caches/ms-playwright"
)

find_pids() {
  pgrep -f "${PROFILE_MARKER}" 2>/dev/null || true
}

clear_lock_files() {
  local root profile
  for root in "${PROFILE_ROOTS[@]}"; do
    [ -d "${root}" ] || continue
    for profile in "${root}/${PROFILE_MARKER}"*; do
      [ -d "${profile}" ] || continue
      rm -f "${profile}/SingletonLock" \
            "${profile}/SingletonCookie" \
            "${profile}/SingletonSocket" 2>/dev/null || true
    done
  done
}

main() {
  local pids
  pids="$(find_pids)"

  if [ -z "${pids}" ]; then
    echo "playwright-unlock: no Playwright-MCP Chrome processes found."
    clear_lock_files
    echo "playwright-unlock: cleared any stale Singleton* lock files. Nothing else to do."
    return 0
  fi

  echo "playwright-unlock: found orphaned Playwright-MCP Chrome process(es):"
  pgrep -fl "${PROFILE_MARKER}" 2>/dev/null || true

  # Graceful first: SIGTERM lets Chrome release the lock on its way out.
  echo "playwright-unlock: sending SIGTERM..."
  kill ${pids} 2>/dev/null || true
  sleep 2

  # Escalate only for survivors.
  local survivors
  survivors="$(find_pids)"
  if [ -n "${survivors}" ]; then
    echo "playwright-unlock: SIGTERM left survivors, sending SIGKILL..."
    kill -9 ${survivors} 2>/dev/null || true
    sleep 1
  fi

  local remaining
  remaining="$(find_pids)"
  if [ -n "${remaining}" ]; then
    echo "playwright-unlock: ERROR — could not kill PID(s): ${remaining}" >&2
    return 1
  fi

  clear_lock_files
  echo "playwright-unlock: all Playwright-MCP Chrome processes killed and lock files cleared."
  echo "playwright-unlock: retry your Playwright MCP call now."
  return 0
}

main "$@"
