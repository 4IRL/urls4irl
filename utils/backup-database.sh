#!/bin/bash
set +x # Disable command echoing

echo "----------------------------------------------------"
echo -e "\n\n START BACKUP SESSION $(date +%Y%m%d_%H%M%S)\n\n"

USERNAME=$(< ./secrets/username)

# ------- GET SECRETS ------- #

# Get infisical login parameters
ID=$(< ./secrets/inf_id)
SECRET=$(< ./secrets/inf_secret)
INFISICAL_URL="https://us.infisical.com/api/v3/secrets/raw/"
ENVIRONMENT_WORKSPACE="?environment=prod&workspaceSlug=u4-i-fv-ya"

# Make cURL request to get the access token
echo "Fetching access token..."
response=$(restricted_curl POST "https://app.infisical.com/api/v1/auth/universal-auth/login" "$ID" "$SECRET")

if [ "$?" -ne 0 ]; then
  echo "Error: Failure in fetching access token"
  exit 1
fi
echo "Success: Fetched access token"

# Parse for access token
echo "Parsing access token..."
ACCESS_TOKEN=$(echo $response | jq -r '.accessToken')
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in parsing for access token"
  exit 1
fi
if [[ ! $ACCESS_TOKEN ]]; then
  echo "Error: Empty access token"
  exit 1
fi
echo "Success: Parsed access token"

# Get all credentials
response=$(restricted_curl GET "https://us.infisical.com/api/v3/secrets/raw?environment=prod&workspaceSlug=u4-i-fv-ya&tagSlugs=prod-pull" "${ACCESS_TOKEN}")
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in fetching credentials"
  exit 1
fi
echo "Success: Fetched credentials"

# Parse for DB PASSWORD
echo "Parsing DB Password..."
DB_PASS=$(echo $response | jq -r --arg key "PROD_DB_PASSWORD" '.secrets[] | select(.secretKey == $key) | .secretValue')
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in parsing for DB Pass"
  exit 1
fi
if [[ ! $DB_PASS ]]; then
  echo "Error: Empty DB Pass"
  exit 1
fi
echo "Success: Parsed DB Pass"

# Parse for DB USER
echo "Parsing DB User..."
DB_USER=$(echo $response | jq -r --arg key "PROD_DB_USER" '.secrets[] | select(.secretKey == $key) | .secretValue')
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in parsing for DB User"
  exit 1
fi
if [[ ! $DB_USER ]]; then
  echo "Error: Empty DB User"
  exit 1
fi
echo "Success: Parsed DB User"

# Parse for DB USER
echo "Parsing DB Name..."
DB_NAME=$(echo $response | jq -r --arg key "PROD_DB_NAME" '.secrets[] | select(.secretKey == $key) | .secretValue')
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in parsing for DB Name"
  exit 1
fi
if [[ ! $DB_NAME ]]; then
  echo "Error: Empty DB Name"
  exit 1
fi
echo "Success: Parsed DB Name"

# Parse for R2 Access Key
echo "Parsing Access Key..."
ACCESS_KEY=$(echo $response | jq -r --arg key "CF_ACCESS_KEY_ID" '.secrets[] | select(.secretKey == $key) | .secretValue')
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in parsing for Access Key"
  exit 1
fi
if [[ ! $ACCESS_KEY ]]; then
  echo "Error: Empty Access Key"
  exit 1
fi
echo "Success: Parsed Access Key"

# Parse for R2 Access Key
echo "Parsing Secret Access Key..."
SECRET_ACCESS_KEY=$(echo $response | jq -r --arg key "CF_SECRET_ACCESS_KEY" '.secrets[] | select(.secretKey == $key) | .secretValue')
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in parsing for Secret Access Key"
  exit 1
fi
if [[ ! $SECRET_ACCESS_KEY ]]; then
  echo "Error: Empty Secret Access Key"
  exit 1
fi
echo "Success: Parsed Secret Access Key"

# Parse for R2 Endpoint
echo "Parsing R2 Endpoint..."
R2_ENDPOINT=$(echo $response | jq -r --arg key "S3_ENDPOINT" '.secrets[] | select(.secretKey == $key) | .secretValue')
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in parsing for R2 Endpoint"
  exit 1
