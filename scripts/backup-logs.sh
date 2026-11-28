#!/bin/bash
set -euo pipefail
set +x # Disable command echoing

echo "----------------------------------------------------"
echo -e "\n\n START LOG BACKUP SESSION $(date +%Y%m%d_%H%M%S)\n\n"

# ------- BACKUP LOGS, STORE AND COMPRESS ON HOST ------- #

# Compress daily backup on host. A run after that day's nightly one (an admin-triggered backup) finds the log
# already compressed and removed, so it reuses that archive instead of failing (#1060).
if [[ ! -f "${LOG_FILE}" && -f "${COMPRESSED_LOG_FILE}" ]]; then
  echo "Logs already compressed by an earlier run: ${COMPRESSED_LOG_FILE}"
else
  echo "Compressing logs on host..."
  if ! gzip -c "${LOG_FILE}" >"${COMPRESSED_LOG_FILE}"; then
    echo "Error: Failure in compressing the logs"
    return 1
  fi
  echo "Success: Compressed logs on host"
fi

# Verify the compressed log archive is a valid gzip (size is not enforced; a quiet day yields a near-empty log)
if ! /opt/metrics-venv/bin/python /app/backup_maintenance.py verify-dump --path "${COMPRESSED_LOG_FILE}" --min-size 0; then
  echo "Error: log backup failed integrity verification"
  return 1
fi

echo "Removing uncompressed daily log files..."
if ! rm -f "${LOG_FILE}"; then
  echo "Error: Failure in removing uncompressed log files"
  return 1
fi

# ------- ROTATE LOCAL DB's - ONLY STORE PAST 90 DAYS  ------- #
if ! /opt/metrics-venv/bin/python /app/backup_maintenance.py prune-logs --directory "${LOG_DIR}" --pattern '*_daily.log.gz' --max-files 90; then
  echo "Warning: log prune failed"
fi

echo -e "\n\n FINISH LOG BACKUP SESSION $(date +%Y%m%d_%H%M%S)\n\n"
echo "----------------------------------------------------"
