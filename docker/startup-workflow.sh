#!/bin/bash
set +x # Disable command echoing

echo "!!######################################################################################################!!"
echo -e "\nSTARTING DAILY WORKFLOW CONTAINER: $(date +%Y%m%d_%H%M%S)\n"
echo "!!######################################################################################################!!"

# Fix permissions for mounted volumes (running as root)
echo "Setting up volume permissions..."
# /app/volume is the app_logs volume shared with web, whose log dir is owned by web's user (the host
# UID locally), so it is never re-chowned here — workflow joins the log dir's group below instead.
chown -R workflow:workflow /app/workflow_logs /backups 2>/dev/null || true
chmod -R 755 /backups /app/workflow_logs 2>/dev/null || true

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

# The daily log leg (daily-docker.sh -> backup-logs.sh) gzips/prunes in /app/volume/logs, so grant
# workflow membership in that dir's owning group (the dir is group-writable). Must precede
# `exec cron -f`: cron resolves a job user's supplementary groups at job start.
logs_gid=$(stat -c %g /app/volume/logs 2>/dev/null) || logs_gid=""
if [ -z "$logs_gid" ]; then
  echo "WARNING: /app/volume/logs is missing; the daily log backup will fail."
elif [ "$logs_gid" = "0" ]; then
  echo "WARNING: /app/volume/logs is group root; not joining it, so the log-backup leg may be unable to write /app/volume/logs."
else
  getent group "$logs_gid" >/dev/null || groupadd --gid "$logs_gid" u4i-logs
  logs_group=$(getent group "$logs_gid" | cut -d: -f1)
  if [ -n "$logs_group" ]; then
    usermod -aG "$logs_group" workflow
    chmod g+rwX /app/volume/logs
  else
    echo "WARNING: could not resolve group $logs_gid for /app/volume/logs; the log-backup leg may be unable to write it."
  fi
fi

echo -e "\nStarting cron daemon...\n"
exec cron -f
