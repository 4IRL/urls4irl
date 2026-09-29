#!/usr/bin/env bash
#
# End-to-end test harness for the derived hub Playwright image (docker/Dockerfile.Playwright) and
# its supervising entrypoint (docker/playwright-entrypoint.sh): idle reap, restart in place, and
# signal handling.
#
# Usage: playwright-lifecycle-test.sh [IMAGE]   (normally via `make test-playwright-lifecycle`)
#   IMAGE defaults to u4i-playwright:lifecycle-test.
#
# Runs THROWAWAY containers on their own uniquely named network, all removed on exit by one
# `trap cleanup EXIT` (modeled on docker/db-provision-test.sh). It never touches the hub's
# `playwright` container. Every server runs with a 1-minute idle window and a 2 s poll so the whole
# harness finishes in ~7 minutes.
#
# Legs:
#   (A) offline start: healthy with --network none, so no registry fetch is needed
#   (B) idle reap: still running at 50 s, then exits 0 (loopback probes never reset the clock)
#   (C) restart in place: `docker start` serves again under the same container ID
#   (D) a held connection keeps it alive past the window; SIGKILLing the client still reaps
#   (E) SIGTERM is prompt: `docker stop` exits 143/0, not 137, within 12 s
#   (F) an invalid idle knob is rejected before the server is ever spawned
#   (G) U4I_PLAYWRIGHT_IDLE_MINUTES=0 disables reaping
set -euo pipefail

IMAGE="${1:-u4i-playwright:lifecycle-test}"

RUN_ID="$$_${RANDOM}"
NET="u4i-pwlc-${RUN_ID}-net"
SERVER="u4i-pwlc-${RUN_ID}-server"
HOLDER="u4i-pwlc-${RUN_ID}-holder"
GUARD="u4i-pwlc-${RUN_ID}-guard"
NOGAP="u4i-pwlc-${RUN_ID}-nogap"

IDLE_ENV=(-e U4I_PLAYWRIGHT_IDLE_MINUTES=1 -e U4I_PLAYWRIGHT_POLL_SECONDS=2)