fi
if [[ ! $R2_ENDPOINT ]]; then
  echo "Error: Empty R2 Endpoint"
  exit 1
fi
echo "Success: Parsed R2 Endpoint"


# ------- BACKUP DATABASE, STORE AND COMPRESS ON HOST ------- #

BACKUP_DIR="/home/$USERNAME/backups/"
BACKUP_FILE="${DB_NAME}_$(date +%Y%m%d_%H%M%S).sql"
COMPRESSED_BACKUP_FILE="${BACKUP_FILE}"

# Create backup and store on host
echo "Generating backup and storing on the host..."
docker exec -i --env PGPASSWORD="$DB_PASS" u4i-prod-postgres pg_dump -U "$DB_USER" "$DB_NAME" > "${BACKUP_DIR}${BACKUP_FILE}"
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in generating backup in docker container"
  exit 1
fi
echo "Success: Generated backup and stored on host"

# Compress daily backup on host
echo "Compressing backup on host..."
gzip -c "${BACKUP_DIR}${BACKUP_FILE}" > "${BACKUP_DIR}${COMPRESSED_BACKUP_FILE}_daily.gz"
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in compressing the backup"
  exit 1
fi
echo "Success: Compressed backup on host"

# Remove original uncompressed file
rm "${BACKUP_DIR}${BACKUP_FILE}"

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

# Send using rclone
echo "Copying daily backup to Cloudflare R2..."
rclone --config="$CONFIG_FILE" copy "${BACKUP_DIR}${COMPRESSED_BACKUP_FILE}_daily.gz" "remote:u4i-backups/" --progress --s3-no-check-bucket
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in sending daily backup to Cloudflare R2"
else
  echo "Success: Sent daily backup to Cloudflare R2"
fi

# ------- IF FIRST OF MONTH, SEND A FIRST-OF-MONTH BACKUP  ------- #

CURRENT_DAY=$(date +%d)
if [ "$CURRENT_DAY" -eq 1 ]; then
  # First day of the month, send a monthly backup
  cp "${BACKUP_DIR}${COMPRESSED_BACKUP_FILE}_daily.gz" "${BACKUP_DIR}${COMPRESSED_BACKUP_FILE}_monthly.gz"
  rclone --config="$CONFIG_FILE" copy "${BACKUP_DIR}${COMPRESSED_BACKUP_FILE}_monthly.gz" "remote:u4i-backups/" --progress --s3-no-check-bucket
  if [ "$?" -ne 0 ]; then
    echo "Error: Failure in sending monthly backup to Cloudflare R2"
  else
  echo "Success: Sent monthly backup to Cloudflare R2"
  fi
  rm "${BACKUP_DIR}${COMPRESSED_BACKUP_FILE}_monthly.gz"
fi

rm "$CONFIG_FILE"

# ------- UNSET  ------- #
unset ACCESS_TOKEN DB_PASS DB_USER DB_NAME
unset ACCESS_KEY SECRET_ACCESS_KEY R2_ENDPOINT
unset RCLONE_CONFIG_R2_TYPE
unset RCLONE_CONFIG_R2_PROVIDER
unset RCLONE_CONFIG_R2_ACCESS_KEY_ID
unset RCLONE_CONFIG_R2_SECRET_ACCESS_KEY
unset RCLONE_CONFIG_R2_ENDPOINT


# ------- ROTATE LOCAL DB's - ONLY STORE PAST 90 DAYS  ------- #
MAX_BACKUP_FILES=90
NUM_BACKUPS=$(find ${BACKUP_DIR} -maxdepth 1 -type f | wc -l)
    if [ "$NUM_BACKUPS" -gt "$MAX_BACKUP_FILES" ]; then
        OLDEST_FILE=$(find ${BACKUP_DIR} -maxdepth 1 -type f -printf '%T+ %p\n' | sort | head -n 1 | cut -d ' ' -f2-)
        echo "Oldest file is ${OLDEST_FILE}, removing..."
        rm "${OLDEST_FILE}"
        unset OLDEST_FILE
    else
        echo "No local backup files to prune ..."
    fi

unset NUM_BACKUPS


echo -e "\n\n FINISH BACKUP SESSION $(date +%Y%m%d_%H%M%S)\n\n"
echo "----------------------------------------------------"
