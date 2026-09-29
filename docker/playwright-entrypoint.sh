#!/usr/bin/env bash
#
# Entrypoint for the hub `playwright` browser server (docker/compose.hub.yaml).
#
# WHY: the idle server holds ~518 MB for nothing between UI runs. This script supervises
# `playwright run-server` and exits 0 once no client has been connected for
# U4I_PLAYWRIGHT_IDLE_MINUTES (default 15; 0 disables reaping), polling every
# U4I_PLAYWRIGHT_POLL_SECONDS (default 30, a test-harness override only: see the knob block below);
# `make playwright-up` then restarts the exited container in place. The idle clock starts at
# container start, so a fresh start gets one full window.
#
# `--count FILE…` is a pure mode used by the watchdog and by `make playwright-rebuild`'s guard: it
# prints how many clients are connected, from /proc/net/tcp-format tables (`-` reads stdin, a
# missing file is skipped, an existing file that cannot be read as a regular file fails loudly).
# A client is a row whose local port is the server port, whose state is ESTABLISHED (01), and
# whose remote address is not loopback, so the container's own healthcheck probe (127.0.0.1, and
# its IPv6 forms ::1 and ::ffff:127.0.0.1) never counts as a client.
set -euo pipefail

readonly SERVER_PORT_HEX=0BB8

fail() {
  echo "playwright-entrypoint: $1" >&2
  exit 1
}

count_established() {
  local readable_files=()
  local file
  for file in "$@"; do
    if [ "$file" != - ]; then
      [ -e "$file" ] || continue
      if [ ! -f "$file" ] || [ ! -r "$file" ]; then
        fail "cannot read $file"
      fi
    fi
    readable_files+=("$file")
  done
  if [ "${#readable_files[@]}" -eq 0 ]; then
    echo 0
    return
  fi
  # Header lines are skipped by pattern, not position: a piped stream carries one per table.
  awk -v port="$SERVER_PORT_HEX" '
    $1 == "sl" { next }
    {
      split($2, local_addr, ":")
      split($3, remote_addr, ":")
      if (local_addr[2] == port && $4 == "01" \
        && remote_addr[1] != "0100007F" \
        && remote_addr[1] != "00000000000000000000000001000000" \
        && remote_addr[1] != "0000000000000000FFFF00000100007F") {
        total++
      }
    }
    END { print total + 0 }
  ' "${readable_files[@]}"
}

if [ "${1:-}" = "--count" ]; then
  shift
  [ "$#" -ge 1 ] || fail "usage: --count FILE…"
  count_established "$@"
  exit 0
fi

[ "$#" -eq 0 ] || fail "unexpected arguments: $*"

IDLE_MINUTES="${U4I_PLAYWRIGHT_IDLE_MINUTES:-15}"
# U4I_PLAYWRIGHT_POLL_SECONDS (default 30) is a test-harness override, set only by
# docker/playwright-lifecycle-test.sh via `docker run -e` and deliberately not wired into
# compose.hub.yaml: operators tune reaping via U4I_PLAYWRIGHT_IDLE_MINUTES only.
POLL_SECONDS="${U4I_PLAYWRIGHT_POLL_SECONDS:-30}"
[[ "$IDLE_MINUTES" =~ ^[0-9]{1,5}$ ]] ||
  fail "U4I_PLAYWRIGHT_IDLE_MINUTES must be 0-99999 (0 disables reaping), got '$IDLE_MINUTES'"
[[ "$POLL_SECONDS" =~ ^[0-9]{1,5}$ ]] ||
  fail "U4I_PLAYWRIGHT_POLL_SECONDS must be 1-99999, got '$POLL_SECONDS'"
# Force base 10: a leading zero would otherwise be read as octal (and 08/09 rejected).
IDLE_MINUTES=$((10#$IDLE_MINUTES))
POLL_SECONDS=$((10#$POLL_SECONDS))
if ((POLL_SECONDS < 1)); then
  fail "U4I_PLAYWRIGHT_POLL_SECONDS must be 1-99999, got '$POLL_SECONDS'"
fi

SERVER_CMD=(playwright run-server --port 3000 --host 0.0.0.0)

if ((IDLE_MINUTES == 0)); then
  echo "playwright-entrypoint: serving :3000, reaping disabled"
  exec "${SERVER_CMD[@]}"
fi

# TERM the server, KILL it if still alive after ~5 s, then reap it. A no-op before it has started.
stop_server() {
  [ -n "${server_pid:-}" ] || return 0
  kill -TERM "$server_pid" 2>/dev/null || true
  local waited=0
  while [ "$waited" -lt 5 ] && kill -0 "$server_pid" 2>/dev/null; do
    sleep 1
    waited=$((waited + 1))
  done
  if kill -0 "$server_pid" 2>/dev/null; then
    kill -KILL "$server_pid" 2>/dev/null || true
  fi
  wait "$server_pid" || true
}

echo "playwright-entrypoint: serving :3000, reaping after ${IDLE_MINUTES}m idle"
# Trapped before the server starts, so a signal in between cannot orphan it.
trap 'stop_server; exit 143' TERM INT
"${SERVER_CMD[@]}" &
server_pid=$!

idle_since=$SECONDS
while kill -0 "$server_pid" 2>/dev/null; do
  # Backgrounded so a TERM trap fires immediately instead of after the sleep.
  sleep "$POLL_SECONDS" &
  wait $! || true
  # A server that died during the sleep falls through to the status-propagating wait below.
  kill -0 "$server_pid" 2>/dev/null || break
  active=$(count_established /proc/net/tcp /proc/net/tcp6)
  if ((active > 0)); then
    idle_since=$SECONDS
  fi
  # An `if`, never a bare (( )): under set -e a false arithmetic statement exits the script.
  if ((SECONDS - idle_since >= IDLE_MINUTES * 60)); then
    # Re-check right before exiting to narrow the window in which a just-connected client could be dropped.
    active=$(count_established /proc/net/tcp /proc/net/tcp6)
    if ((active == 0)); then
      echo "playwright-entrypoint: idle ${IDLE_MINUTES}m with no clients — exiting"
      stop_server
      exit 0
    fi
    idle_since=$SECONDS
  fi
done

# The server died on its own: propagate its exit code so a crash stays visible in `docker ps -a`.
server_status=0
wait "$server_pid" || server_status=$?
exit "$server_status"