cleanup() {
  echo "Cleaning up..."
  local container
  for container in "$SERVER" "$HOLDER" "$GUARD" "$NOGAP"; do
    docker rm -f "$container" >/dev/null 2>&1 || true
  done
  docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

die() {
  echo "FAIL: $*" >&2
  exit 1
}

# Like die, but first dumps the tail of a container's logs for context.
die_with_logs() {
  local container=$1
  shift
  echo "--- logs: $container ---" >&2
  docker logs "$container" 2>&1 | tail -40 >&2 || true
  die "$@"
}

# Canonical TCP probe: Dockerfile.Playwright's HEALTHCHECK and compose.hub.yaml's healthcheck.test reuse
# this exact node -e script byte-identical (enforced by tests/unit/test_compose_hub.py's
# test_playwright_dockerfile_healthcheck_matches_compose and
# test_lifecycle_harness_probe_matches_compose_healthcheck). Loopback, so the idle watchdog never
# counts it as a client.
probe() {
  docker exec "$1" node -e "require('net').connect(3000,'127.0.0.1').on('connect',function(){process.exit(0)}).on('error',function(){process.exit(1)})"
}

# Polls a command every 1 s until it succeeds; returns 1 once <timeout_s> seconds have passed.
wait_until() {
  local timeout_s=$1
  shift
  local deadline=$((SECONDS + timeout_s))
  until "$@" >/dev/null 2>&1; do
    if ((SECONDS >= deadline)); then
      return 1
    fi
    sleep 1
  done
}

# Waits up to <timeout_s> seconds for a container to exit, then prints its exit code.
wait_exit() {
  local container=$1 timeout_s=$2
  local deadline=$((SECONDS + timeout_s))
  until [[ "$(docker inspect -f '{{.State.Status}}' "$container")" == exited ]]; do
    if ((SECONDS >= deadline)); then
      return 1
    fi
    sleep 1
  done
  docker inspect -f '{{.State.ExitCode}}' "$container"
}

is_running() {
  [[ "$(docker inspect -f '{{.State.Running}}' "$1")" == true ]]
}

# Sleeps until <seconds> have elapsed since <start> (a $SECONDS snapshot).
sleep_until_elapsed() {
  local start=$1 seconds=$2
  local remaining=$((start + seconds - SECONDS))
  if ((remaining > 0)); then
    sleep "$remaining"
  fi
}

server_client_count() {
  docker exec "$SERVER" u4i-playwright-entrypoint --count /proc/net/tcp /proc/net/tcp6
}

server_client_count_is() {
  [[ "$(server_client_count)" == "$1" ]]
}

# --- (A) Offline start ---
echo "-- Leg A: offline start --"
SERVER_START=$SECONDS
docker run -d --init --network none --name "$SERVER" "${IDLE_ENV[@]}" "$IMAGE" >/dev/null
wait_until 30 probe "$SERVER" || die_with_logs "$SERVER" "(A) server never accepted a connection within 30 s"
echo "PASS A"

# --- (B) Idle reap, never before a full idle window ---
echo "-- Leg B: idle reap --"
sleep_until_elapsed "$SERVER_START" 50
is_running "$SERVER" || die_with_logs "$SERVER" "(B) server exited before 50 s (reaped inside the idle window)"
EXIT_CODE="$(wait_exit "$SERVER" 100)" || die_with_logs "$SERVER" "(B) server still running 100 s after the 50 s mark"
[[ "$EXIT_CODE" == 0 ]] || die_with_logs "$SERVER" "(B) idle reap exit code: expected 0, got $EXIT_CODE"
echo "PASS B"

# --- (C) Restart in place ---
echo "-- Leg C: restart in place --"
ID_BEFORE="$(docker inspect -f '{{.Id}}' "$SERVER")"
docker start "$SERVER" >/dev/null
wait_until 30 probe "$SERVER" || die_with_logs "$SERVER" "(C) restarted server never accepted a connection within 30 s"
ID_AFTER="$(docker inspect -f '{{.Id}}' "$SERVER")"
[[ "$ID_AFTER" == "$ID_BEFORE" ]] || die "(C) container ID changed on restart: $ID_BEFORE -> $ID_AFTER"
echo "PASS C"

# --- (D) Held connection keeps it alive; SIGKILLed client still reaps ---
echo "-- Leg D: held connection, then SIGKILLed client --"
docker network create "$NET" >/dev/null
# The A-C container is on --network none and can never join a bridge network in place: recreate it.
docker rm -f "$SERVER" >/dev/null
SERVER_START=$SECONDS
docker run -d --init --name "$SERVER" --network "$NET" --network-alias pw "${IDLE_ENV[@]}" "$IMAGE" >/dev/null
wait_until 30 probe "$SERVER" || die_with_logs "$SERVER" "(D) server never accepted a connection within 30 s"
docker run -d --init --name "$HOLDER" --network "$NET" --entrypoint node "$IMAGE" \
  -e "require('net').connect(3000,'pw');setInterval(function(){},1e9)" >/dev/null
wait_until 15 server_client_count_is 1 ||
  die_with_logs "$HOLDER" "(D) client count never reached 1 (got '$(server_client_count 2>&1)')"
sleep_until_elapsed "$SERVER_START" 90
is_running "$SERVER" || die_with_logs "$SERVER" "(D) server reaped at under 90 s while a client was connected"
docker kill -s KILL "$HOLDER" >/dev/null
wait_until 15 server_client_count_is 0 ||
  die_with_logs "$SERVER" "(D) client count never returned to 0 (got '$(server_client_count 2>&1)')"
EXIT_CODE="$(wait_exit "$SERVER" 100)" || die_with_logs "$SERVER" "(D) server not reaped within 100 s of the client dying"
[[ "$EXIT_CODE" == 0 ]] || die_with_logs "$SERVER" "(D) idle reap exit code: expected 0, got $EXIT_CODE"
echo "PASS D"

# --- (E) SIGTERM is prompt ---
echo "-- Leg E: SIGTERM is prompt --"
docker start "$SERVER" >/dev/null
wait_until 30 probe "$SERVER" || die_with_logs "$SERVER" "(E) restarted server never accepted a connection within 30 s"
STOP_START=$SECONDS
docker stop -t 10 "$SERVER" >/dev/null
STOP_ELAPSED=$((SECONDS - STOP_START))
EXIT_CODE="$(docker inspect -f '{{.State.ExitCode}}' "$SERVER")"
[[ "$EXIT_CODE" == 143 || "$EXIT_CODE" == 0 ]] ||
  die_with_logs "$SERVER" "(E) docker stop exit code: expected 143 or 0, got $EXIT_CODE"
((STOP_ELAPSED <= 12)) || die "(E) docker stop took ${STOP_ELAPSED}s (limit 12 s)"
echo "PASS E"

# --- (F) Invalid knob is rejected before the server starts ---
echo "-- Leg F: invalid idle knob --"
docker run -d --init --network none --name "$GUARD" -e U4I_PLAYWRIGHT_IDLE_MINUTES=abc "$IMAGE" >/dev/null
EXIT_CODE="$(wait_exit "$GUARD" 10)" || die_with_logs "$GUARD" "(F) invalid knob did not stop the container within 10 s"
[[ "$EXIT_CODE" != 0 ]] || die_with_logs "$GUARD" "(F) invalid knob exited 0"
GUARD_LOGS="$(docker logs "$GUARD" 2>&1)"
[[ "$GUARD_LOGS" == *"playwright-entrypoint: "* ]] ||
  die "(F) no 'playwright-entrypoint: ' failure message. Logs were:
$GUARD_LOGS"
[[ "$GUARD_LOGS" != *"playwright-entrypoint: serving"* ]] ||
  die "(F) the server was started despite the invalid knob. Logs were:
$GUARD_LOGS"
echo "PASS F"

# --- (G) IDLE_MINUTES=0 disables reaping ---
echo "-- Leg G: IDLE_MINUTES=0 disables reaping --"
NOGAP_START=$SECONDS
docker run -d --init --network none --name "$NOGAP" \
  -e U4I_PLAYWRIGHT_IDLE_MINUTES=0 -e U4I_PLAYWRIGHT_POLL_SECONDS=2 "$IMAGE" >/dev/null
wait_until 30 probe "$NOGAP" || die_with_logs "$NOGAP" "(G) server never accepted a connection within 30 s"
sleep_until_elapsed "$NOGAP_START" 75
is_running "$NOGAP" || die_with_logs "$NOGAP" "(G) server exited with reaping disabled"
probe "$NOGAP" || die_with_logs "$NOGAP" "(G) server stopped accepting connections at 75 s"
echo "PASS G"

echo "ALL PLAYWRIGHT-LIFECYCLE LEGS PASSED"
