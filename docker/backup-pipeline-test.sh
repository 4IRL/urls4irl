#!/usr/bin/env bash
#
# End-to-end test harness for the workflow container's daily backup pipeline.
#
# Usage: backup-pipeline-test.sh <provision-image> <workflow-image>
#   <provision-image>  an image with Flask + migrations + addmock (u4i-prod /
#                      u4i-local-web) — used ONLY to install the REAL u4i schema
#                      (flask db upgrade) and seed it (flask addmock all).
#   <workflow-image>   the workflow image (u4i-workflow) that ships the backup
#                      bash scripts + pg_dump/rclone — the actual code under test.
#
# Modeled on docker/smoke-test.sh: a single user-defined network, sidecars via
# `docker run`, one cleanup() behind one `trap cleanup EXIT`. Self-provisions its
# own Postgres sidecar, so no CI `services:` block is required. Real R2 / Discord
# are never contacted (the rclone leg stubs the binary inside the driver).
set -e

PROVISION_IMAGE=$1
WORKFLOW_IMAGE=$2
if [ -z "${PROVISION_IMAGE:-}" ] || [ -z "${WORKFLOW_IMAGE:-}" ]; then
  echo "usage: $0 <provision-image> <workflow-image>" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

NET=backup_test_net
DB=backup_test_db
MAIN=backup_test_main
GUARD=backup_test_guard
S3=backup_test_s3
PRODSIM=backup_test_prodsim

# The S3 sidecar speaks the same API as Cloudflare R2, so pointing the real,
# un-stubbed rclone at it exercises the production upload code path hermetically.
S3_USER=s3admin
S3_PASS=s3admin123
S3_ENDPOINT=http://s3:9000

SECRETS_VOL=backup_test_secrets

NETWORK_CREATED=0
DB_STARTED=""
MAIN_STARTED=""
GUARD_STARTED=""
S3_STARTED=""
PRODSIM_STARTED=""
SECRETS_VOL_CREATED=""
# Fresh per-leg containers for the heartbeat legs (space-separated names).
LEG_CONTAINERS=""

cleanup() {
  echo "🧹 Cleaning up..."
  for leg_container in $LEG_CONTAINERS; do
    docker rm -f "$leg_container" >/dev/null 2>&1 || true
  done
  [ -n "$MAIN_STARTED" ] && docker rm -f "$MAIN" >/dev/null 2>&1 || true
  [ -n "$GUARD_STARTED" ] && docker rm -f "$GUARD" >/dev/null 2>&1 || true
  [ -n "$PRODSIM_STARTED" ] && docker rm -f "$PRODSIM" >/dev/null 2>&1 || true
  [ -n "$S3_STARTED" ] && docker rm -f "$S3" >/dev/null 2>&1 || true
  [ -n "$DB_STARTED" ] && docker rm -f "$DB" >/dev/null 2>&1 || true
  [ "$NETWORK_CREATED" = "1" ] && docker network rm "$NET" >/dev/null 2>&1 || true
  [ -n "$SECRETS_VOL_CREATED" ] && docker volume rm "$SECRETS_VOL" >/dev/null 2>&1 || true
}
trap cleanup EXIT

wait_for_env_file() {
  local container_name=$1
  for _ in $(seq 1 10); do
    docker exec "$container_name" test -f /app/container_environment && return 0
    sleep 1
  done
  docker exec "$container_name" test -f /app/container_environment
}

# Today's daily-docker.sh log of a container (empty when absent).
daily_log() {
  docker exec "$1" cat "/app/workflow_logs/$(docker exec "$1" date +%Y_%m_%d)-daily-workflow-logs.txt" 2>/dev/null || echo ""
}

# Assert a log holds exactly ONE daily_backup heartbeat line and that it matches a
# pattern. $1 = leg label, $2 = log text, $3 = ERE the single line must match.
assert_one_heartbeat_line() {
  local label=$1 log_text=$2 pattern=$3 total matching
  total=$(echo "$log_text" | grep -c "notifs_hub lane=heartbeat check=daily_backup" || true)
  matching=$(echo "$log_text" | grep -cE "notifs_hub lane=heartbeat check=daily_backup .*${pattern}" || true)
  if [ "$total" != "1" ] || [ "$matching" != "1" ]; then
    echo "❌ $label: expected exactly one heartbeat line matching '${pattern}' (total=$total matching=$matching)" >&2
    echo "$log_text" | grep "notifs_hub" >&2 || true
    exit 1
  fi
}

