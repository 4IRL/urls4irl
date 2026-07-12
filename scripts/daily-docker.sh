#!/bin/bash
set -euo pipefail
set +x # Disable command echoing

SENSITIVE_VARS=("R2_ENDPOINT" "SECRET_ACCESS_KEY" "ACCESS_KEY" "DB_PASS" "DB_USER" "DB_NAME" "ACCESS_TOKEN" "DB_BACKUP_DIR" "DB_BACKUP_FILE" "COMPRESSED_DB_BACKUP_FILE" "LOG_DIR" "LOG_FILE" "COMPRESSED_LOG_FILE" "FINAL_LOG_FILE" "TMP_LOG_DIR" "NOTIFICATION_URL" "RCLONE_CONFIG_REMOTE_ACCESS_KEY_ID" "RCLONE_CONFIG_REMOTE_SECRET_ACCESS_KEY" "RCLONE_CONFIG_REMOTE_ENDPOINT" PGPASSWORD)

# Cleanup function
cleanup_secrets() {
  local exit_code=$?
  echo "----------------------------------------------------"

  if [[ $exit_code -ne 0 ]]; then
    echo -e "\nXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
    echo -e "\n\n SCRIPT EXITED IN ERROR \n\n"
    echo "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
  fi

  echo -e "\n\n Cleaning up sensitive variables...\n\n"
  echo "----------------------------------------------------"
  for var in "${SENSITIVE_VARS[@]}"; do
    if [[ -n "${!var:-}" ]]; then
      # Get the variable value and its length
      local var_value="${!var}"
      local var_length=${#var_value}
      if [[ $var_length -gt 0 ]]; then
        # Overwrite with random data
        eval "$var=\"$(head -c $var_length /dev/urandom 2>/dev/null | base64 2>/dev/null | head -c $var_length || echo '')\""
      fi
      unset "$var"
    fi
  done

  if [[ -n "${WORKFLOW_LOG_DIR:-}" ]]; then
    if ! /opt/metrics-venv/bin/python /app/backup_maintenance.py prune-logs --directory "$WORKFLOW_LOG_DIR" --pattern '*-daily-workflow-logs.txt' --max-files 90; then
      echo "Warning: workflow_logs prune failed"
    fi
  fi
}

trap cleanup_secrets EXIT

# Make sure cron jobs load the Docker compose environment
if [[ -f /app/container_environment ]]; then
  . /app/container_environment
else
  echo "ERROR: /app/container_environment not found!"
  exit 1
fi

# Redirecting file stdout/stderr to a daily logfile
# https://unix.stackexchange.com/a/184217
SCRIPT_DIR=$(dirname "$0")
WORKFLOW_LOG_DIR="$SCRIPT_DIR/workflow_logs"
mkdir -p "$WORKFLOW_LOG_DIR"
LOGFILE="$WORKFLOW_LOG_DIR/$(date +%Y_%m_%d)-daily-workflow-logs.txt"

exec 1>>"$LOGFILE"
exec 2>&1

# Source of this run: "scheduled" (the 1 AM cron) or "manual" (an admin's
# Trigger Backup action, exported by run_backup_if_requested.py). Surfaced in
# every Discord message so a manual run is distinguishable from the nightly one.
BACKUP_TRIGGER_SOURCE="${BACKUP_TRIGGER_SOURCE:-scheduled}"

notify_step() {
  /opt/metrics-venv/bin/python /app/scripts/notify.py --job "$1" --status "$2" --detail "${3:-}" --trigger "$BACKUP_TRIGGER_SOURCE" || true
}

echo '$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$'
echo -e "\n\nPREPARING TO RUN DAILY TASKS... $(date +%Y%m%d_%H%M%S)\n\n"

# Fail fast WITH a notification if any required Postgres var is missing or empty.
# These are sourced from /app/container_environment. Without this guard, set -u
# would abort at the first ${POSTGRES_DB} expansion below — before the backup
# block could send a failure notification — leaving only a cron.log line as the
# signal. Checking here turns a silent misconfiguration into a notified one.
for required_var in POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD; do
  if [[ -z "${!required_var:-}" ]]; then
    echo "Error: required environment variable ${required_var} is missing or empty"
    notify_step "DAILY" "FAILURE" "Error: required environment variable ${required_var} is missing or empty — aborting daily backup"
    exit 1
  fi
done

# Build variables for database backup
DB_BACKUP_DIR="/backups/"
DB_BACKUP_FILE="${DB_BACKUP_DIR}${POSTGRES_DB}_$(date +%Y%m%d_%H%M%S)_daily.sql"
COMPRESSED_DB_BACKUP_FILE="${DB_BACKUP_FILE}.gz"
DB_USER=${POSTGRES_USER}
DB_PASS=${POSTGRES_PASSWORD}
DB_NAME=${POSTGRES_DB}
export DB_BACKUP_FILE COMPRESSED_DB_BACKUP_FILE DB_USER DB_PASS DB_NAME DB_BACKUP_DIR

# Per-step notifications fire on FAILURE only — per-step SUCCESS is intentionally
# silent because the end-of-run digest already reports each leg's outcome.
database_backed_up="true"
if ! source "$SCRIPT_DIR/backup-database.sh"; then
  echo "Error: Failure in daily local backup of database"
  notify_step "DB_BACKUP" "FAILURE" "Error: Failure in daily local backup of database"
  database_backed_up="false"
fi
unset DB_BACKUP_FILE DB_USER DB_PASS DB_NAME

# Build variables for logging backup
LOG_DIR="/app/volume/logs"
LOG_FILE="${LOG_DIR}/$(date -d "yesterday" +%Y-%m-%d)_daily.log"
COMPRESSED_LOG_FILE="${LOG_FILE}.gz"
export LOG_FILE COMPRESSED_LOG_FILE

logs_backed_up="true"
if ! source "$SCRIPT_DIR/backup-logs.sh"; then
  echo "Error: Failure in daily local backup of app logs"
  notify_step "LOG_BACKUP" "FAILURE" "Error: Failure in daily local backup of app logs: $(date -d "yesterday" +%Y-%m-%d).log"
  logs_backed_up="false"
fi

unset LOG_FILE LOG_DIR

source "$SCRIPT_DIR/remote-object-storage.sh"
remote_exit=0
remote_backup "$database_backed_up" "$logs_backed_up" || remote_exit=$?
if [[ $remote_exit -ne 0 ]]; then
  echo "Error: Failure in daily export of backups to remote object storage"
fi

/opt/metrics-venv/bin/python /app/scripts/notify.py --summary \
  --database "$([ "$database_backed_up" = "true" ] && echo ok || echo fail)" \
  --logs "$([ "$logs_backed_up" = "true" ] && echo ok || echo fail)" \
  --remote-db "${REMOTE_DB_STATUS:-skip}" \
  --remote-monthly "${REMOTE_DB_MONTHLY_STATUS:-skip}" \
  --remote-logs "${REMOTE_LOGS_STATUS:-skip}" \
  --trigger "$BACKUP_TRIGGER_SOURCE" || true

# Stamp the backup last-success sentinel in the metrics Redis (read by the
# admin health dashboard). Best-effort: a Redis hiccup never fails the
# pipeline. METRICS_REDIS_URI is passed explicitly because the environment
# file above is sourced without allexport.
if [[ "$database_backed_up" == "true" ]]; then
  if ! METRICS_REDIS_URI="${METRICS_REDIS_URI:-}" /opt/metrics-venv/bin/python "$SCRIPT_DIR/backup_sentinel.py"; then
    echo "Warning: backup last-success sentinel stamp failed"
  fi
fi

exit $remote_exit
