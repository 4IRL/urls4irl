#!/bin/bash
set +x # Disable command echoing

# Redirecting file stdout/stderr to a daily logfile
# https://unix.stackexchange.com/a/184217
SCRIPT_DIR=$(dirname "$0")
LOGFILE="$SCRIPT_DIR/daily_workflow_logs/$(date +%Y_%m_%d)-daily-workflow-logs.txt"
exec 1>>"$LOGFILE"
exec 2>&1


SENSITIVE_VARS=("R2_ENDPOINT" "SECRET_ACCESS_KEY" "ACCESS_KEY" "DB_PASS" "DB_USER" "DB_NAME" "ACCESS_TOKEN" "INF_ID" "INF_SECRET" "USERNAME" "BACKUP_DIR" "BACKUP_FILE" "COMPRESSED_BACKUP_FILE" "LOG_DIR" "LOG_FILE" "COMPRESSED_LOG_FILE")

# Cleanup function
cleanup_secrets() {
    local exit_code=$?
    echo "----------------------------------------------------"

    if [[ $exit_code -ne 0 ]]; then
      echo "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
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

echo '$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$'
echo -e "\n\nPREPARING TO RUN DAILY TASKS... $(date +%Y%m%d_%H%M%S)\n\n"

source "$SCRIPT_DIR/config.sh"
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in getting daily config setup"
  exit 1
fi
unset INF_ID INF_SECRET ACCESS_TOKEN

source "$SCRIPT_DIR/backup-database.sh"
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in backing up database"
  exit 1
fi
unset DB_PASS DB_USER DB_NAME

source "$SCRIPT_DIR/backup-logs.sh"
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in backing up the daily app logs"
  exit 1
fi

source "$SCRIPT_DIR/remote-object-storage.sh"
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in performing remote object storage"
  exit 1
fi
unset ACCESS_KEY SECRET_ACCESS_KEY R2_ENDPOINT USERNAME
unset BACKUP_DIR BACKUP_FILE COMPRESSED_BACKUP_FILE
unset LOG_DIR LOG_FILE COMPRESSED_LOG_FILE

cleanup_secrets

echo -e "\n\nFINISHED RUNNING DAILY TASKS\n\n"
echo '$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$'
