#!/usr/bin/env bash
#
# End-to-end test harness for docker/db-provision.sh (the hub's `cluster-init` and each spoke's
# `db-init` one-shot).
#
# Usage: db-provision-test.sh   (normally via `make test-db-provision`)
#
# Runs the real script against THROWAWAY postgres:16.3-bookworm containers on their own uniquely
# named network and named volumes, all removed on exit by one `trap cleanup EXIT` (modeled on
# docker/backup-pipeline-test.sh). It never touches the hub's `db` container, its `pgdata` volume,
# or any real dev database.
#
# The script is copied into the throwaway container and run there with PGHOST=db (the container's
# own network alias), so it authenticates over TCP with scram-sha-256 exactly as `db-init` does.
# Assertions connect as the superuser over the local socket.
#
# Legs:
#   (a) fresh cluster (cluster, then spoke)     (c) idempotent re-run
#   (d) re-applied limit/pw (cluster)           (e) test-role isolation
#   (f) input guards per scope, before any mutation
#   (h) cluster scope creates no dev DB         (i) spoke scope leaves the role untouched
#   (j) readiness wait against a container still in its socket-only first-init phase
#   (k) two spokes concurrently                 (l) two cluster provisions serialized by the advisory lock
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

RUN_ID="$$_${RANDOM}"
NET="u4i_dbprov_test_net_${RUN_ID}"
DB="u4i_dbprov_test_db_${RUN_ID}"
VOL="u4i_dbprov_test_vol_${RUN_ID}"
DB_J="u4i_dbprov_test_db_j_${RUN_ID}"
VOL_J="u4i_dbprov_test_vol_j_${RUN_ID}"

ADMIN=u4i_admin
PW1=provision-pw-1
PW2=provision-pw-2
TEST_ROLE=u4i_test
TEST_DB=u4i_test_base
CLUSTER_LOCK_SQL="pg_advisory_lock(hashtext('u4i-cluster-provision'))"

NETWORK_CREATED=0
VOLUME_CREATED=0
DB_STARTED=0
VOLUME_J_CREATED=0
DB_J_STARTED=0
WORK_DIR="$(mktemp -d)"

