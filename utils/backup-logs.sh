#!/bin/bash
set +x # Disable command echoing

echo "----------------------------------------------------"
echo -e "\n\n START LOG BACKUP SESSION $(date +%Y%m%d_%H%M%S)\n\n"


# ------- BACKUP DATABASE, STORE AND COMPRESS ON HOST ------- #

# Create backup and store on host
echo "Generating log backup and storing on the host..."
docker logs --since=24h u4i-prod-flask &> "${TMP_LOG_DIR}${LOG_FILE}"
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in generating app logs from docker container"
  exit 1
fi
echo "Success: Generated app logs for day and stored on host"

FINAL_LOG_FILE="log_$(date +%Y%m%d_%H%M%S).txt"
echo "Appending all logs into one single file..."
find "${TMP_LOG_DIR}" -name "*.txt" -type f | sort | xargs cat > "${LOG_DIR}${FINAL_LOG_FILE}"
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in appending all logs together"
  exit 1
fi

echo "Removing all temporary daily log files..."
rm -f "${TMP_LOG_DIR}"*
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in removing the temporary log files"
  exit 1
fi

# Compress daily backup on host
echo "Compressing logs on host..."
gzip -c "${LOG_DIR}${FINAL_LOG_FILE}" > "${LOG_DIR}${COMPRESSED_LOG_FILE}_daily.gz"
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in compressing the logs"
  exit 1
fi
echo "Success: Compressed logs on host"

# Remove original uncompressed file
rm "${LOG_DIR}${FINAL_LOG_FILE}"

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
