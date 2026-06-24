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
MINIO=backup_test_minio
PRODSIM=backup_test_prodsim

# MinIO is S3-compatible (same API as Cloudflare R2), so pointing the real,
# un-stubbed rclone at it exercises the production upload code path hermetically.
MINIO_USER=minioadmin
MINIO_PASS=minioadmin123
MINIO_ENDPOINT=http://minio:9000

SECRETS_VOL=backup_test_secrets

NETWORK_CREATED=0
DB_STARTED=""
MAIN_STARTED=""
GUARD_STARTED=""
MINIO_STARTED=""
PRODSIM_STARTED=""
SECRETS_VOL_CREATED=""

cleanup() {
    echo "🧹 Cleaning up..."
    [ -n "$MAIN_STARTED" ] && docker rm -f "$MAIN" >/dev/null 2>&1 || true
    [ -n "$GUARD_STARTED" ] && docker rm -f "$GUARD" >/dev/null 2>&1 || true
    [ -n "$PRODSIM_STARTED" ] && docker rm -f "$PRODSIM" >/dev/null 2>&1 || true
    [ -n "$MINIO_STARTED" ] && docker rm -f "$MINIO" >/dev/null 2>&1 || true
    [ -n "$DB_STARTED" ] && docker rm -f "$DB" >/dev/null 2>&1 || true
    [ "$NETWORK_CREATED" = "1" ] && docker network rm "$NET" >/dev/null 2>&1 || true
    [ -n "$SECRETS_VOL_CREATED" ] && docker volume rm "$SECRETS_VOL" >/dev/null 2>&1 || true
}
trap cleanup EXIT

wait_for_env_file() {
    local container_name=$1
    local attempt
    for attempt in $(seq 1 10); do
        docker exec "$container_name" test -f /app/container_environment && return 0
        sleep 1
    done
    docker exec "$container_name" test -f /app/container_environment
}

echo "🌐 Creating network $NET"
docker network create "$NET" >/dev/null
NETWORK_CREATED=1

# --- Postgres sidecar (alias `db` — the backup scripts hardcode `-h "db"`) ---
echo "🐘 Starting Postgres sidecar (alias db)"
DB_STARTED=$(docker run -d \
    --network "$NET" --network-alias db \
    -e POSTGRES_USER=bob -e POSTGRES_DB=test -e POSTGRES_PASSWORD=test \
    --name "$DB" \
    postgres:16.3-bookworm)

echo "⏳ Waiting for Postgres to accept connections..."
for attempt in $(seq 1 30); do
    if docker exec "$DB" pg_isready -U bob -d test >/dev/null 2>&1; then break; fi
    sleep 1
done
docker exec "$DB" pg_isready -U bob -d test >/dev/null 2>&1 || { echo "❌ Postgres sidecar never became ready" >&2; exit 1; }

# --- MinIO (S3-compatible) sidecar + buckets for the real-upload legs ---
echo "🪣 Starting MinIO sidecar (alias minio)"
MINIO_STARTED=$(docker run -d \
    --network "$NET" --network-alias minio \
    -e MINIO_ROOT_USER="$MINIO_USER" -e MINIO_ROOT_PASSWORD="$MINIO_PASS" \
    --name "$MINIO" \
    minio/minio server /data)

# Wait for MinIO and create the two buckets using the workflow image's own rclone
# (--s3-no-check-bucket in the prod script means the buckets must pre-exist).
echo "⏳ Waiting for MinIO and creating buckets..."
docker run --rm --network "$NET" --entrypoint bash "$WORKFLOW_IMAGE" -c "
export RCLONE_CONFIG_REMOTE_TYPE=s3
export RCLONE_CONFIG_REMOTE_PROVIDER=Other
export RCLONE_CONFIG_REMOTE_ACCESS_KEY_ID=$MINIO_USER
export RCLONE_CONFIG_REMOTE_SECRET_ACCESS_KEY=$MINIO_PASS
export RCLONE_CONFIG_REMOTE_ENDPOINT=$MINIO_ENDPOINT
for attempt in \$(seq 1 30); do rclone lsd remote: >/dev/null 2>&1 && break; sleep 1; done
rclone mkdir remote:u4i-backups
rclone mkdir remote:u4i-logs
rclone lsd remote: | grep -q u4i-backups
rclone lsd remote: | grep -q u4i-logs
" || { echo "❌ Could not provision MinIO buckets" >&2; exit 1; }
echo "✅ MinIO ready with u4i-backups + u4i-logs buckets"

# --- Provision the REAL schema + seed data (drift-proof: uses migrations) ---
# Non-prod mode: DOCKER=true → DB host resolves to `db`; REDIS_URI defaults to
# memory:// so no Redis is needed; dummy SECRET_KEY/MAILJET satisfy config checks.
echo "📐 Provisioning real u4i schema via $PROVISION_IMAGE (flask db upgrade + addmock all)..."
docker run --rm \
    --network "$NET" \
    -e DOCKER=true \
    -e POSTGRES_USER=bob -e POSTGRES_DB=test -e POSTGRES_PASSWORD=test -e POSTGRES_TEST_DB=test \
    -e SECRET_KEY=backup-pipeline-test-secret \
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

wait_for_env_file "$MAIN" || { echo "❌ /app/container_environment not written in $MAIN" >&2; exit 1; }