# Start a fresh workflow container for a heartbeat leg: /backups + yesterday's
# log in place, Discord notifier stubbed, and a cron-like env dump written with
# PRODUCTION=true, an unreachable hub and NO key directory. $1 = name, $2 = the
# Postgres password to put in the dump (a wrong one makes the DB backup fail).
start_heartbeat_leg_container() {
  local name=$1 db_password=$2
  docker run -d \
    --network "$NET" --no-healthcheck \
    -e POSTGRES_USER=bob -e POSTGRES_DB=test -e POSTGRES_PASSWORD=test \
    -e POSTGRES_HOST=db -e POSTGRES_PORT=5432 \
    -e METRICS_FLUSH_LIVENESS_THRESHOLD_SECONDS=180 \
    --name "$name" \
    "$WORKFLOW_IMAGE" >/dev/null
  LEG_CONTAINERS="$LEG_CONTAINERS $name"
  wait_for_env_file "$name" || {
    echo "❌ /app/container_environment not written in $name" >&2
    exit 1
  }
  docker exec "$name" mkdir -p /backups /app/volume/logs
  docker exec "$name" chown -R 1001:1001 /backups /app/volume
  docker exec -u 1001 "$name" bash -c 'printf "leg log line\n" > "/app/volume/logs/$(date -d yesterday +%Y-%m-%d)_daily.log"'
  docker exec "$name" bash -c 'printf "#!/bin/bash\nexit 0\n" > /usr/bin/restricted_curl && chmod +x /usr/bin/restricted_curl'
  docker exec -u 1001 "$name" bash -c "printf 'POSTGRES_USER=bob\nPOSTGRES_PASSWORD=${db_password}\nPOSTGRES_DB=test\nPOSTGRES_HOST=db\nPOSTGRES_PORT=5432\nPRODUCTION=true\nNOTIFS_BASE_URL=http://127.0.0.1:9\nNOTIFS_KEY_DIR=/nonexistent\n' > /app/container_environment"
}

echo "🌐 Creating network $NET"
docker network create "$NET" >/dev/null
NETWORK_CREATED=1

# --- Postgres sidecar (alias `db` — the backup scripts default to `-h "${POSTGRES_HOST:-db}"`) ---
echo "🐘 Starting Postgres sidecar (alias db)"
DB_STARTED=$(docker run -d \
  --network "$NET" --network-alias db \
  -e POSTGRES_USER=bob -e POSTGRES_DB=test -e POSTGRES_PASSWORD=test \
  --name "$DB" \
  postgres:16.3-bookworm)

echo "⏳ Waiting for Postgres to accept TCP connections..."
# Check TCP (-h 127.0.0.1), NOT the default local unix socket. The postgres image's
# first-init boots a TEMPORARY socket-only server to run initdb/init scripts, then
# shuts it down and restarts the real server. A socket `pg_isready` reports "ready"
# during that temp phase, so a socket-based loop breaks early — and a single-shot
# final check then lands in the brief gap while the temp server is stopping before
# the real one is up, printing "never became ready" in ~1s despite the 30-iteration
# loop (a first-init race, flaky by timing). The temp server never binds TCP, so a
# TCP `pg_isready` only succeeds once the REAL server is up — no race. We also loop
# a single readiness flag (no separate single-shot final check) and dump the
# container logs on failure to make any genuine startup error diagnosable.
DB_READY=0
for _ in $(seq 1 60); do
  if docker exec "$DB" pg_isready -h 127.0.0.1 -U bob -d test >/dev/null 2>&1; then
    DB_READY=1
    break
  fi
  sleep 1
done
if [ "$DB_READY" != 1 ]; then
  echo "❌ Postgres sidecar never became ready" >&2
  docker logs "$DB" 2>&1 | tail -40 >&2 || true
  exit 1
fi

