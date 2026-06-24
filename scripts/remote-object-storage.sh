#!/bin/bash
set -euo pipefail
set +x # Disable command echoing

remote_backup() {
  local database_success="${1:-}"
  local log_success="${2:-}"
  local failure=0
  local db_mime_type=""
  local log_mime_type=""
  REMOTE_BACKUP_ERROR=""

  if [[ "${PRODUCTION:-}" != "true" ]]; then
    echo -e "\n\n Skipping remote object storage due to not in production \n\n"
    REMOTE_BACKUP_ERROR="Error: Failure in sending daily database backup to Cloudflare R2"
    failure=1
    return $failure
  fi

  # Configure rclone via environment variables (no plaintext config file on disk)
  export RCLONE_CONFIG_REMOTE_TYPE=s3
  export RCLONE_CONFIG_REMOTE_PROVIDER=Cloudflare
  export RCLONE_CONFIG_REMOTE_ACCESS_KEY_ID="$ACCESS_KEY"
  export RCLONE_CONFIG_REMOTE_SECRET_ACCESS_KEY="$SECRET_ACCESS_KEY"
  export RCLONE_CONFIG_REMOTE_ACL=private
  export RCLONE_CONFIG_REMOTE_ENDPOINT="$R2_ENDPOINT"
  export RCLONE_CONFIG_REMOTE_NO_CHECK_BUCKET=true

  echo "----------------------------------------------------"
  echo -e "\n\n START REMOTE OBJECT STORAGE SESSION $(date +%Y%m%d_%H%M%S)\n\n"

  # ------- SEND DATABASE AND LOG BACKUP TO R2 ------- #

  unset ACCESS_KEY SECRET_ACCESS_KEY R2_ENDPOINT

  # Send database backup using rclone
  if [ "$database_success" = "true" ]; then
    echo "Copying daily database backup to Cloudflare R2..."
    db_mime_type=$(file --mime-type -b "${COMPRESSED_DB_BACKUP_FILE}")

    if ! rclone copy "${COMPRESSED_DB_BACKUP_FILE}" "remote:u4i-backups/" \
      --s3-no-check-bucket \
      --header-upload "Content-Type:$db_mime_type"; then
      echo "Error: Failure in sending daily database backup to Cloudflare R2"
      REMOTE_BACKUP_ERROR="Error: Failure in sending daily database backup to Cloudflare R2"
      failure=1
    else
      echo "Success: Sent daily database backup to Cloudflare R2"
    fi

    # ------- IF FIRST OF MONTH, SEND A FIRST-OF-MONTH DATABASE BACKUP  ------- #

    CURRENT_DAY=$(date +%d)
    if [ "$CURRENT_DAY" -eq 1 ]; then
      # First day of the month, send a monthly backup
      monthly_file="${COMPRESSED_DB_BACKUP_FILE/daily/monthly}"
      cp "${COMPRESSED_DB_BACKUP_FILE}" "${monthly_file}"
      if ! rclone copy "${monthly_file}" "remote:u4i-backups/" \
        --s3-no-check-bucket \
        --header-upload "Content-Type:$db_mime_type"; then
        echo "Error: Failure in sending monthly database backup to Cloudflare R2"
        REMOTE_BACKUP_ERROR="Error: Failure in sending monthly database backup to Cloudflare R2"
        failure=1
      else
        echo "Success: Sent monthly database backup to Cloudflare R2"
      fi
      rm -f "${monthly_file}"
    fi
  else
    echo "Skipping database remote backup due to local backup failure"
    REMOTE_BACKUP_ERROR="Skipping database remote backup due to local backup failure"
    failure=1
  fi

  # Send logs backup using rclone
  if [ "$log_success" == "true" ]; then
    echo "Copying daily app logs to Cloudflare R2..."
    log_mime_type=$(file --mime-type -b "${COMPRESSED_LOG_FILE}")
    if ! rclone copy "${COMPRESSED_LOG_FILE}" "remote:u4i-logs/" \
      --s3-no-check-bucket \
      --header-upload "Content-Type:$log_mime_type"; then
      echo "Error: Failure in sending daily app logs to Cloudflare R2"
      REMOTE_BACKUP_ERROR="Error: Failure in sending daily app logs to Cloudflare R2"
      failure=1
    else
      echo "Success: Sent daily app logs to Cloudflare R2"
    fi
  else
    echo "Skipping log remote backup due to local backup failure"
    REMOTE_BACKUP_ERROR="Skipping log remote backup due to local backup failure"
    failure=1
  fi

  unset RCLONE_CONFIG_REMOTE_ACCESS_KEY_ID RCLONE_CONFIG_REMOTE_SECRET_ACCESS_KEY RCLONE_CONFIG_REMOTE_ENDPOINT
  unset DB_BACKUP_DIR

  echo -e "\n\n FINISH REMOTE OBJECT STORAGE SESSION $(date +%Y%m%d_%H%M%S)\n\n"
  echo "----------------------------------------------------"

  return $failure
}
