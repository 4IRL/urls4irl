#!/usr/bin/env bash
#
# End-to-end test harness for docker/db-provision.sh (the compose `db-init` one-shot).
#
# Usage: db-provision-test.sh   (normally via `make test-db-provision`)
#
# Runs the real script against a THROWAWAY postgres:16.3-bookworm container on its own uniquely
# named network and named volume, all removed on exit by one `trap cleanup EXIT` (modeled on
# docker/backup-pipeline-test.sh). It never touches the local stack's `db` container, its `pgdata`
# volume, or any real dev database.
#
# The script is copied into the throwaway container and run there with PGHOST=db (the container's
# own network alias), so it authenticates over TCP with scram-sha-256 exactly as `db-init` does.
# Assertions connect as the superuser over the local socket.
#
# Legs:
#   (a) fresh cluster          (b) legacy rename            (c) idempotent re-run
#   (c2) orphaned legacy DB (U4I_DEV_DB exists): isolated with a warning, not renamed
#   (d) re-applied limit/pw    (e) test-role isolation      (f) input guards, before any mutation
#   (g) a failure after the rename leaves U4I_DEV_DB connectable (the failure-recovery pass)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

RUN_ID="$$_${RANDOM}"
NET="u4i_dbprov_test_net_${RUN_ID}"
DB="u4i_dbprov_test_db_${RUN_ID}"
VOL="u4i_dbprov_test_vol_${RUN_ID}"

ADMIN=u4i_admin
PW1=provision-pw-1
PW2=provision-pw-2
TEST_ROLE=u4i_test
TEST_DB=u4i_test_base

NETWORK_CREATED=0
VOLUME_CREATED=0
DB_STARTED=0
WORK_DIR="$(mktemp -d)"

