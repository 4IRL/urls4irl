#!/bin/bash
set +x # Disable command echoing
SCRIPT_DIR=$(dirname "$0")

# Daily log file
LOGFILE="$SCRIPT_DIR/daily_workflow_logs/$(date +%Y_%m_%d)-daily-workflow-logs.txt"

# Redirecting file stdout/stderr to logfile
# https://unix.stackexchange.com/a/184217
exec 1>>"$LOGFILE"
exec 2>&1

echo '$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$'
echo -e "\n\nPREPARING TO RUN DAILY TASKS... $(date +%Y%m%d_%H%M%S)\n\n"

source "$SCRIPT_DIR/backup-database.sh"
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in backing up database"
  exit 1
fi

echo -e "\n\nFINISHED RUNNING DAILY TASKS\n\n"
echo '$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$'
