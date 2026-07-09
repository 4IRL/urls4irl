#!/usr/bin/env bash
set -e

IMAGE_NAME=$1

echo "🚀 Starting smoke test for $IMAGE_NAME..."

# Container/network names derived from a single prefix so they're easy to
# change. The workflow leg below stands up a Redis sidecar on a dedicated
# bridge network; the prod leg leaves these unset and the cleanup trap
# becomes a no-op for those resources.
SMOKE_NET=smoke_test_net
SMOKE_REDIS=smoke_test_redis
SMOKE_MAIN=smoke_test
SMOKE_PROD_SIM=smoke_test_prod_sim

CONTAINER_ID=""
REDIS_CONTAINER_ID=""
NETWORK_CREATED=0
SMOKE_SECRETS_DIR=""
LIVENESS_STDERR_FILE=""
PROD_SIM_STARTED="" # Non-empty signals cleanup that the prod-sim container was started

# dev-sim injects 5 vars via `docker run -e` (POSTGRES_USER/DB/PASSWORD,
# METRICS_REDIS_URI, METRICS_FLUSH_LIVENESS_THRESHOLD_SECONDS), all allow-listed.
# Unfiltered `printenv` on this image is ~11 lines (5 injected + ~6 Docker
# defaults like PATH/HOSTNAME/HOME), so a threshold of 8 sits above the
# allow-listed set yet below the unfiltered baseline and reliably fires when
# the filter regresses to unfiltered printenv.
DEV_SIM_LINE_COUNT_MAX=8

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
  if [ -n "$PROD_SIM_STARTED" ]; then
    docker rm -f "$SMOKE_PROD_SIM" >/dev/null 2>&1 || true
  fi
  if [ "$NETWORK_CREATED" = "1" ]; then
    docker network rm "$SMOKE_NET" >/dev/null 2>&1 || true
  fi
  if [ -n "$SMOKE_SECRETS_DIR" ]; then
    rm -rf "$SMOKE_SECRETS_DIR" >/dev/null 2>&1 || true
  fi
  rm -f "$LIVENESS_STDERR_FILE" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Poll until the named container has written /app/container_environment.
# Guards against a race where assertions run before startup-workflow.sh
# finishes the dump. Used by both the dev-sim and prod-sim legs.
wait_for_env_file() {
  local container_name=$1
  for _ in $(seq 1 10); do
    docker exec "$container_name" test -f /app/container_environment && return 0
    sleep 1
  done
  docker exec "$container_name" test -f /app/container_environment
}