# --- S3-compatible sidecar (Versity S3 Gateway) + buckets for the real-upload legs ---
# versitygw replaced MinIO: MinIO archived its open-source edition and withdrew
# its public images (Docker Hub on 2026-09-12, then quay.io began refusing
# anonymous pulls with "unauthorized" on 2026-09-24), so no MinIO tag is pullable.
# versitygw's posix backend serves a plain directory over the S3 API, with root
# creds via env vars. Pinned to a release tag (not :latest) so an upstream move
# can't break CI with no code change, matching the pinned postgres sidecar above.
echo "🪣 Starting S3 sidecar (versitygw, alias s3)"
S3_STARTED=$(docker run -d \
  --network "$NET" --network-alias s3 \
  -e ROOT_ACCESS_KEY="$S3_USER" -e ROOT_SECRET_KEY="$S3_PASS" \
  --name "$S3" \
  versity/versitygw:v1.8.0 --port :9000 posix /tmp)

# Wait for the S3 sidecar and create the two buckets using the workflow image's own
# rclone (--s3-no-check-bucket in the prod script means the buckets must pre-exist).
echo "⏳ Waiting for S3 sidecar and creating buckets..."
docker run --rm --network "$NET" --entrypoint bash "$WORKFLOW_IMAGE" -c "
export RCLONE_CONFIG_REMOTE_TYPE=s3
export RCLONE_CONFIG_REMOTE_PROVIDER=Other
export RCLONE_CONFIG_REMOTE_ACCESS_KEY_ID=$S3_USER
export RCLONE_CONFIG_REMOTE_SECRET_ACCESS_KEY=$S3_PASS
export RCLONE_CONFIG_REMOTE_ENDPOINT=$S3_ENDPOINT
for attempt in \$(seq 1 30); do rclone lsd remote: >/dev/null 2>&1 && break; sleep 1; done
rclone mkdir remote:u4i-backups
rclone mkdir remote:u4i-logs
rclone lsd remote: | grep -q u4i-backups
rclone lsd remote: | grep -q u4i-logs
" || {
  echo "❌ Could not provision S3 buckets" >&2
  exit 1
}
echo "✅ S3 sidecar ready with u4i-backups + u4i-logs buckets"

# --- Provision the REAL schema + seed data (drift-proof: uses migrations) ---
# Non-prod mode: DOCKER=true → DB host resolves to `db`; REDIS_URI defaults to
# memory:// so no Redis is needed; dummy SECRET_KEY/MAILJET satisfy config checks.
echo "📐 Provisioning real u4i schema via $PROVISION_IMAGE (flask db upgrade + addmock all)..."
docker run --rm \
  --network "$NET" \
  -e DOCKER=true \
  -e POSTGRES_USER=bob -e POSTGRES_DB=test -e POSTGRES_PASSWORD=test -e POSTGRES_TEST_DB=test \
  -e SECRET_KEY=backup-pipeline-test-secret-0123456789 \
  -e MAILJET_API_KEY=test -e MAILJET_SECRET_KEY=test \
  --entrypoint bash \
  "$PROVISION_IMAGE" \
  -c ". /code/venv/bin/activate && flask db upgrade && flask addmock all"
echo "✅ Schema provisioned and seeded"

# --- Workflow container (the code under test) ---
echo "🚢 Starting workflow container $MAIN"
MAIN_STARTED=$(docker run -d \
  --network "$NET" --no-healthcheck \
  -e POSTGRES_USER=bob -e POSTGRES_DB=test -e POSTGRES_PASSWORD=test \
  -e POSTGRES_HOST=db -e POSTGRES_PORT=5432 \
  -e METRICS_FLUSH_LIVENESS_THRESHOLD_SECONDS=180 \
  --name "$MAIN" \
  "$WORKFLOW_IMAGE")

wait_for_env_file "$MAIN" || {
  echo "❌ /app/container_environment not written in $MAIN" >&2
  exit 1
}

# In prod /backups is a mounted volume; here it does not exist. Create it and hand
# it to the workflow uid so the driver (run as 1001) can write the dump there.
docker exec "$MAIN" mkdir -p /backups
docker exec "$MAIN" chown 1001:1001 /backups

echo "🧪 Running driver legs (DB round-trip, log, prune, rclone stub + S3 sidecar) inside the workflow image..."
docker cp "$SCRIPT_DIR/backup-pipeline-driver.sh" "$MAIN":/tmp/driver.sh
docker exec -u 1001 \
  -e S3_USER="$S3_USER" -e S3_PASS="$S3_PASS" -e S3_ENDPOINT="$S3_ENDPOINT" \
  "$MAIN" bash /tmp/driver.sh

