#!/bin/bash
set +x # Disable command echoing


echo "!!######################################################################################################!!"
echo -e "\nSTARTING DAILY WORKFLOW CONTAINER: $(date +%Y%m%d_%H%M%S)\n"
echo "!!######################################################################################################!!"

# Fix permissions for mounted volumes (running as root)
echo "Setting up volume permissions..."
chown -R workflow:workflow /app/volume /app/workflow_logs /backups 2>/dev/null || true
chmod -R 755 /backups /app/volume /app/workflow_logs 2>/dev/null || true

if [ "$PRODUCTION" == "true" ]; then
    echo -e "\nLoading environments...\n"
else
    echo -e "\nRunning workflow in development mode\n"
fi

# Write the cron environment dump. build_container_env.py is the single source
# of truth for the allow-list and (in production) the Docker-secret loading +
# METRICS_REDIS_URI percent-encode assembly — extracted from this entrypoint so
# the filter and URI logic are unit-testable without booting the image. It reads
# PRODUCTION / the compose env / /run/secrets itself and writes the KEY=value
# dump; this script only tightens mode + ownership afterward.
echo "Saving environment for cron jobs..."
python3 /app/build_container_env.py

# Ensure proper permissions
# Mode 600 is safe: cron daemon runs as root (Dockerfile.Workflow:88) so it can read regardless of mode bits; cron job lines run as UID 1001 / workflow (Dockerfile.Workflow:43) which owns this file.
chmod 600 /app/container_environment
chown workflow:workflow /app/container_environment

echo -e "\nStarting cron daemon...\n"
exec cron -f
