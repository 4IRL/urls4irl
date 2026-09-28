#!/usr/bin/env bash
#
# Entrypoint for the hub `playwright` browser server (docker/compose.hub.yaml).
#
# WHY: the idle server holds ~518 MB for nothing between UI runs. This script will supervise
# `playwright run-server` and exit 0 once no client has been connected for
# U4I_PLAYWRIGHT_IDLE_MINUTES; `make playwright-up` then restarts the exited container in place.
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

fail "usage: --count FILE…"