# --- Leg 5: missing-var guard (separate container, cron-like clean env) ---
echo "── Leg 5: missing-var guard ──"
GUARD_STARTED=$(docker run -d \
  --network "$NET" --no-healthcheck \
  -e POSTGRES_USER=bob -e POSTGRES_DB=test -e POSTGRES_PASSWORD=test \
  -e POSTGRES_HOST=db -e POSTGRES_PORT=5432 \
  -e METRICS_FLUSH_LIVENESS_THRESHOLD_SECONDS=180 \
  --name "$GUARD" \
  "$WORKFLOW_IMAGE")

wait_for_env_file "$GUARD" || {
  echo "❌ /app/container_environment not written in $GUARD" >&2
  exit 1
}

# Blank POSTGRES_DB in the cron env dump (daily-docker.sh re-sources this file, so
# clearing the process env alone would not trip the guard).
docker exec -u 1001 "$GUARD" bash -c 'printf "POSTGRES_USER=bob\nPOSTGRES_PASSWORD=test\nPOSTGRES_DB=\n" > /app/container_environment'

# Run cron-like: env -i strips the inherited environment (mirrors cron); a minimal
# PATH lets `date` resolve. Expect a non-zero exit from the guard.
set +e
docker exec -u 1001 "$GUARD" env -i PATH=/usr/local/bin:/usr/bin:/bin bash /app/daily-docker.sh
guard_rc=$?
set -e
[ "$guard_rc" -ne 0 ] || {
  echo "❌ Leg 5: daily-docker.sh exited 0 despite missing POSTGRES_DB" >&2
  exit 1
}

GUARD_LOG="/app/workflow_logs/$(docker exec "$GUARD" date +%Y_%m_%d)-daily-workflow-logs.txt"
GUARD_OUTPUT=$(docker exec "$GUARD" cat "$GUARD_LOG" 2>/dev/null || echo "")
echo "$GUARD_OUTPUT" | grep -q "required environment variable POSTGRES_DB is missing or empty" ||
  {
    echo "❌ Leg 5: guard message not found in workflow log" >&2
    exit 1
  }
echo "$GUARD_OUTPUT" | grep -q "IGNORE, IN DEVELOPMENT" ||
  {
    echo "❌ Leg 5: dev-mode notification not found in workflow log" >&2
    exit 1
  }
if docker exec "$GUARD" bash -c 'ls /backups/*_daily.sql.gz >/dev/null 2>&1'; then
  echo "❌ Leg 5: a backup file was created despite the guard aborting" >&2
  exit 1
fi
# Dev mode (PRODUCTION unset): the heartbeat takes its skip gate, one line, no hub call.
assert_one_heartbeat_line "Leg 5" "$GUARD_OUTPUT" "kind=fail outcome=skip"
echo "✅ Leg 5 PASSED: guard notified and aborted before any backup"

# --- Leg 7: full PRODUCTION=true daily-docker.sh end-to-end ---
# Exercises the real production flow as one run: build_container_env.py loading
# /run/secrets → dump → verify → REAL rclone upload to the S3 sidecar → success
# notification. Only the Discord webhook is stubbed (no external network).
echo "── Leg 7: prod-mode daily-docker.sh end-to-end ──"

# Populate a named volume with the secret files (a named volume lives inside the
# Docker VM, so this is portable — a host bind-mount of a mktemp dir is not shared
# into Colima's VM and would arrive empty locally).
docker volume create "$SECRETS_VOL" >/dev/null
SECRETS_VOL_CREATED=1
docker run --rm -v "$SECRETS_VOL":/s --entrypoint bash "$WORKFLOW_IMAGE" -c "
printf '%s' 'test'                                        > /s/POSTGRES_DB
printf '%s' 'bob'                                         > /s/POSTGRES_USER
printf '%s' 'test'                                        > /s/POSTGRES_PASSWORD
printf '%s' 'redispw'                                     > /s/REDIS_PASSWORD
printf '%s' 'https://discord.com/api/webhooks/1/stubbed'  > /s/NOTIFICATION_URL
printf '%s' '$S3_USER'                                 > /s/ACCESS_KEY
printf '%s' '$S3_PASS'                                 > /s/SECRET_ACCESS_KEY
printf '%s' '$S3_ENDPOINT'                             > /s/R2_ENDPOINT
"

