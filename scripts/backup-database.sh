#!/bin/bash
set -euo pipefail
set +x # Disable command echoing

echo "----------------------------------------------------"
echo -e "\n\n START LOCAL DATABASE BACKUP SESSION $(date +%Y%m%d_%H%M%S)\n\n"

# ------- BACKUP DATABASE, STORE AND COMPRESS ON HOST ------- #

echo "Generating backup and storing on the host..."
if ! PGPASSWORD="$DB_PASS" pg_dump -h "db" -U "$DB_USER" -d "$DB_NAME" --clean --if-exists --create > "${DB_BACKUP_FILE}"; then
  echo "Error: Failure in generating backup in docker container"
  return 1
fi
echo "Success: Generated backup and stored on host"

unset DB_PASS DB_USER DB_NAME

# Compress daily backup on host
echo "Compressing backup on host..."
if ! gzip -c "${DB_BACKUP_FILE}" > "${COMPRESSED_DB_BACKUP_FILE}"; then
  echo "Error: Failure in compressing the backup"
  return 1
fi
echo "Success: Compressed backup on host"

# Verify the compressed dump is a valid gzip and large enough to be a real dump
if ! /opt/metrics-venv/bin/python /app/backup_maintenance.py verify-dump --path "${COMPRESSED_DB_BACKUP_FILE}" --min-size 1024; then
  echo "Error: DB backup failed integrity/size verification"
  return 1
fi

# Remove original uncompressed file
rm "${DB_BACKUP_FILE}"

# ------- ROTATE LOCAL DB's - ONLY STORE PAST 90 DAYS  ------- #
MAX_BACKUP_FILES=90
NUM_BACKUPS=$(find "${DB_BACKUP_DIR}" -maxdepth 1 -type f | wc -l)
    if [ "$NUM_BACKUPS" -gt "$MAX_BACKUP_FILES" ]; then
        OLDEST_FILE=$(find "${DB_BACKUP_DIR}" -maxdepth 1 -type f -printf '%T+ %p\n' | sort | head -n 1 | cut -d ' ' -f2-)
        echo "Oldest file is ${OLDEST_FILE}, removing..."
        rm "${OLDEST_FILE}"
        unset OLDEST_FILE
    else
        echo "No local backup files to prune ..."
    fi

unset NUM_BACKUPS DB_BACKUP_FILE


echo -e "\n\n FINISH LOCAL DATABASE BACKUP SESSION $(date +%Y%m%d_%H%M%S)\n\n"
echo "----------------------------------------------------"
