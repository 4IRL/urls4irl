#!/usr/bin/env bash
set -e

IMAGE_NAME=$1

echo "🚀 Starting smoke test for $IMAGE_NAME..."
ENV_VARS="-e SECRET_KEY=ABC123456"

# Container/network names derived from a single prefix so they're easy to
# change. The workflow leg below stands up a Redis sidecar on a dedicated
# bridge network; the prod leg leaves these unset and the cleanup trap
# becomes a no-op for those resources.
SMOKE_NET=smoke_test_net
SMOKE_REDIS=smoke_test_redis
SMOKE_MAIN=smoke_test

CONTAINER_ID=""
REDIS_CONTAINER_ID=""
NETWORK_CREATED=0

# Single cleanup function called from a single trap so all paths
# (success, failure, error) tear everything down. Each step is guarded so
# a failure mid-setup doesn't leave a noisy cleanup that masks the real
# error in CI logs.
cleanup() {
    echo "🧹 Cleaning up..."
    if [ -n "$CONTAINER_ID" ]; then
        docker rm -f "$SMOKE_MAIN" >/dev/null 2>&1 || true
    fi
    if [ -n "$REDIS_CONTAINER_ID" ]; then
        docker rm -f "$SMOKE_REDIS" >/dev/null 2>&1 || true
    fi
    if [ "$NETWORK_CREATED" = "1" ]; then
        docker network rm "$SMOKE_NET" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

# Run the container (using Docker's internal healthcheck)
echo "Running container..."
if [[ "$IMAGE_NAME" == *"u4i-prod"* ]]; then
    CONTAINER_ID=$(docker run -d \
        --entrypoint bash \
        -e DEV_SERVER=true \
        -e POSTGRES_USER=bob \
        -e POSTGRES_DB=test \
        -e POSTGRES_TEST_DB=test \
        -e POSTGRES_PASSWORD=test \
        -e IS_DOCKER=true \
        --name "$SMOKE_MAIN" \
        "$IMAGE_NAME" \
        -c ". /code/venv/bin/activate && flask run --host=0.0.0.0 --port=5000"
    )

    echo "Container ID: $CONTAINER_ID"

    echo "Waiting for Docker Healthcheck status..."

    # Poll Docker for the health status
    MAX_RETRIES=15
    for i in $(seq 1 $MAX_RETRIES); do
      # Get the status: starting, healthy, or unhealthy
      STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_ID")

      if [ "$STATUS" == "healthy" ]; then
        echo "✅ Smoke test PASSED ($STATUS)"
        exit 0
      fi

      if [ "$STATUS" == "unhealthy" ]; then
        echo "❌ Smoke test FAILED ($STATUS)"
        docker logs "$CONTAINER_ID"
        exit 1
      fi

      echo "Attempt $i/$MAX_RETRIES: Status is '$STATUS'. Retrying in 5s..."
      sleep 5
    done

    echo "❌ Smoke test TIMED OUT"
    docker logs "$CONTAINER_ID"
    exit 1
fi

# ----------------------------------------------------------------------
# Workflow image branch
# ----------------------------------------------------------------------
# The workflow image's HEALTHCHECK runs check_flush_liveness.py, which
# requires a reachable Redis to read the metrics:flush:last_success_epoch
# sentinel. Standalone `docker run` with no Redis sidecar can never go
# healthy — and even if it could, start-period=200s exceeds our 75s poll
# budget. Stand up a Redis sidecar on a dedicated network and exercise
# the script directly via `docker exec` for a strictly stronger 3-state
# contract verification.

echo "🌐 Creating dedicated network: $SMOKE_NET"
docker network create "$SMOKE_NET" >/dev/null
NETWORK_CREATED=1

echo "📦 Starting Redis sidecar: $SMOKE_REDIS"
REDIS_CONTAINER_ID=$(docker run -d \
    --network "$SMOKE_NET" \
    --name "$SMOKE_REDIS" \
    redis:6.2
)

# Give Redis a moment to accept connections before the first SET.
for i in $(seq 1 10); do
    if docker exec "$SMOKE_REDIS" redis-cli ping >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

echo "🚢 Starting workflow container: $SMOKE_MAIN"
CONTAINER_ID=$(docker run -d \
    --network "$SMOKE_NET" \
    -e POSTGRES_USER=bob \
    -e POSTGRES_DB=test \
    -e POSTGRES_PASSWORD=test \
    -e METRICS_REDIS_URI="redis://${SMOKE_REDIS}:6379/0" \
    -e METRICS_FLUSH_LIVENESS_THRESHOLD_SECONDS=180 \
    --name "$SMOKE_MAIN" \
    "$IMAGE_NAME"
)

echo "Container ID: $CONTAINER_ID"

# ----------------------------------------------------------------------
# Step A — Verify Dockerfile HEALTHCHECK directive is wired correctly.
# ----------------------------------------------------------------------
# Guards against future Dockerfile drift (e.g., someone reverts to
# `pgrep cron` or changes the venv path) by asserting the actual
# inspected healthcheck command matches what we expect.
echo "🔍 Verifying HEALTHCHECK directive..."
HEALTHCHECK_JSON=$(docker inspect --format='{{json .Config.Healthcheck}}' "$CONTAINER_ID")
EXPECTED_HC_PYTHON="/opt/metrics-venv/bin/python"
EXPECTED_HC_SCRIPT="/app/check_flush_liveness.py"
if [[ "$HEALTHCHECK_JSON" != *"$EXPECTED_HC_PYTHON"* ]] \
   || [[ "$HEALTHCHECK_JSON" != *"$EXPECTED_HC_SCRIPT"* ]]; then
    echo "❌ HEALTHCHECK directive does not reference $EXPECTED_HC_PYTHON $EXPECTED_HC_SCRIPT"
    echo "   Inspected: $HEALTHCHECK_JSON"
    exit 1
fi
echo "✅ HEALTHCHECK directive references $EXPECTED_HC_PYTHON $EXPECTED_HC_SCRIPT"

# ----------------------------------------------------------------------
# Step B — Active 3-state liveness verification via `docker exec`.
# ----------------------------------------------------------------------
# Doesn't wait for Docker's 60s healthcheck loop — runs the same script
# the HEALTHCHECK runs, in the same container, with full control over
# the sentinel value.

# Helper: run the liveness check inside the workflow container and
# capture exit code + stderr. Stdout is discarded (script writes to
# stderr).
LIVENESS_STDERR_FILE=$(mktemp)
run_liveness_check() {
    set +e
    docker exec "$SMOKE_MAIN" \
        /opt/metrics-venv/bin/python /app/check_flush_liveness.py \
        2> "$LIVENESS_STDERR_FILE" \
        >/dev/null
    local exit_code=$?
    set -e
    return $exit_code
}

echo "🧪 State 1 — no sentinel (expect non-zero + 'missing')..."
if run_liveness_check; then
    echo "❌ State 1 FAILED: expected non-zero exit, got 0"
    cat "$LIVENESS_STDERR_FILE"
    exit 1
fi
if ! grep -q "missing" "$LIVENESS_STDERR_FILE"; then
    echo "❌ State 1 FAILED: stderr missing 'missing' substring"
    cat "$LIVENESS_STDERR_FILE"
    exit 1
fi
echo "✅ State 1 PASSED"

echo "🧪 State 2 — fresh sentinel (expect 0)..."
NOW_EPOCH=$(date +%s)
docker exec "$SMOKE_REDIS" redis-cli SET metrics:flush:last_success_epoch "$NOW_EPOCH" >/dev/null
if ! run_liveness_check; then
    echo "❌ State 2 FAILED: expected exit 0, got non-zero"
    cat "$LIVENESS_STDERR_FILE"
    exit 1
fi
echo "✅ State 2 PASSED"

echo "🧪 State 3 — stale sentinel (expect non-zero + 'stale')..."
docker exec "$SMOKE_REDIS" redis-cli SET metrics:flush:last_success_epoch 0 >/dev/null
if run_liveness_check; then
    echo "❌ State 3 FAILED: expected non-zero exit, got 0"
    cat "$LIVENESS_STDERR_FILE"
    exit 1
fi
if ! grep -q "stale" "$LIVENESS_STDERR_FILE"; then
    echo "❌ State 3 FAILED: stderr missing 'stale' substring"
    cat "$LIVENESS_STDERR_FILE"
    exit 1
fi
echo "✅ State 3 PASSED"

rm -f "$LIVENESS_STDERR_FILE"

# Active 3-state verification above is strictly stronger than waiting up
# to 75s for Docker to call the same script; skip the legacy poll loop
# (it would never go healthy within 75s anyway — start-period=200s).
echo "✅ Smoke test PASSED (3-state liveness contract verified)"
exit 0