PRODSIM_STARTED=$(docker run -d \
  --network "$NET" --no-healthcheck \
  -e PRODUCTION=true -e DEV_SERVER=false \
  -e POSTGRES_HOST=db -e POSTGRES_PORT=5432 \
  -e METRICS_FLUSH_LIVENESS_THRESHOLD_SECONDS=180 \
  -v "$SECRETS_VOL":/run/secrets:ro \
  --name "$PRODSIM" \
  "$WORKFLOW_IMAGE")

wait_for_env_file "$PRODSIM" || {
  echo "❌ /app/container_environment not written in $PRODSIM" >&2
  exit 1
}

# /backups volume + yesterday's log so both DB and log legs succeed.
docker exec "$PRODSIM" mkdir -p /backups /app/volume/logs
docker exec "$PRODSIM" chown -R 1001:1001 /backups /app/volume
docker exec -u 1001 "$PRODSIM" bash -c 'printf "prod-sim log line\n" > "/app/volume/logs/$(date -d yesterday +%Y-%m-%d)_daily.log"'
# Stub the Discord notifier (capture messages instead of POSTing to discord.com).
docker exec "$PRODSIM" bash -c 'printf "#!/bin/bash\necho \"NOTIFY: \$3\" >> /tmp/notify.log\nexit 0\n" > /usr/bin/restricted_curl && chmod +x /usr/bin/restricted_curl'

set +e
docker exec -u 1001 "$PRODSIM" bash /app/daily-docker.sh
prodsim_rc=$?
set -e
if [ "$prodsim_rc" -ne 0 ]; then
  echo "❌ Leg 7: daily-docker.sh exited $prodsim_rc in prod mode" >&2
  echo "--- workflow_logs dir ---" >&2
  docker exec "$PRODSIM" sh -c 'ls -la /app/workflow_logs/ 2>&1; echo "--- log contents ---"; cat /app/workflow_logs/*.txt 2>&1' >&2 || true
  exit 1
fi

PRODSIM_LOG=$(docker exec "$PRODSIM" cat "/app/workflow_logs/$(docker exec "$PRODSIM" date +%Y_%m_%d)-daily-workflow-logs.txt" 2>/dev/null || echo "")
# Exactly one success heartbeat (no key directory is mounted, so the client logs
# missing_key) and the run's exit code (asserted above) is unchanged.
assert_one_heartbeat_line "Leg 7" "$PRODSIM_LOG" "kind=success .*outcome=missing_key"
echo "$PRODSIM_LOG" | grep -q "Success: Sent daily database backup to Cloudflare R2" ||
  {
    echo "❌ Leg 7: database upload did not report success" >&2
    exit 1
  }
docker exec "$PRODSIM" cat /tmp/notify.log 2>/dev/null | grep -qE "Daily Backup.*SUCCESS" ||
  {
    echo "❌ Leg 7: success notification not dispatched" >&2
    exit 1
  }
# Per-step SUCCESS lines are intentionally suppressed — only the digest reports
# each leg's outcome. Per-step messages carry the "DOCKER: " prefix (the digest
# does not), so any "DOCKER: <STEP> SUCCESS" line means a per-step success leaked.
if docker exec "$PRODSIM" cat /tmp/notify.log 2>/dev/null | grep -qE "DOCKER: [A-Z_]+ SUCCESS"; then
  echo "❌ Leg 7: per-step SUCCESS notification leaked (should be digest-only)" >&2
  exit 1
fi

# Confirm the objects actually persisted in the S3 sidecar (real end-to-end upload).
docker run --rm --network "$NET" --entrypoint bash "$WORKFLOW_IMAGE" -c "
export RCLONE_CONFIG_REMOTE_TYPE=s3
export RCLONE_CONFIG_REMOTE_PROVIDER=Other
export RCLONE_CONFIG_REMOTE_ACCESS_KEY_ID=$S3_USER
export RCLONE_CONFIG_REMOTE_SECRET_ACCESS_KEY=$S3_PASS
export RCLONE_CONFIG_REMOTE_ENDPOINT=$S3_ENDPOINT
rclone ls remote:u4i-backups/ | grep -q 'test_.*_daily.sql.gz'
rclone ls remote:u4i-logs/ | grep -q '_daily.log.gz'
" || {
  echo "❌ Leg 7: expected objects not found in S3 buckets" >&2
  exit 1
}
echo "✅ Leg 7 PASSED: prod-mode end-to-end (secrets → dump → verify → real S3 upload → notification)"

