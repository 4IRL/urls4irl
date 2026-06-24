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

NETWORK_CREATED=0
DB_STARTED=""
MAIN_STARTED=""
GUARD_STARTED=""

cleanup() {
    echo "🧹 Cleaning up..."
    [ -n "$MAIN_STARTED" ] && docker rm -f "$MAIN" >/dev/null 2>&1 || true
    [ -n "$GUARD_STARTED" ] && docker rm -f "$GUARD" >/dev/null 2>&1 || true
    [ -n "$DB_STARTED" ] && docker rm -f "$DB" >/dev/null 2>&1 || true
    [ "$NETWORK_CREATED" = "1" ] && docker network rm "$NET" >/dev/null 2>&1 || true
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

echo "🧪 Running driver legs (DB round-trip, log, prune, rclone) inside the workflow image..."
docker cp "$SCRIPT_DIR/backup-pipeline-driver.sh" "$MAIN":/tmp/driver.sh
docker exec -u 1001 "$MAIN" bash /tmp/driver.sh

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

echo "✅ ALL BACKUP PIPELINE LEGS PASSED"
exit 0
