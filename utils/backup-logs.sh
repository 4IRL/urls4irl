#!/bin/bash
set +x # Disable command echoing

echo "----------------------------------------------------"
echo -e "\n\n START LOG BACKUP SESSION $(date +%Y%m%d_%H%M%S)\n\n"

# ------- BACKUP LOGS, STORE AND COMPRESS ON HOST ------- #

# Compress daily backup on host
echo "Compressing logs on host..."
gzip -c "${LOG_FILE}" > "${COMPRESSED_LOG_FILE}"
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in compressing the logs"
  return 1
fi
echo "Success: Compressed logs on host"

echo "Removing uncompressed daily log files..."
rm -f "${LOG_FILE}"
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in removing uncompressed log files"
  return 1
fi

# ------- ROTATE LOCAL DB's - ONLY STORE PAST 90 DAYS  ------- #
MAX_LOG_FILES=90
NUM_BACKUPS=$(find ${LOG_DIR} -maxdepth 1 -type f | wc -l)
    if [ "$NUM_BACKUPS" -gt "$MAX_LOG_FILES" ]; then
        OLDEST_FILE=$(find ${LOG_DIR} -maxdepth 1 -type f -printf '%T+ %p\n' | sort | head -n 1 | cut -d ' ' -f2-)
        echo "Oldest file is ${OLDEST_FILE}, removing..."
        rm "${OLDEST_FILE}"
        unset OLDEST_FILE
    else
        echo "No local backup files to prune ..."
    fi

unset NUM_BACKUPS

echo -e "\n\n FINISH LOG BACKUP SESSION $(date +%Y%m%d_%H%M%S)\n\n"
echo "----------------------------------------------------"