# --- Heartbeat legs: each runs daily-docker.sh in its OWN fresh container with
# PRODUCTION=true (so the client passes its skip gate) and no key directory, and
# counts the daily_backup heartbeat lines in that container's own log. ---

# Leg 8: PRODUCTION=true variant of Leg 5 (missing POSTGRES_DB) -> exactly one fail.
echo "── Leg 8: prod missing-var guard sends one fail heartbeat ──"
start_heartbeat_leg_container backup_test_hb_guard test
docker exec -u 1001 backup_test_hb_guard bash -c "printf 'POSTGRES_USER=bob\nPOSTGRES_PASSWORD=test\nPOSTGRES_DB=\nPRODUCTION=true\nNOTIFS_BASE_URL=http://127.0.0.1:9\nNOTIFS_KEY_DIR=/nonexistent\n' > /app/container_environment"
set +e
docker exec -u 1001 backup_test_hb_guard env -i PATH=/usr/local/bin:/usr/bin:/bin bash /app/daily-docker.sh
hb_guard_rc=$?
set -e
[ "$hb_guard_rc" -ne 0 ] || {
  echo "❌ Leg 8: daily-docker.sh exited 0 despite missing POSTGRES_DB" >&2
  exit 1
}
assert_one_heartbeat_line "Leg 8" "$(daily_log backup_test_hb_guard)" "kind=fail .*outcome=missing_key"
echo "✅ Leg 8 PASSED: missing POSTGRES_* in prod sends exactly one fail heartbeat"

# Leg 9: failing step (wrong DB password, so the database backup fails) -> one fail.
echo "── Leg 9: failing backup step sends one fail heartbeat ──"
start_heartbeat_leg_container backup_test_hb_step wrong-password
set +e
docker exec -u 1001 backup_test_hb_step bash /app/daily-docker.sh
set -e
assert_one_heartbeat_line "Leg 9" "$(daily_log backup_test_hb_step)" "kind=fail .*outcome=missing_key"
echo "✅ Leg 9 PASSED: failed database backup sends exactly one fail heartbeat"

# Leg 10: manual trigger -> a skip line and no hub call (no missing_key line).
echo "── Leg 10: manual run sends no heartbeat ──"
start_heartbeat_leg_container backup_test_hb_manual wrong-password
set +e
docker exec -u 1001 -e BACKUP_TRIGGER_SOURCE=manual backup_test_hb_manual bash /app/daily-docker.sh
set -e
HB_MANUAL_LOG=$(daily_log backup_test_hb_manual)
assert_one_heartbeat_line "Leg 10" "$HB_MANUAL_LOG" "outcome=skip error=manual_trigger"
if echo "$HB_MANUAL_LOG" | grep -q "outcome=missing_key"; then
  echo "❌ Leg 10: a manual run reached the hub client" >&2
  exit 1
fi
echo "✅ Leg 10 PASSED: manual run logs a skip and pings nothing"

# Leg 11: set -e abort. After container_environment is sourced and the trap is
# armed, `source remote-object-storage.sh` is unguarded, so a failing file aborts
# the script under set -e; the EXIT trap must still send exactly one fail ping
# using its defaults without tripping set -u.
echo "── Leg 11: set -e abort sends one fail heartbeat ──"
start_heartbeat_leg_container backup_test_hb_abort test
docker exec backup_test_hb_abort bash -c "printf 'false\n' > /app/remote-object-storage.sh"
set +e
docker exec -u 1001 backup_test_hb_abort bash /app/daily-docker.sh
hb_abort_rc=$?
set -e
[ "$hb_abort_rc" -ne 0 ] || {
  echo "❌ Leg 11: daily-docker.sh did not abort under set -e" >&2
  exit 1
}
HB_ABORT_LOG=$(daily_log backup_test_hb_abort)
assert_one_heartbeat_line "Leg 11" "$HB_ABORT_LOG" "kind=fail .*outcome=missing_key"
if echo "$HB_ABORT_LOG" | grep -q "unbound variable"; then
  echo "❌ Leg 11: the EXIT trap tripped set -u" >&2
  exit 1
fi
echo "✅ Leg 11 PASSED: set -e abort sends exactly one fail heartbeat"

echo "✅ ALL BACKUP PIPELINE LEGS PASSED"
exit 0
