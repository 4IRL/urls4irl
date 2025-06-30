#!/bin/bash

remote_backup() {
  set +x # Disable command echoing

  local database_success="$1"
  local log_success="$2"

  if [[ "$PRODUCTION" != "true" ]]; then
    database_success="false"
    log_success="false"
  fi

  echo "----------------------------------------------------"
  echo -e "\n\n START REMOTE OBJECT STORAGE SESSION $(date +%Y%m%d_%H%M%S)\n\n"

  # ------- SEND DATABASE AND LOG BACKUP TO R2 ------- #

  # Create rclone config file
  CONFIG_FILE="${DB_BACKUP_DIR}/rclone-config.txt"
  cat > "$CONFIG_FILE" <<EOF
[remote]
type = s3
provider = Cloudflare
access_key_id = $ACCESS_KEY
secret_access_key = $SECRET_ACCESS_KEY
acl = private
endpoint = $R2_ENDPOINT
no_check_bucket = true
EOF

  unset ACCESS_KEY SECRET_ACCESS_KEY R2_ENDPOINT

  # Send database backup using rclone
  if [ "$database_success" = "true" ]; then
    echo "Copying daily database backup to Cloudflare R2..."
    rclone --config="$CONFIG_FILE" copy "${COMPRESSED_DB_BACKUP_FILE}" "remote:u4i-backups/" --progress --s3-no-check-bucket
    if [ "$?" -ne 0 ]; then
      echo "Error: Failure in sending daily database backup to Cloudflare R2"
    else
      echo "Success: Sent daily database backup to Cloudflare R2"
    fi

    # ------- IF FIRST OF MONTH, SEND A FIRST-OF-MONTH DATABASE BACKUP  ------- #

    CURRENT_DAY=$(date +%d)
    if [ "$CURRENT_DAY" -eq 1 ]; then
      # First day of the month, send a monthly backup
      monthly_file="${COMPRESSED_DB_BACKUP_FILE//\/daily\//\/monthly\/}"
      cp "${COMPRESSED_DB_BACKUP_FILE}" "${monthly_file}"
      rclone --config="$CONFIG_FILE" copy "${monthly_file}" "remote:u4i-backups/" --progress --s3-no-check-bucket
      if [ "$?" -ne 0 ]; then
        echo "Error: Failure in sending monthly database backup to Cloudflare R2"
      else
      echo "Success: Sent monthly database backup to Cloudflare R2"
      fi
      rm "${monthly_file}"
    fi
  else
    echo "Skipping database remote backup due to local backup failure"
  fi

  # Send logs backup using rclone
  if [ "$log_success" == "true" ]; then
    echo "Copying daily app logs to Cloudflare R2..."
    rclone --config="$CONFIG_FILE" copy "${COMPRESSED_LOG_FILE}" "remote:u4i-logs/" --progress --s3-no-check-bucket
    if [ "$?" -ne 0 ]; then
      echo "Error: Failure in sending daily app logs to Cloudflare R2"
    else
      echo "Success: Sent daily app logs to Cloudflare R2"
    fi
  else
    echo "Skipping log remote backup due to local backup failure"
  fi

  rm "$CONFIG_FILE"
  unset CONFIG_FILE DB_BACKUP_DIR

  echo -e "\n\n FINISH REMOTE OBJECT STORAGE SESSION $(date +%Y%m%d_%H%M%S)\n\n"
  echo "----------------------------------------------------"
}
