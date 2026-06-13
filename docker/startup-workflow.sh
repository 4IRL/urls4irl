#!/bin/bash
set +x # Disable command echoing


echo "!!######################################################################################################!!"
echo -e "\nSTARTING DAILY WORKFLOW CONTAINER: $(date +%Y%m%d_%H%M%S)\n"
echo "!!######################################################################################################!!"

# Fix permissions for mounted volumes (running as root)
echo "Setting up volume permissions..."
chown -R workflow:workflow /app/volume /app/workflow_logs /backups 2>/dev/null || true
chmod -R 755 /backups /app/volume /app/workflow_logs 2>/dev/null || true

# Function to load secrets from Docker secrets
load_secrets() {
    echo -e "Loading secrets..."
    
    # Load secrets from files and export them
    for secret_file in /run/secrets/*; do
        if [ -f "$secret_file" ]; then
            secret_name=$(basename "$secret_file")
            secret_value=$(cat "$secret_file")
            export "$secret_name"="$secret_value"
            echo -e "Loaded secret: $secret_name"
        fi
    done
}

if [ "$PRODUCTION" == "true" ]; then
    echo -e "\nLoading environments...\n"
    load_secrets
    # Assemble METRICS_REDIS_URI from REDIS_PASSWORD secret. The workflow
    # container only writes to the metrics DB on the dedicated `redis-metrics`
    # container (no sessions, no rate-limiter), so it does not need REDIS_URI.
    # Mirrors the assembly in backend/config.py for the web container —
    # including the urllib.parse.quote percent-encode so passwords containing
    # URL-special characters (@, :, #, ?) do not produce a malformed URI here
    # while web connects fine.
    ENCODED_REDIS_PASSWORD=$(printf '%s' "${REDIS_PASSWORD}" | python3 -c 'import sys, urllib.parse; sys.stdout.write(urllib.parse.quote(sys.stdin.read()))')
    export METRICS_REDIS_URI="redis://:${ENCODED_REDIS_PASSWORD}@redis-metrics:6379/0"
else
    echo -e "\nRunning workflow in development mode\n"
fi

# Dump current env to a file readable by cron jobs
echo "Saving environment for cron jobs..."
ALLOW_VARS=(
  ACCESS_KEY
  DEV_SERVER
  METRICS_FLUSH_LIVENESS_THRESHOLD_SECONDS
  METRICS_REDIS_URI
  NOTIFICATION_URL
  POSTGRES_DB
  POSTGRES_HOST
  POSTGRES_PASSWORD
  POSTGRES_PORT
  POSTGRES_USER
  PRODUCTION
  R2_ENDPOINT
  SECRET_ACCESS_KEY
)
: > /app/container_environment
for var in "${ALLOW_VARS[@]}"; do
  if [[ -n "${!var+x}" ]]; then
    printf '%s=%s\n' "$var" "${!var}" >> /app/container_environment
  fi
done

# Ensure proper permissions
# Mode 600 is safe: cron daemon runs as root (Dockerfile.Workflow:88) so it can read regardless of mode bits; cron job lines run as UID 1001 / workflow (Dockerfile.Workflow:43) which owns this file.
chmod 600 /app/container_environment
chown workflow:workflow /app/container_environment

echo -e "\nStarting cron daemon...\n"
exec cron -f