# Run the container (using Docker's internal healthcheck)
echo "Running container..."
if [[ "$IMAGE_NAME" == *"u4i-prod"* ]]; then
  CONTAINER_ID=$(
    docker run -d \
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
#
# This branch runs three verification steps:
#   Step A — assert the Dockerfile HEALTHCHECK directive is wired correctly,
#            then assert /app/container_environment mode/owner/line-count
#            on the dev-sim container (vars injected via `docker run -e`).
#   Step B — active 3-state liveness contract via `docker exec`.
#   Step C — prod-sim: boot a second container with PRODUCTION=true and a
#            mounted /run/secrets tmpdir to exercise startup-workflow.sh's
#            load_secrets() + METRICS_REDIS_URI URL-encode assembly +
#            allow-list dump filter — the only CI coverage of that branch.

echo "🌐 Creating dedicated network: $SMOKE_NET"
docker network create "$SMOKE_NET" >/dev/null
NETWORK_CREATED=1

echo "📦 Starting Redis sidecar: $SMOKE_REDIS"
REDIS_CONTAINER_ID=$(
  docker run -d \
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
CONTAINER_ID=$(
  docker run -d \
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
if [[ "$HEALTHCHECK_JSON" != *"$EXPECTED_HC_PYTHON"* ]] ||
  [[ "$HEALTHCHECK_JSON" != *"$EXPECTED_HC_SCRIPT"* ]]; then
  echo "❌ HEALTHCHECK directive does not reference $EXPECTED_HC_PYTHON $EXPECTED_HC_SCRIPT"
  echo "   Inspected: $HEALTHCHECK_JSON"
  exit 1
fi
echo "✅ HEALTHCHECK directive references $EXPECTED_HC_PYTHON $EXPECTED_HC_SCRIPT"

wait_for_env_file "$SMOKE_MAIN" || {
  echo "TIMEOUT: /app/container_environment was not written within 10s" >&2
  exit 1
}

echo "🔍 Asserting /app/container_environment mode + ownership + bounded line count..."
MODE_OWNER="$(docker exec "$SMOKE_MAIN" stat -c '%a %U:%G' /app/container_environment)"
if [ "$MODE_OWNER" != "600 workflow:workflow" ]; then # GNU stat -c '%a' outputs octal without leading zeros; 600 = rw------- as expected for a restricted secrets file.
  echo "❌ FAIL: expected mode+owner '600 workflow:workflow', got '$MODE_OWNER'" >&2
  exit 1
fi
LINE_COUNT="$(docker exec "$SMOKE_MAIN" sh -c 'wc -l < /app/container_environment')"
if [ "$LINE_COUNT" -gt "$DEV_SIM_LINE_COUNT_MAX" ]; then
  echo "❌ FAIL: /app/container_environment has $LINE_COUNT lines (>$DEV_SIM_LINE_COUNT_MAX). Either the allow-list grew significantly or the filter regressed to unfiltered printenv." >&2
  exit 1
fi
echo "✅ /app/container_environment is mode 600 / workflow:workflow with $LINE_COUNT lines."

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
    2>"$LIVENESS_STDERR_FILE" \
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

# Active 3-state verification above is strictly stronger than waiting up
# to 75s for Docker to call the same script; skip the legacy poll loop
# (it would never go healthy within 75s anyway — start-period=200s).
echo "✅ Smoke test PASSED (3-state liveness contract verified)"

# ----------------------------------------------------------------------
# Step C — Prod-sim: exercise startup-workflow.sh's PRODUCTION=true branch.
# ----------------------------------------------------------------------
# The dev-sim leg above passes vars via `docker run -e`, which skips the
# `if [ "$PRODUCTION" == "true" ]` branch of startup-workflow.sh and so
# never exercises load_secrets() or the METRICS_REDIS_URI URL-encoding
# assembly. This leg fixes that gap by mounting a tmpdir of fake secret
# files at /run/secrets and setting PRODUCTION=true, then asserting the
# resulting /app/container_environment contents.

echo "🔐 Step C — Prod-sim: load_secrets() + METRICS_REDIS_URI assembly..."

SMOKE_SECRETS_DIR="$(mktemp -d)"
# Eight fake secret files whose basenames mirror the prod compose `secrets:` block.
# REDIS_PASSWORD uses `p@ssword` (no slash). urllib.parse.quote() does NOT
# encode '/' by default, so a slash-free password makes
# quote('p@ssword') == 'p%40ssword' deterministic without any production
# code change to startup-workflow.sh.
printf '%s' 'fakedb' >"$SMOKE_SECRETS_DIR/POSTGRES_DB"
printf '%s' 'fakeuser' >"$SMOKE_SECRETS_DIR/POSTGRES_USER"
printf '%s' 'fakepass' >"$SMOKE_SECRETS_DIR/POSTGRES_PASSWORD"
printf '%s' 'p@ssword' >"$SMOKE_SECRETS_DIR/REDIS_PASSWORD"
printf '%s' 'https://fake/url' >"$SMOKE_SECRETS_DIR/NOTIFICATION_URL"
printf '%s' 'fakeaccess' >"$SMOKE_SECRETS_DIR/ACCESS_KEY"
printf '%s' 'fakesecret' >"$SMOKE_SECRETS_DIR/SECRET_ACCESS_KEY"
printf '%s' 'https://fake.r2' >"$SMOKE_SECRETS_DIR/R2_ENDPOINT"

echo "🚢 Starting prod-sim workflow container: $SMOKE_PROD_SIM"
# --no-healthcheck because check_flush_liveness.py would fail (no Redis
# reachable at the assembled `redis-metrics:6379` hostname — we are only
# asserting the dump file, not flush behavior).
PROD_SIM_STARTED=$(
  docker run -d \
    --network "$SMOKE_NET" \
    --no-healthcheck \
    -e PRODUCTION=true \
    -e DEV_SERVER=false \
    -e POSTGRES_HOST=db \
    -e POSTGRES_PORT=5432 \
    -e METRICS_FLUSH_LIVENESS_THRESHOLD_SECONDS=180 \
    -v "$SMOKE_SECRETS_DIR":/run/secrets:ro \
    --name "$SMOKE_PROD_SIM" \
    "$IMAGE_NAME"
)

wait_for_env_file "$SMOKE_PROD_SIM" || {
  echo "TIMEOUT: /app/container_environment was not written within 10s in prod-sim" >&2
  exit 1
}

echo "🔍 Step C.1 — Asserting mode + ownership..."
MODE_OWNER="$(docker exec "$SMOKE_PROD_SIM" stat -c '%a %U:%G' /app/container_environment)"
if [ "$MODE_OWNER" != "600 workflow:workflow" ]; then
  echo "❌ Prod-sim FAIL: expected '600 workflow:workflow', got '$MODE_OWNER'" >&2
  exit 1
fi

echo "🔍 Step C.2 — Asserting secret-derived vars made it into the dump..."
DUMP="$(docker exec "$SMOKE_PROD_SIM" cat /app/container_environment)"
for var in POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD NOTIFICATION_URL ACCESS_KEY SECRET_ACCESS_KEY R2_ENDPOINT; do
  if ! echo "$DUMP" | grep -qF "${var}="; then
    # On failure the full dump is echoed to CI logs, so this smoke test must
    # only ever run against images built with fake/test secrets — never a
    # real production image.
    echo "❌ Prod-sim FAIL: secret-derived var '$var' missing from /app/container_environment" >&2
    echo "Full dump:" >&2
    echo "$DUMP" >&2
    exit 1
  fi
done

echo "🔍 Step C.3 — Asserting METRICS_REDIS_URI was assembled with URL-encoded password..."
# urllib.parse.quote('p@ssword') → 'p%40ssword' (no slash in password, so no %2F needed)
EXPECTED_URI='METRICS_REDIS_URI=redis://:p%40ssword@redis-metrics:6379/0'
if ! echo "$DUMP" | grep -qF "$EXPECTED_URI"; then
  echo "❌ Prod-sim FAIL: expected line '$EXPECTED_URI' not present in dump" >&2
  echo "Full dump:" >&2
  echo "$DUMP" >&2
  exit 1
fi

echo "🔍 Step C.4 — Asserting raw REDIS_PASSWORD was excluded (allow-list intent)..."
if echo "$DUMP" | grep -q "^REDIS_PASSWORD="; then
  echo "❌ Prod-sim FAIL: raw REDIS_PASSWORD present in dump (allow-list should exclude it — URI was pre-assembled at line 40)" >&2
  exit 1
fi

echo "🔍 Step C.5 — Asserting container metadata was excluded..."
for unwanted in PATH HOSTNAME HOME LANG; do
  if echo "$DUMP" | grep -qF "${unwanted}="; then
    echo "❌ Prod-sim FAIL: container metadata var '$unwanted' present in dump (allow-list filter regressed)" >&2
    exit 1
  fi
done

echo "✅ Step C PASSED (prod-sim secret loading + URI assembly + allow-list filter all verified)"
exit 0