# In prod /backups is a mounted volume; here it does not exist. Create it and hand
# it to the workflow uid so the driver (run as 1001) can write the dump there.
docker exec "$MAIN" mkdir -p /backups
docker exec "$MAIN" chown 1001:1001 /backups

echo "🧪 Running driver legs (DB round-trip, log, prune, rclone stub + MinIO) inside the workflow image..."
docker cp "$SCRIPT_DIR/backup-pipeline-driver.sh" "$MAIN":/tmp/driver.sh
docker exec -u 1001 \
    -e MINIO_USER="$MINIO_USER" -e MINIO_PASS="$MINIO_PASS" -e MINIO_ENDPOINT="$MINIO_ENDPOINT" \
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

wait_for_env_file "$GUARD" || { echo "❌ /app/container_environment not written in $GUARD" >&2; exit 1; }

# Blank POSTGRES_DB in the cron env dump (daily-docker.sh re-sources this file, so
# clearing the process env alone would not trip the guard).
docker exec -u 1001 "$GUARD" bash -c 'printf "POSTGRES_USER=bob\nPOSTGRES_PASSWORD=test\nPOSTGRES_DB=\n" > /app/container_environment'

# Run cron-like: env -i strips the inherited environment (mirrors cron); a minimal
# PATH lets `date` resolve. Expect a non-zero exit from the guard.
set +e
docker exec -u 1001 "$GUARD" env -i PATH=/usr/local/bin:/usr/bin:/bin bash /app/daily-docker.sh
guard_rc=$?
set -e
[ "$guard_rc" -ne 0 ] || { echo "❌ Leg 5: daily-docker.sh exited 0 despite missing POSTGRES_DB" >&2; exit 1; }

GUARD_LOG="/app/workflow_logs/$(docker exec "$GUARD" date +%Y_%m_%d)-daily-workflow-logs.txt"
GUARD_OUTPUT=$(docker exec "$GUARD" cat "$GUARD_LOG" 2>/dev/null || echo "")
echo "$GUARD_OUTPUT" | grep -q "required environment variable POSTGRES_DB is missing or empty" \
    || { echo "❌ Leg 5: guard message not found in workflow log" >&2; exit 1; }
echo "$GUARD_OUTPUT" | grep -q "IGNORE, IN DEVELOPMENT" \
    || { echo "❌ Leg 5: dev-mode notification not found in workflow log" >&2; exit 1; }
if docker exec "$GUARD" bash -c 'ls /backups/*_daily.sql.gz >/dev/null 2>&1'; then
    echo "❌ Leg 5: a backup file was created despite the guard aborting" >&2
    exit 1
fi
echo "✅ Leg 5 PASSED: guard notified and aborted before any backup"

# --- Leg 7: full PRODUCTION=true daily-docker.sh end-to-end ---
# Exercises the real production flow as one run: build_container_env.py loading
# /run/secrets → dump → verify → REAL rclone upload to MinIO → success
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
printf '%s' '$MINIO_USER'                                 > /s/ACCESS_KEY
printf '%s' '$MINIO_PASS'                                 > /s/SECRET_ACCESS_KEY
printf '%s' '$MINIO_ENDPOINT'                             > /s/R2_ENDPOINT
"

PRODSIM_STARTED=$(docker run -d \
    --network "$NET" --no-healthcheck \
    -e PRODUCTION=true -e DEV_SERVER=false \
    -e POSTGRES_HOST=db -e POSTGRES_PORT=5432 \
    -e METRICS_FLUSH_LIVENESS_THRESHOLD_SECONDS=180 \
    -v "$SECRETS_VOL":/run/secrets:ro \
    --name "$PRODSIM" \
    "$WORKFLOW_IMAGE")

wait_for_env_file "$PRODSIM" || { echo "❌ /app/container_environment not written in $PRODSIM" >&2; exit 1; }

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
echo "$PRODSIM_LOG" | grep -q "Success: Sent daily database backup to Cloudflare R2" \
    || { echo "❌ Leg 7: database upload did not report success" >&2; exit 1; }
docker exec "$PRODSIM" cat /tmp/notify.log 2>/dev/null | grep -q "Success: Backups saved and exported to cloud" \
    || { echo "❌ Leg 7: success notification not dispatched" >&2; exit 1; }

# Confirm the objects actually persisted in MinIO (real end-to-end upload).
docker run --rm --network "$NET" --entrypoint bash "$WORKFLOW_IMAGE" -c "
export RCLONE_CONFIG_REMOTE_TYPE=s3
export RCLONE_CONFIG_REMOTE_PROVIDER=Other
export RCLONE_CONFIG_REMOTE_ACCESS_KEY_ID=$MINIO_USER
export RCLONE_CONFIG_REMOTE_SECRET_ACCESS_KEY=$MINIO_PASS
export RCLONE_CONFIG_REMOTE_ENDPOINT=$MINIO_ENDPOINT
rclone ls remote:u4i-backups/ | grep -q 'test_.*_daily.sql.gz'
rclone ls remote:u4i-logs/ | grep -q '_daily.log.gz'
" || { echo "❌ Leg 7: expected objects not found in MinIO buckets" >&2; exit 1; }
echo "✅ Leg 7 PASSED: prod-mode end-to-end (secrets → dump → verify → real MinIO upload → notification)"

echo "✅ ALL BACKUP PIPELINE LEGS PASSED"
exit 0
