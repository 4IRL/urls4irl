#!/bin/bash
set +x # Disable command echoing

SENSITIVE_VARS=("R2_ENDPOINT" "SECRET_ACCESS_KEY" "ACCESS_KEY" "DB_PASS" "DB_USER" "DB_NAME" "ACCESS_TOKEN" "DB_BACKUP_DIR" "DB_BACKUP_FILE" "COMPRESSED_DB_BACKUP_FILE" "LOG_DIR" "LOG_FILE" "COMPRESSED_LOG_FILE" "FINAL_LOG_FILE" "TMP_LOG_DIR" "NOTIFICATION_URL" PGPASSWORD)

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
}

trap cleanup_secrets EXIT

# Make sure cron jobs load the Docker compose environment
if [[ -f /etc/container_environment ]]; then
  . /etc/container_environment
fi

# Redirecting file stdout/stderr to a daily logfile
# https://unix.stackexchange.com/a/184217
SCRIPT_DIR=$(dirname "$0")
WORKFLOW_LOG_DIR="$SCRIPT_DIR/workflow_logs"
mkdir -p "$WORKFLOW_LOG_DIR"
LOGFILE="$WORKFLOW_LOG_DIR/$(date +%Y_%m_%d)-daily-workflow-logs.txt"

exec 1>>"$LOGFILE"
exec 2>&1

send_notification_msg() {
    local output="$1"
    if [[ "$PRODUCTION" != "true" ]]; then
        output="IGNORE, IN DEVELOPMENT: $output"
    fi
    #TODO: Remove DOCKER prefix once we verify this is working in prod
    if [[ "$DEV_SERVER" == "true" || "$PRODUCTION" != "true" ]]; then
          echo "DOCKER: $output"
    else
        restricted_curl "POST" "$NOTIFICATION_URL" "DOCKER: $output"
    fi
    if [ "$?" -ne 0 ]; then
      echo "Error: Failure in sending notification"
    fi
}

echo '$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$'
echo -e "\n\nPREPARING TO RUN DAILY TASKS... $(date +%Y%m%d_%H%M%S)\n\n"

# Build variables for database backup
DB_BACKUP_DIR="/backups/"
DB_BACKUP_FILE="${DB_BACKUP_DIR}${POSTGRES_DB}_$(date +%Y%m%d_%H%M%S)_daily.sql"
COMPRESSED_DB_BACKUP_FILE="${DB_BACKUP_FILE}.gz"
DB_USER=${POSTGRES_USER}
DB_PASS=${POSTGRES_PASSWORD}
DB_NAME=${POSTGRES_DB}
export DB_BACKUP_FILE COMPRESSED_DB_BACKUP_FILE DB_USER DB_PASS DB_NAME DB_BACKUP_DIR

database_backed_up="true"
source "$SCRIPT_DIR/backup-database.sh"
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in daily local backup of database"
  send_notification_msg "Error: Failure in daily local backup of database"
  database_backed_up="false"
fi
unset DB_BACKUP_FILE DB_USER DB_PASS DB_NAME

# Build variables for logging backup
LOG_DIR="/app/volume/logs"
LOG_FILE="${LOG_DIR}/$(date -d "yesterday" +%Y-%m-%d)_daily.log"
COMPRESSED_LOG_FILE="${LOG_FILE}.gz"
export LOG_FILE COMPRESSED_LOG_FILE

logs_backed_up="true"
source "$SCRIPT_DIR/backup-logs.sh"
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in daily local backup of app logs"
  send_notification_msg "Error: Failure in daily local backup of app logs: $(date -d "yesterday" +%Y-%m-%d).log"
  logs_backed_up="false"
fi

unset LOG_FILE LOG_DIR


source "$SCRIPT_DIR/remote-object-storage.sh"
remote_backup "$database_backed_up" "$logs_backed_up"
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in daily export of backups to remote object storage"
  send_notification_msg "Remote Backup Failure: $REMOTE_BACKUP_ERROR"
  exit 1
fi

send_notification_msg "Success: Backups saved and exported to cloud"
unset ACCESS_KEY SECRET_ACCESS_KEY R2_ENDPOINT
unset DB_BACKUP_DIR COMPRESSED_DB_BACKUP_FILE
unset COMPRESSED_LOG_FILE
unset NOTIFICATION_URL

cleanup_secrets

echo -e "\n\nFINISHED RUNNING DAILY TASKS\n\n"
echo '$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$'

if [[ "$PRODUCTION" != "true" ]]; then
    echo "Testing logs for development - $(date +%Y%m%d_%H%M%S)"
    send_notification_msg "Testing logs for development - $(date +%Y%m%d_%H%M%S)"
    exit 0
fi