cleanup() {
  echo "Cleaning up..."
  # Background psql clients (legs j/k/l) exit once their container is gone; kill any stragglers anyway.
  local job_pid
  for job_pid in $(jobs -p); do
    kill "$job_pid" >/dev/null 2>&1 || true
  done
  if [[ "$DB_STARTED" == 1 ]]; then docker rm -f "$DB" >/dev/null 2>&1 || true; fi
  if [[ "$DB_J_STARTED" == 1 ]]; then docker rm -f "$DB_J" >/dev/null 2>&1 || true; fi
  if [[ "$NETWORK_CREATED" == 1 ]]; then docker network rm "$NET" >/dev/null 2>&1 || true; fi
  if [[ "$VOLUME_CREATED" == 1 ]]; then docker volume rm "$VOL" >/dev/null 2>&1 || true; fi
  if [[ "$VOLUME_J_CREATED" == 1 ]]; then docker volume rm "$VOL_J" >/dev/null 2>&1 || true; fi
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
# No U4I_PROVISION_SCOPE: every run names its scope explicitly.
BASE_ENV=(
  "PGHOST=db"
  "POSTGRES_USER=$ADMIN"
  "POSTGRES_PASSWORD=$PW1"
  "POSTGRES_TEST_DB=$TEST_DB"
  "U4I_DEV_DB=u4i_dev_fresh"
  "U4I_TEST_ROLE=$TEST_ROLE"
  "U4I_PG_TEST_CONN_LIMIT=25"
)

# Runs the script inside container $1 (which must hold /tmp/db-provision.sh).
provision_in() {
  local container=$1
  shift
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
  docker exec "${env_flags[@]}" "$container" bash /tmp/db-provision.sh
}

provision() {
  provision_in "$DB" "$@"
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

# Waits for background job $1 and records its exit code in JOB_RC, without tripping `set -e`. Never call
# it inside $(…): a subshell cannot `wait` on the parent's jobs.
JOB_RC=0
wait_job() {
  if wait "$1"; then
    JOB_RC=0
  else
    JOB_RC=$?
  fi
}

# Connects as the test role over TCP (scram); prints psql's output, returns its exit code.
connect_as_test_role() {
  local password=$1 database=$2
  docker exec -e PGPASSWORD="$password" "$DB" \
    psql -X -qtA -h db -U "$TEST_ROLE" -d "$database" -c "SELECT current_user" 2>&1
}

# Session that takes the cluster-provision advisory lock and then sleeps, so cluster runs queue behind it.
start_lock_holder() {
  docker exec -e PGAPPNAME="$1" "$DB" psql -X -q -U "$ADMIN" -d postgres \
    -c "SELECT $CLUSTER_LOCK_SQL; SELECT pg_sleep(600);" >/dev/null 2>&1 &
}
# True once exactly $2 sessions whose application_name matches the LIKE pattern $1 hold (granted=$3)
# or wait for (granted=false) an advisory lock.
advisory_lock_sql() {
  local app_pattern=$1 expected_count=$2 granted=$3
  echo "SELECT count(*) = $expected_count FROM pg_locks JOIN pg_stat_activity USING (pid)
    WHERE application_name LIKE '$app_pattern' AND locktype = 'advisory' AND granted = $granted"
}
release_holder() {
  sql postgres "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = '$1'" >/dev/null
}

DB_STATE_SQL="SELECT string_agg(format('%s|%s|%s|%s', datname, pg_get_userbyid(datdba), datallowconn, datacl), ',' ORDER BY datname) FROM pg_database"
ROLE_STATE_SQL="SELECT string_agg(format('%s|%s|%s|%s|%s', rolname, rolcanlogin, rolcreatedb, rolsuper, rolconnlimit), ',' ORDER BY rolname) FROM pg_roles"
# Includes the scram hash: ALTER ROLE ... PASSWORD re-salts it, so any re-applied password shows.
FULL_STATE_SQL="SELECT ($DB_STATE_SQL) || ' / ' || (SELECT string_agg(format('%s|%s|%s', rolname, rolconnlimit, rolpassword), ',' ORDER BY rolname) FROM pg_authid)"
TEST_ROLE_FINGERPRINT_SQL="SELECT format('%s|%s', rolconnlimit, rolpassword) FROM pg_authid WHERE rolname = '$TEST_ROLE'"
DEV_DBS_SQL="SELECT coalesce(string_agg(datname, ',' ORDER BY datname), '') FROM pg_database WHERE datname LIKE 'u4i\_dev\_%'"

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

# --- (a) Fresh cluster: cluster scope, then spoke scope ---
echo "-- Leg (a): fresh cluster --"
run_provision "U4I_PROVISION_SCOPE=cluster"
expect_eq "(a) cluster exit code" 0 "$PROVISION_RC"
expect_contains "(a) cluster ready line" "db-provision: role $TEST_ROLE and test database $TEST_DB ready" "$PROVISION_OUT"
run_provision "U4I_PROVISION_SCOPE=spoke"
expect_eq "(a) spoke exit code" 0 "$PROVISION_RC"
expect_contains "(a) spoke ready line" "db-provision: dev database u4i_dev_fresh ready" "$PROVISION_OUT"
expect_eq "(a) role attributes (login|createdb|super|connlimit)" "t|t|f|25" \
  "$(sql postgres "SELECT format('%s|%s|%s|%s', rolcanlogin, rolcreatedb, rolsuper, rolconnlimit) FROM pg_roles WHERE rolname = '$TEST_ROLE'")"
expect_eq "(a) dev DB created" 1 "$(sql postgres "SELECT count(*) FROM pg_database WHERE datname = 'u4i_dev_fresh'")"
expect_eq "(a) PUBLIC CONNECT on dev DB" f "$(sql postgres "SELECT has_database_privilege('public', 'u4i_dev_fresh', 'CONNECT')")"
expect_eq "(a) base test DB owner" "$TEST_ROLE" "$(sql postgres "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = '$TEST_DB'")"
echo "Leg (a) PASSED"

# --- (c) Idempotent re-run ---
echo "-- Leg (c): idempotent re-run --"
DB_STATE_BEFORE="$(sql postgres "$DB_STATE_SQL")"
ROLE_STATE_BEFORE="$(sql postgres "$ROLE_STATE_SQL")"
run_provision "U4I_PROVISION_SCOPE=cluster"
expect_eq "(c) cluster exit code" 0 "$PROVISION_RC"
run_provision "U4I_PROVISION_SCOPE=spoke"
expect_eq "(c) spoke exit code" 0 "$PROVISION_RC"
expect_eq "(c) databases unchanged" "$DB_STATE_BEFORE" "$(sql postgres "$DB_STATE_SQL")"
expect_eq "(c) roles unchanged" "$ROLE_STATE_BEFORE" "$(sql postgres "$ROLE_STATE_SQL")"
echo "Leg (c) PASSED"

# --- (d) Re-apply: changed connection limit and password propagate ---
echo "-- Leg (d): re-apply connection limit and password --"
# .env's POSTGRES_PASSWORD is also the superuser's, so rotate the superuser first (over the socket).
sql postgres "ALTER ROLE $ADMIN PASSWORD '$PW2'" >/dev/null
LEG_D_ENV=("POSTGRES_PASSWORD=$PW2" "U4I_PG_TEST_CONN_LIMIT=40")
run_provision "${LEG_D_ENV[@]}" "U4I_PROVISION_SCOPE=cluster"
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
run_provision "${LEG_D_ENV[@]}" "U4I_PROVISION_SCOPE=cluster"
expect_eq "(e) cluster exit code" 0 "$PROVISION_RC"
run_provision "${LEG_D_ENV[@]}" "U4I_PROVISION_SCOPE=spoke"
expect_eq "(e) spoke exit code" 0 "$PROVISION_RC"
if TEST_ROLE_OUT="$(connect_as_test_role "$PW2" u4i_dev_fresh)"; then
  die "(e) test role connected to dev DB u4i_dev_fresh"
fi
expect_contains "(e) refused on u4i_dev_fresh" "permission denied for database" "$TEST_ROLE_OUT"
if ! TEST_ROLE_OUT="$(connect_as_test_role "$PW2" "$TEST_DB")"; then
  die "(e) test role could not connect to $TEST_DB: $TEST_ROLE_OUT"
fi
expect_eq "(e) base test DB reachable" "$TEST_ROLE" "$TEST_ROLE_OUT"
echo "Leg (e) PASSED"

# --- (f) Input guards reject bad input before any mutation ---
echo "-- Leg (f): input guards --"
# Otherwise-valid input aimed at a not-yet-existing dev DB, so a guard that let the run through
# would create it (spoke) or re-salt the role password (cluster), which the full-state fingerprint catches.
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
check_guard "must not start with 'pg_'" "U4I_PROVISION_SCOPE=cluster" "U4I_TEST_ROLE=pg_u4i_test"
check_guard "U4I_PG_TEST_CONN_LIMIT must be a non-negative integer" "U4I_PROVISION_SCOPE=cluster" "U4I_PG_TEST_CONN_LIMIT=abc"
check_guard "U4I_PG_TEST_CONN_LIMIT must be a non-negative integer" "U4I_PROVISION_SCOPE=cluster" "U4I_PG_TEST_CONN_LIMIT=-1"
check_guard "U4I_PG_TEST_CONN_LIMIT must be a non-negative integer" "U4I_PROVISION_SCOPE=cluster" "U4I_PG_TEST_CONN_LIMIT=123456"
check_guard "must not be a system database" "U4I_PROVISION_SCOPE=cluster" "POSTGRES_TEST_DB=postgres"
check_guard "must not be a system database" "U4I_PROVISION_SCOPE=cluster" "POSTGRES_TEST_DB=template1"
check_guard "U4I_TEST_ROLE must differ from POSTGRES_USER" "U4I_PROVISION_SCOPE=cluster" "U4I_TEST_ROLE=$ADMIN"
check_guard "POSTGRES_TEST_DB is required" "U4I_PROVISION_SCOPE=cluster" "POSTGRES_TEST_DB="
check_guard "POSTGRES_TEST_DB must differ from U4I_DEV_DB" "U4I_PROVISION_SCOPE=spoke" "POSTGRES_TEST_DB=u4i_dev_guard"
check_guard "U4I_DEV_DB is required" "U4I_PROVISION_SCOPE=spoke" "U4I_DEV_DB="
check_guard "POSTGRES_TEST_DB is required" "U4I_PROVISION_SCOPE=spoke" "POSTGRES_TEST_DB="
check_guard "U4I_PROVISION_SCOPE must be 'cluster' or 'spoke', got 'bogus'" "U4I_PROVISION_SCOPE=bogus"
check_guard "U4I_PROVISION_SCOPE must be 'cluster' or 'spoke', got ''" "U4I_PROVISION_SCOPE="
echo "Leg (f) PASSED"

# --- (h) Cluster scope provisions the role and base test DB, and never a dev DB ---
echo "-- Leg (h): cluster scope creates no dev DB --"
DEV_DBS_BEFORE="$(sql postgres "$DEV_DBS_SQL")"
run_provision "POSTGRES_PASSWORD=$PW2" "U4I_PROVISION_SCOPE=cluster" "U4I_DEV_DB=" \
  "U4I_TEST_ROLE=u4i_h_role" "POSTGRES_TEST_DB=u4i_h_test" "U4I_PG_TEST_CONN_LIMIT=12"
expect_eq "(h) exit code" 0 "$PROVISION_RC"
expect_eq "(h) role connection limit" 12 "$(sql postgres "SELECT rolconnlimit FROM pg_roles WHERE rolname = 'u4i_h_role'")"
expect_eq "(h) base test DB owner" u4i_h_role "$(sql postgres "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = 'u4i_h_test'")"
expect_eq "(h) no dev DB created" "$DEV_DBS_BEFORE" "$(sql postgres "$DEV_DBS_SQL")"
sql postgres "DROP DATABASE u4i_h_test" >/dev/null
sql postgres "DROP ROLE u4i_h_role" >/dev/null
echo "Leg (h) PASSED"

# --- (i) Spoke scope creates and isolates its dev DB, leaving the test role untouched ---
echo "-- Leg (i): spoke scope leaves the role untouched --"
ROLE_FINGERPRINT_BEFORE="$(sql postgres "$TEST_ROLE_FINGERPRINT_SQL")"
# A different limit proves spoke scope ignores it rather than re-applying it.
run_provision "POSTGRES_PASSWORD=$PW2" "U4I_PROVISION_SCOPE=spoke" "U4I_DEV_DB=u4i_dev_spoke_a" "U4I_PG_TEST_CONN_LIMIT=99"
expect_eq "(i) exit code" 0 "$PROVISION_RC"
expect_eq "(i) dev DB created" 1 "$(sql postgres "SELECT count(*) FROM pg_database WHERE datname = 'u4i_dev_spoke_a'")"
expect_eq "(i) PUBLIC CONNECT on dev DB" f "$(sql postgres "SELECT has_database_privilege('public', 'u4i_dev_spoke_a', 'CONNECT')")"
expect_eq "(i) role limit and password hash untouched" "$ROLE_FINGERPRINT_BEFORE" "$(sql postgres "$TEST_ROLE_FINGERPRINT_SQL")"
echo "Leg (i) PASSED"

# --- (j) Readiness wait: the script waits out a container still in its socket-only first-init phase ---
echo "-- Leg (j): readiness wait --"
# Every /docker-entrypoint-initdb.d/*.sh is sourced while the temp server is socket-only, so this
# keeps TCP closed for at least 8s after init starts: a deterministic window, not a race with initdb.
printf 'sleep 8\n' >"$WORK_DIR/00-slow-init.sh"
chmod 0644 "$WORK_DIR/00-slow-init.sh"
docker volume create "$VOL_J" >/dev/null
VOLUME_J_CREATED=1
DB_J_STARTED=1
# Alias db-j, distinct from db, so the first container is never reached. Deliberately not polled.
docker run -d \
  --network "$NET" --network-alias db-j \
  -v "$VOL_J":/var/lib/postgresql/data \
  -v "$WORK_DIR/00-slow-init.sh":/docker-entrypoint-initdb.d/00-slow-init.sh:ro \
  -e POSTGRES_USER="$ADMIN" -e POSTGRES_PASSWORD="$PW1" -e POSTGRES_DB=postgres \
  --name "$DB_J" \
  postgres:16.3-bookworm >/dev/null
docker cp "$SCRIPT_DIR/db-provision.sh" "$DB_J":/tmp/db-provision.sh
# Cluster scope: this fresh cluster has no test role yet. PW1 matches its superuser (leg d rotated only $DB's).
provision_in "$DB_J" "U4I_PROVISION_SCOPE=cluster" "PGHOST=db-j" "POSTGRES_PASSWORD=$PW1" >"$WORK_DIR/leg_j.out" 2>&1 &
LEG_J_PID=$!
wait_job "$LEG_J_PID"
LEG_J_LOG="$(cat "$WORK_DIR/leg_j.out")"
[[ "$JOB_RC" == 0 ]] || die "(j) exit code: expected 0, got $JOB_RC. Output was:
$LEG_J_LOG"
expect_contains "(j) waited for the db" "db-provision: waiting for db-j" "$LEG_J_LOG"
expect_eq "(j) test role and base test DB exist" "1|1" \
  "$(docker exec "$DB_J" psql -X -v ON_ERROR_STOP=1 -qtA -U "$ADMIN" -d postgres -c \
    "SELECT format('%s|%s', (SELECT count(*) FROM pg_roles WHERE rolname = '$TEST_ROLE'), (SELECT count(*) FROM pg_database WHERE datname = '$TEST_DB'))")"
docker rm -f "$DB_J" >/dev/null
DB_J_STARTED=0
docker volume rm "$VOL_J" >/dev/null
VOLUME_J_CREATED=0
echo "Leg (j) PASSED"

# --- (k) Two spokes provisioning concurrently ---
echo "-- Leg (k): two spokes concurrently --"
provision "POSTGRES_PASSWORD=$PW2" "U4I_PROVISION_SCOPE=spoke" "U4I_DEV_DB=u4i_dev_k1" >"$WORK_DIR/leg_k1.out" 2>&1 &
LEG_K1_PID=$!
provision "POSTGRES_PASSWORD=$PW2" "U4I_PROVISION_SCOPE=spoke" "U4I_DEV_DB=u4i_dev_k2" >"$WORK_DIR/leg_k2.out" 2>&1 &
LEG_K2_PID=$!
wait_job "$LEG_K1_PID"
[[ "$JOB_RC" == 0 ]] || die "(k) first spoke exited $JOB_RC: $(cat "$WORK_DIR/leg_k1.out")"
wait_job "$LEG_K2_PID"
[[ "$JOB_RC" == 0 ]] || die "(k) second spoke exited $JOB_RC: $(cat "$WORK_DIR/leg_k2.out")"
expect_eq "(k) both dev DBs exist" 2 "$(sql postgres "SELECT count(*) FROM pg_database WHERE datname IN ('u4i_dev_k1', 'u4i_dev_k2')")"
echo "Leg (k) PASSED"

# --- (l) Two cluster provisions at once serialize on the advisory lock ---
echo "-- Leg (l): two cluster provisions concurrently --"
# A role and base test DB that don't exist yet, so both runs reach the CREATE path. The holder
# parks both runs on the lock, then releases them together: without the lock, the loser of the
# NOT EXISTS ... \gexec race would fail with duplicate_object.
LEG_L_ENV=("POSTGRES_PASSWORD=$PW2" "U4I_PROVISION_SCOPE=cluster" "U4I_TEST_ROLE=u4i_race" "POSTGRES_TEST_DB=u4i_race_test")
start_lock_holder u4i_dbprov_l_holder
wait_for "the holder to take the advisory lock" "$(advisory_lock_sql u4i_dbprov_l_holder 1 true)"
provision "${LEG_L_ENV[@]}" "PGAPPNAME=u4i_dbprov_l_run1" >"$WORK_DIR/leg_l1.out" 2>&1 &
LEG_L1_PID=$!
provision "${LEG_L_ENV[@]}" "PGAPPNAME=u4i_dbprov_l_run2" >"$WORK_DIR/leg_l2.out" 2>&1 &
LEG_L2_PID=$!
wait_for "both cluster runs to wait on the advisory lock" "$(advisory_lock_sql 'u4i_dbprov_l_run%' 2 false)"
release_holder u4i_dbprov_l_holder
wait_job "$LEG_L1_PID"
[[ "$JOB_RC" == 0 ]] || die "(l) first cluster run exited $JOB_RC: $(cat "$WORK_DIR/leg_l1.out")"
wait_job "$LEG_L2_PID"
[[ "$JOB_RC" == 0 ]] || die "(l) second cluster run exited $JOB_RC: $(cat "$WORK_DIR/leg_l2.out")"
expect_eq "(l) one role" 1 "$(sql postgres "SELECT count(*) FROM pg_roles WHERE rolname = 'u4i_race'")"
expect_eq "(l) one base test DB" 1 "$(sql postgres "SELECT count(*) FROM pg_database WHERE datname = 'u4i_race_test'")"
sql postgres "DROP DATABASE u4i_race_test" >/dev/null
sql postgres "DROP ROLE u4i_race" >/dev/null
echo "Leg (l) PASSED"

echo "ALL DB-PROVISION LEGS PASSED"