cleanup() {
  echo "Cleaning up..."
  # Background psql clients (leg g) exit once the container is gone; kill any stragglers anyway.
  local job_pid
  for job_pid in $(jobs -p); do
    kill "$job_pid" >/dev/null 2>&1 || true
  done
  if [[ "$DB_STARTED" == 1 ]]; then docker rm -f "$DB" >/dev/null 2>&1 || true; fi
  if [[ "$NETWORK_CREATED" == 1 ]]; then docker network rm "$NET" >/dev/null 2>&1 || true; fi
  if [[ "$VOLUME_CREATED" == 1 ]]; then docker volume rm "$VOL" >/dev/null 2>&1 || true; fi
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

die() {
  echo "FAIL: $*" >&2
  exit 1
}

# psql as the cluster superuser over the local socket; prints bare tuples.
sql() {
  local database=$1 query=$2
  docker exec "$DB" psql -X -v ON_ERROR_STOP=1 -qtA -U "$ADMIN" -d "$database" -c "$query"
}

expect_eq() {
  local description=$1 expected=$2 actual=$3
  [[ "$actual" == "$expected" ]] || die "$description: expected '$expected', got '$actual'"
}

expect_contains() {
  local description=$1 needle=$2 haystack=$3
  [[ "$haystack" == *"$needle"* ]] || die "$description: output lacks '$needle'. Output was:
$haystack"
}

expect_not_contains() {
  local description=$1 needle=$2 haystack=$3
  [[ "$haystack" != *"$needle"* ]] || die "$description: output unexpectedly has '$needle'. Output was:
$haystack"
}

# Polls a boolean query until it returns true (30s cap), dumping client backends on timeout.
wait_for() {
  local description=$1 query=$2
  for _ in $(seq 1 150); do
    if [[ "$(sql postgres "$query")" == t ]]; then
      return 0
    fi
    sleep 0.2
  done
  echo "--- client backends ---" >&2
  sql postgres "SELECT pid, application_name, state, wait_event_type, left(query, 90)
    FROM pg_stat_activity WHERE backend_type = 'client backend'" >&2 || true
  die "timed out waiting for: $description"
}

# Baseline env for db-provision.sh; per-run KEY=VALUE arguments replace matching keys (last wins).
BASE_ENV=(
  "PGHOST=db"
  "POSTGRES_USER=$ADMIN"
  "POSTGRES_PASSWORD=$PW1"
  "POSTGRES_TEST_DB=$TEST_DB"
  "U4I_DEV_DB=u4i_dev_fresh"
  "U4I_TEST_ROLE=$TEST_ROLE"
  "U4I_PG_TEST_CONN_LIMIT=25"
  "LEGACY_DEV_DB="
)

provision() {
  # Each key reaches docker exec exactly once: an entry is kept only if no later entry sets the same
  # key. Plain arrays, no associative ones, so this also runs on macOS's bash 3.2.
  local -a combined=("${BASE_ENV[@]}" "$@")
  local -a env_flags=()
  local index later superseded
  for ((index = 0; index < ${#combined[@]}; index++)); do
    superseded=0
    for ((later = index + 1; later < ${#combined[@]}; later++)); do
      if [[ "${combined[later]%%=*}" == "${combined[index]%%=*}" ]]; then
        superseded=1
      fi
    done
    if [[ "$superseded" == 0 ]]; then
      env_flags+=(-e "${combined[index]}")
    fi
  done
  docker exec "${env_flags[@]}" "$DB" bash /tmp/db-provision.sh
}

# Runs provision() and records its combined output and exit code without tripping `set -e`.
PROVISION_OUT=""
PROVISION_RC=0
run_provision() {
  if PROVISION_OUT="$(provision "$@" 2>&1)"; then
    PROVISION_RC=0
  else
    PROVISION_RC=$?
  fi
}

# Connects as the test role over TCP (scram); prints psql's output, returns its exit code.
connect_as_test_role() {
  local password=$1 database=$2
  docker exec -e PGPASSWORD="$password" "$DB" \
    psql -X -qtA -h db -U "$TEST_ROLE" -d "$database" -c "SELECT current_user" 2>&1
}

DB_STATE_SQL="SELECT string_agg(format('%s|%s|%s|%s', datname, pg_get_userbyid(datdba), datallowconn, datacl), ',' ORDER BY datname) FROM pg_database"
ROLE_STATE_SQL="SELECT string_agg(format('%s|%s|%s|%s|%s', rolname, rolcanlogin, rolcreatedb, rolsuper, rolconnlimit), ',' ORDER BY rolname) FROM pg_roles"
# Includes the scram hash: ALTER ROLE ... PASSWORD re-salts it, so any re-applied password shows.
FULL_STATE_SQL="SELECT ($DB_STATE_SQL) || ' / ' || (SELECT string_agg(format('%s|%s|%s', rolname, rolconnlimit, rolpassword), ',' ORDER BY rolname) FROM pg_authid)"

echo "Creating network $NET and volume $VOL"
docker network create "$NET" >/dev/null
NETWORK_CREATED=1
docker volume create "$VOL" >/dev/null
VOLUME_CREATED=1

echo "Starting throwaway Postgres $DB (alias db)"
# Set before `run`: it can create the container and then fail to start it, which still needs rm -f.
DB_STARTED=1
docker run -d \
  --network "$NET" --network-alias db \
  -v "$VOL":/var/lib/postgresql/data \
  -e POSTGRES_USER="$ADMIN" -e POSTGRES_PASSWORD="$PW1" -e POSTGRES_DB=postgres \
  --name "$DB" \
  postgres:16.3-bookworm >/dev/null

# TCP, not the socket: the image's first-init temp server is socket-only (see backup-pipeline-test.sh).
DB_READY=0
for _ in $(seq 1 60); do
  if docker exec "$DB" pg_isready -h 127.0.0.1 -U "$ADMIN" -d postgres >/dev/null 2>&1; then
    DB_READY=1
    break
  fi
  sleep 1
done
if [[ "$DB_READY" != 1 ]]; then
  docker logs "$DB" 2>&1 | tail -40 >&2 || true
  die "throwaway Postgres never became ready"
fi
docker cp "$SCRIPT_DIR/db-provision.sh" "$DB":/tmp/db-provision.sh

# --- (a) Fresh cluster ---
echo "-- Leg (a): fresh cluster --"
run_provision
expect_eq "(a) exit code" 0 "$PROVISION_RC"
expect_contains "(a) ready line" "db-provision: role $TEST_ROLE, dev database u4i_dev_fresh, test database $TEST_DB ready" "$PROVISION_OUT"
expect_eq "(a) role attributes (login|createdb|super|connlimit)" "t|t|f|25" \
  "$(sql postgres "SELECT format('%s|%s|%s|%s', rolcanlogin, rolcreatedb, rolsuper, rolconnlimit) FROM pg_roles WHERE rolname = '$TEST_ROLE'")"
expect_eq "(a) dev DB created" 1 "$(sql postgres "SELECT count(*) FROM pg_database WHERE datname = 'u4i_dev_fresh'")"
expect_eq "(a) PUBLIC CONNECT on dev DB" f "$(sql postgres "SELECT has_database_privilege('public', 'u4i_dev_fresh', 'CONNECT')")"
expect_eq "(a) base test DB owner" "$TEST_ROLE" "$(sql postgres "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = '$TEST_DB'")"
echo "Leg (a) PASSED"

# --- (b) Legacy rename ---
echo "-- Leg (b): legacy rename --"
sql postgres "CREATE DATABASE legacy_dev" >/dev/null
sql legacy_dev "CREATE TABLE marker (note text); INSERT INTO marker VALUES ('survives-rename')" >/dev/null
LEG_B_ENV=("LEGACY_DEV_DB=legacy_dev" "U4I_DEV_DB=u4i_dev_renamed")
run_provision "${LEG_B_ENV[@]}"
expect_eq "(b) exit code" 0 "$PROVISION_RC"
expect_contains "(b) rename logged" "db-provision: renamed legacy dev database legacy_dev to u4i_dev_renamed" "$PROVISION_OUT"
expect_not_contains "(b) no orphan warning" "WARNING orphaned" "$PROVISION_OUT"
expect_eq "(b) legacy DB gone" 0 "$(sql postgres "SELECT count(*) FROM pg_database WHERE datname = 'legacy_dev'")"
expect_eq "(b) marker data survives" survives-rename "$(sql u4i_dev_renamed "SELECT note FROM marker")"
expect_eq "(b) renamed DB accepts connections" t "$(sql postgres "SELECT datallowconn FROM pg_database WHERE datname = 'u4i_dev_renamed'")"
expect_eq "(b) PUBLIC CONNECT on renamed DB" f "$(sql postgres "SELECT has_database_privilege('public', 'u4i_dev_renamed', 'CONNECT')")"
echo "Leg (b) PASSED"

# --- (c) Idempotent re-run ---
echo "-- Leg (c): idempotent re-run --"
DB_STATE_BEFORE="$(sql postgres "$DB_STATE_SQL")"
ROLE_STATE_BEFORE="$(sql postgres "$ROLE_STATE_SQL")"
run_provision "${LEG_B_ENV[@]}"
expect_eq "(c) exit code" 0 "$PROVISION_RC"
expect_not_contains "(c) no second rename" "renamed legacy dev database" "$PROVISION_OUT"
expect_not_contains "(c) no orphan warning" "WARNING orphaned" "$PROVISION_OUT"
expect_eq "(c) databases unchanged" "$DB_STATE_BEFORE" "$(sql postgres "$DB_STATE_SQL")"
expect_eq "(c) roles unchanged" "$ROLE_STATE_BEFORE" "$(sql postgres "$ROLE_STATE_SQL")"
echo "Leg (c) PASSED"

# --- (c2) Orphaned legacy DB: U4I_DEV_DB already exists, so step 5 isolates the legacy DB instead ---
echo "-- Leg (c2): orphaned legacy DB --"
sql postgres "CREATE DATABASE legacy_orphan" >/dev/null
run_provision "LEGACY_DEV_DB=legacy_orphan" "U4I_DEV_DB=u4i_dev_renamed"
expect_eq "(c2) exit code" 0 "$PROVISION_RC"
expect_contains "(c2) orphan warning" "db-provision: WARNING orphaned legacy database legacy_orphan" "$PROVISION_OUT"
expect_not_contains "(c2) no rename" "renamed legacy dev database" "$PROVISION_OUT"
expect_eq "(c2) legacy DB kept" 1 "$(sql postgres "SELECT count(*) FROM pg_database WHERE datname = 'legacy_orphan'")"
expect_eq "(c2) PUBLIC CONNECT on legacy DB" f "$(sql postgres "SELECT has_database_privilege('public', 'legacy_orphan', 'CONNECT')")"
expect_eq "(c2) dev DB untouched" survives-rename "$(sql u4i_dev_renamed "SELECT note FROM marker")"
echo "Leg (c2) PASSED"

# --- (d) Re-apply: changed connection limit and password propagate ---
echo "-- Leg (d): re-apply connection limit and password --"
# .env's POSTGRES_PASSWORD is also the superuser's, so rotate the superuser first (over the socket).
sql postgres "ALTER ROLE $ADMIN PASSWORD '$PW2'" >/dev/null
LEG_D_ENV=("${LEG_B_ENV[@]}" "POSTGRES_PASSWORD=$PW2" "U4I_PG_TEST_CONN_LIMIT=40")
run_provision "${LEG_D_ENV[@]}"
expect_eq "(d) exit code" 0 "$PROVISION_RC"
expect_eq "(d) connection limit re-applied" 40 "$(sql postgres "SELECT rolconnlimit FROM pg_roles WHERE rolname = '$TEST_ROLE'")"
if ! TEST_ROLE_OUT="$(connect_as_test_role "$PW2" "$TEST_DB")"; then
  die "(d) test role could not log in with the new password: $TEST_ROLE_OUT"
fi
expect_eq "(d) new password logs in" "$TEST_ROLE" "$TEST_ROLE_OUT"
if TEST_ROLE_OUT="$(connect_as_test_role "$PW1" "$TEST_DB")"; then
  die "(d) test role still logs in with the old password"
fi
expect_contains "(d) old password rejected" "password authentication failed" "$TEST_ROLE_OUT"
echo "Leg (d) PASSED"

# --- (e) Isolation: the test role cannot reach the dev DB but can reach the base test DB ---
echo "-- Leg (e): test-role isolation --"
for dev_db in u4i_dev_renamed u4i_dev_fresh; do
  if TEST_ROLE_OUT="$(connect_as_test_role "$PW2" "$dev_db")"; then
    die "(e) test role connected to dev DB $dev_db"
  fi
  expect_contains "(e) refused on $dev_db" "permission denied for database" "$TEST_ROLE_OUT"
done
if ! TEST_ROLE_OUT="$(connect_as_test_role "$PW2" "$TEST_DB")"; then
  die "(e) test role could not connect to $TEST_DB: $TEST_ROLE_OUT"
fi
expect_eq "(e) base test DB reachable" "$TEST_ROLE" "$TEST_ROLE_OUT"
echo "Leg (e) PASSED"

# --- (f) Input guards reject bad input before any mutation ---
echo "-- Leg (f): input guards --"
# Otherwise-valid input aimed at a not-yet-existing dev DB, so a guard that let the run through
# would create it (and re-salt the role password), which the full-state fingerprint catches.
GUARD_ENV=("POSTGRES_PASSWORD=$PW2" "U4I_PG_TEST_CONN_LIMIT=40" "U4I_DEV_DB=u4i_dev_guard")
check_guard() {
  local expected_message=$1
  shift
  local state_before
  state_before="$(sql postgres "$FULL_STATE_SQL")"
  run_provision "${GUARD_ENV[@]}" "$@"
  [[ "$PROVISION_RC" != 0 ]] || die "(f) guard [$*] exited 0"
  expect_contains "(f) guard [$*] message" "$expected_message" "$PROVISION_OUT"
  expect_eq "(f) guard [$*] left the cluster untouched" "$state_before" "$(sql postgres "$FULL_STATE_SQL")"
}
check_guard "POSTGRES_DB and POSTGRES_TEST_DB are both" "LEGACY_DEV_DB=$TEST_DB"
check_guard "must not start with 'pg_'" "U4I_TEST_ROLE=pg_u4i_test"
check_guard "U4I_PG_TEST_CONN_LIMIT must be a non-negative integer" "U4I_PG_TEST_CONN_LIMIT=abc"
check_guard "U4I_PG_TEST_CONN_LIMIT must be a non-negative integer" "U4I_PG_TEST_CONN_LIMIT=-1"
check_guard "U4I_PG_TEST_CONN_LIMIT must be a non-negative integer" "U4I_PG_TEST_CONN_LIMIT=123456"
check_guard "must not be a system database" "POSTGRES_TEST_DB=postgres"
check_guard "must not be a system database" "POSTGRES_TEST_DB=template1"
check_guard "U4I_TEST_ROLE must differ from POSTGRES_USER" "U4I_TEST_ROLE=$ADMIN"
check_guard "POSTGRES_TEST_DB must differ from U4I_DEV_DB" "POSTGRES_TEST_DB=u4i_dev_guard"
check_guard "U4I_DEV_DB is required" "U4I_DEV_DB="
echo "Leg (f) PASSED"

# --- (g) Failure after the rename: the recovery pass re-allows connections on U4I_DEV_DB ---
# Nothing between step 2's rename and step 4's `ALLOW_CONNECTIONS true` can fail on its own, so the
# harness single-steps the script with lock queueing: every statement that writes pg_database takes
# RowExclusiveLock on it, and a SHARE lock queued behind a waiting statement is granted as soon as
# that statement commits. Holder h1 parks the script at step 2's `ALLOW_CONNECTIONS false`; h2,
# queued behind it, parks it at the RENAME; h3, queued behind the RENAME, parks it at step 4 with
# the rename committed and the dev DB still blocked. Cancelling that step-4 statement fails the run
# at exactly the point where only the recovery pass can make the renamed DB connectable again.
echo "-- Leg (g): recovery after a post-rename failure --"
LEG_G_APP=u4i_dbprov_leg_g
LEG_G_OUT="$WORK_DIR/leg_g.out"
sql postgres "CREATE DATABASE legacy_g" >/dev/null
sql legacy_g "CREATE TABLE marker (note text); INSERT INTO marker VALUES ('leg-g')" >/dev/null

start_lock_holder() {
  docker exec -e PGAPPNAME="$1" "$DB" psql -X -q -U "$ADMIN" -d postgres \
    -c "BEGIN; LOCK TABLE pg_catalog.pg_database IN SHARE MODE; SELECT pg_sleep(600);" >/dev/null 2>&1 &
}
holder_lock_sql() {
  local holder=$1 granted=$2
  echo "SELECT EXISTS (SELECT FROM pg_locks JOIN pg_stat_activity USING (pid)
    WHERE application_name = '$holder' AND locktype = 'relation'
      AND relation = 'pg_catalog.pg_database'::regclass AND mode = 'ShareLock' AND granted = $granted)"
}
release_holder() {
  sql postgres "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = '$1'" >/dev/null
}
script_waiting_sql() {
  echo "SELECT EXISTS (SELECT FROM pg_stat_activity
    WHERE application_name = '$LEG_G_APP' AND wait_event_type = 'Lock' AND query LIKE '%$1%')"
}

start_lock_holder u4i_dbprov_h1
wait_for "h1 to hold the pg_database lock" "$(holder_lock_sql u4i_dbprov_h1 true)"
provision "${GUARD_ENV[@]}" "PGAPPNAME=$LEG_G_APP" "LEGACY_DEV_DB=legacy_g" "U4I_DEV_DB=u4i_dev_g" >"$LEG_G_OUT" 2>&1 &
LEG_G_PID=$!
wait_for "the script to block at step 2's ALLOW_CONNECTIONS false" "$(script_waiting_sql "legacy_g ALLOW_CONNECTIONS false")"

start_lock_holder u4i_dbprov_h2
wait_for "h2 to queue behind the script" "$(holder_lock_sql u4i_dbprov_h2 false)"
release_holder u4i_dbprov_h1
wait_for "the script to block at the RENAME" "$(script_waiting_sql "RENAME TO u4i_dev_g")"

start_lock_holder u4i_dbprov_h3
wait_for "h3 to queue behind the RENAME" "$(holder_lock_sql u4i_dbprov_h3 false)"
release_holder u4i_dbprov_h2
wait_for "the script to block at step 4's ALLOW_CONNECTIONS true" "$(script_waiting_sql "\"u4i_dev_g\" ALLOW_CONNECTIONS true")"

# The state the failure strands: renamed, but still blocked. Without recovery it would stay so.
expect_eq "(g) legacy DB renamed away before the failure" 0 "$(sql postgres "SELECT count(*) FROM pg_database WHERE datname = 'legacy_g'")"
expect_eq "(g) renamed DB blocked before the failure" f "$(sql postgres "SELECT datallowconn FROM pg_database WHERE datname = 'u4i_dev_g'")"

STEP4_PID="$(sql postgres "SELECT pid FROM pg_stat_activity
  WHERE application_name = '$LEG_G_APP' AND wait_event_type = 'Lock' AND query LIKE '%\"u4i_dev_g\" ALLOW_CONNECTIONS true%'")"
[[ "$STEP4_PID" =~ ^[0-9]+$ ]] || die "(g) expected one step-4 backend pid, got '$STEP4_PID'"
sql postgres "SELECT pg_cancel_backend($STEP4_PID)" >/dev/null
# Only release h3 once the cancelled backend is gone, so step 4 can never slip through instead.
wait_for "the cancelled step-4 backend to exit" "SELECT NOT EXISTS (SELECT FROM pg_stat_activity WHERE pid = $STEP4_PID)"
release_holder u4i_dbprov_h3

if wait "$LEG_G_PID"; then
  LEG_G_RC=0
else
  LEG_G_RC=$?
fi
LEG_G_LOG="$(cat "$LEG_G_OUT")"
expect_eq "(g) exit code" 1 "$LEG_G_RC"
expect_contains "(g) rename logged" "db-provision: renamed legacy dev database legacy_g to u4i_dev_g" "$LEG_G_LOG"
expect_contains "(g) step 4 was the failure" "canceling statement due to user request" "$LEG_G_LOG"
expect_contains "(g) recovery ran" "db-provision: provisioning failed; re-allowing connections" "$LEG_G_LOG"
expect_not_contains "(g) recovery pass itself succeeded" "recovery pass failed" "$LEG_G_LOG"
expect_eq "(g) renamed DB connectable after recovery" t "$(sql postgres "SELECT datallowconn FROM pg_database WHERE datname = 'u4i_dev_g'")"
expect_eq "(g) marker data survives" leg-g "$(sql u4i_dev_g "SELECT note FROM marker")"
echo "Leg (g) PASSED"

echo "ALL DB-PROVISION LEGS PASSED"
