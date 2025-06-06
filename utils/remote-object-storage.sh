#!/bin/bash
set +x # Disable command echoing

echo "----------------------------------------------------"
echo -e "\n\n START REMOTE OBJECT STORAGE SESSION $(date +%Y%m%d_%H%M%S)\n\n"

# ------- SEND DATABASE BACKUP TO R2 ------- #

# Create rclone config file
CONFIG_FILE="/home/$USERNAME/secrets/rclone-config.txt"
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
echo "Copying daily database backup to Cloudflare R2..."
rclone --config="$CONFIG_FILE" copy "${BACKUP_DIR}${COMPRESSED_BACKUP_FILE}_daily.gz" "remote:u4i-backups/" --progress --s3-no-check-bucket
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in sending daily database backup to Cloudflare R2"
else
  echo "Success: Sent daily database backup to Cloudflare R2"
fi

# ------- IF FIRST OF MONTH, SEND A FIRST-OF-MONTH DATABASE BACKUP  ------- #

CURRENT_DAY=$(date +%d)
if [ "$CURRENT_DAY" -eq 1 ]; then
  # First day of the month, send a monthly backup
  cp "${BACKUP_DIR}${COMPRESSED_BACKUP_FILE}_daily.gz" "${BACKUP_DIR}${COMPRESSED_BACKUP_FILE}_monthly.gz"
  rclone --config="$CONFIG_FILE" copy "${BACKUP_DIR}${COMPRESSED_BACKUP_FILE}_monthly.gz" "remote:u4i-backups/" --progress --s3-no-check-bucket
  if [ "$?" -ne 0 ]; then
    echo "Error: Failure in sending monthly database backup to Cloudflare R2"
  else
  echo "Success: Sent monthly database backup to Cloudflare R2"
  fi
  rm "${BACKUP_DIR}${COMPRESSED_BACKUP_FILE}_monthly.gz"
fi

# Send logs backup using rclone
echo "Copying daily app logs to Cloudflare R2..."
rclone --config="$CONFIG_FILE" copy "${LOG_DIR}${COMPRESSED_LOG_FILE}_daily.gz" "remote:u4i-logs/" --progress --s3-no-check-bucket
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in sending daily app logs to Cloudflare R2"
else
  echo "Success: Sent daily app logs to Cloudflare R2"
fi

rm "$CONFIG_FILE"
unset CONFIG_FILE

echo -e "\n\n FINISH REMOTE OBJECT STORAGE SESSION $(date +%Y%m%d_%H%M%S)\n\n"
echo "----------------------------------------------------"
