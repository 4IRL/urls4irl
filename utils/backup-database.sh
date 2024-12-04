#!/bin/bash

# ------- GET SECRETS ------- #

# Get infisical login parameters
ID=$(< ./secrets/inf_id)
SECRET=$(< ./secrets/inf_secret)
INFISICAL_URL="https://us.infisical.com/api/v3/secrets/raw/"
ENVIRONMENT_WORKSPACE="?environment=prod&workspaceSlug=u4-i-fv-ya"

# Make cURL request to get the access token
echo "Fetching access token..."
response=$(curl -s --location --request POST 'https://app.infisical.com/api/v1/auth/universal-auth/login' \
  --header 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode "clientId=$ID" \
  --data-urlencode "clientSecret=$SECRET")

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

# Get DB Password
echo "Fetching DB Password..."
response=$(curl -s --request GET \
  --url "${INFISICAL_URL}PROD_DB_PASSWORD${ENVIRONMENT_WORKSPACE}" \
  --header "Authorization: Bearer $ACCESS_TOKEN")

if [ "$?" -ne 0 ]; then
  echo "Error: Failure in fetching DB Password"
  exit 1
fi
echo "Success: Fetched DB Password"

# Parse for DB PASSWORD
echo "Parsing DB Password..."
DB_PASS=$(echo $response | jq -r '.secret.secretValue')
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in parsing for DB Pass"
  exit 1
fi
if [[ ! $DB_PASS ]]; then
  echo "Error: Empty DB Pass"
  exit 1
fi
echo "Success: Parsed DB Pass"

# Get DB User
echo "Fetching DB User..."
response=$(curl -s --request GET \
  --url "${INFISICAL_URL}PROD_DB_USER${ENVIRONMENT_WORKSPACE}" \
  --header "Authorization: Bearer $ACCESS_TOKEN")

if [ "$?" -ne 0 ]; then
  echo "Error: Failure in fetching DB User"
  exit 1
fi
echo "Success: Fetched DB User"

# Parse for DB USER
echo "Parsing DB User..."
DB_USER=$(echo $response | jq -r '.secret.secretValue')
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in parsing for DB User"
  exit 1
fi
if [[ ! $DB_USER ]]; then
  echo "Error: Empty DB User"
  exit 1
fi
echo "Success: Parsed DB User"

# Get DB Name
echo "Fetching DB Name..."
response=$(curl -s --request GET \
  --url "${INFISICAL_URL}PROD_DB_NAME${ENVIRONMENT_WORKSPACE}" \
  --header "Authorization: Bearer $ACCESS_TOKEN")

if [ "$?" -ne 0 ]; then
  echo "Error: Failure in fetching DB Name"
  exit 1
fi
echo "Success: Fetched DB Name"

# Parse for DB USER
echo "Parsing DB Name..."
DB_NAME=$(echo $response | jq -r '.secret.secretValue')
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in parsing for DB Name"
  exit 1
fi
if [[ ! $DB_NAME ]]; then
  echo "Error: Empty DB Name"
  exit 1
fi
echo "Success: Parsed DB Name"

# Get R2 Access Key
echo "Fetching Access Key..."
response=$(curl -s --request GET \
  --url "${INFISICAL_URL}CF_ACCESS_KEY_ID${ENVIRONMENT_WORKSPACE}" \
  --header "Authorization: Bearer $ACCESS_TOKEN")

if [ "$?" -ne 0 ]; then
  echo "Error: Failure in fetching Access Key"
  exit 1
fi
echo "Success: Fetched Access Key"

# Parse for R2 Access Key
echo "Parsing Access Key..."
ACCESS_KEY=$(echo $response | jq -r '.secret.secretValue')
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in parsing for Access Key"
  exit 1
fi
if [[ ! $ACCESS_KEY ]]; then
  echo "Error: Empty Access Key"
  exit 1
fi
echo "Success: Parsed Access Key"

# Get R2 Secret Access Key
echo "Fetching Secret Access Key..."
response=$(curl -s --request GET \
  --url "${INFISICAL_URL}CF_SECRET_ACCESS_KEY${ENVIRONMENT_WORKSPACE}" \
  --header "Authorization: Bearer $ACCESS_TOKEN")

if [ "$?" -ne 0 ]; then
  echo "Error: Failure in fetching Secret Access Key"
  exit 1
fi
echo "Success: Fetched Secret Access Key"

# Parse for R2 Access Key
echo "Parsing Secret Access Key..."
SECRET_ACCESS_KEY=$(echo $response | jq -r '.secret.secretValue')
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in parsing for Secret Access Key"
  exit 1
fi
if [[ ! $SECRET_ACCESS_KEY ]]; then
  echo "Error: Empty Secret Access Key"
  exit 1
fi
echo "Success: Parsed Secret Access Key"

# Get R2 Endpoint 
echo "Fetching R2 Endpoint..."
response=$(curl -s --request GET \
  --url "${INFISICAL_URL}S3_ENDPOINT${ENVIRONMENT_WORKSPACE}" \
  --header "Authorization: Bearer $ACCESS_TOKEN")

if [ "$?" -ne 0 ]; then
  echo "Error: Failure in fetching R2 Endpoint"
  exit 1
fi
echo "Success: Fetched R2 Endpoint"

# Parse for R2 Endpoint
echo "Parsing R2 Endpoint..."
R2_ENDPOINT=$(echo $response | jq -r '.secret.secretValue')
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

BACKUP_DIR="./backups/"

BACKUP_FILE="${DB_NAME}_$(date +%Y%m%d_%H%M%S).sql"
COMPRESSED_BACKUP_FILE="${BACKUP_FILE}.gz"

# Create backup and store on host
echo "Generating backup and storing on the host..."
export PGPASSWORD="$DB_PASS"
docker exec -i u4i-prod-postgres pg_dump -U "$DB_USER" "$DB_NAME" > "${BACKUP_DIR}${BACKUP_FILE}"
if [ "$?" -ne 0 ]; then
  unset PGPASSWORD
  echo "Error: Failure in generating backup in docker container"
  exit 1
fi
unset PGPASSWORD
echo "Success: Generated backup and stored on host"

# Compress backup on host
echo "Compressing backup on host..."
gzip -c "${BACKUP_DIR}${BACKUP_FILE}" > "${BACKUP_DIR}${COMPRESSED_BACKUP_FILE}"
if [ "$?" -ne 0 ]; then
  unset PGPASSWORD
  echo "Error: Failure in compressing the backup"
  exit 1
fi
echo "Success: Compressed backup on host"

# Remove original uncompressed file
rm "${BACKUP_DIR}${BACKUP_FILE}"

# ------- SEND DATABASE BACKUP TO R2 ------- #

# Create rclone config file
CONFIG_FILE="./secrets/rclone-config.txt"
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
rclone --config="$CONFIG_FILE" copy "${BACKUP_DIR}${COMPRESSED_BACKUP_FILE}" "remote:u4i-backups/" --progress --s3-no-check-bucket
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in sending daily backup to Cloudflare R2"
fi
echo "Success: Sent daily backup to Cloudflare R2"


# ------- IF FIRST OF MONTH, SEND A FIRST-OF-MONTH BACKUP  ------- #
#
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

# ------- ROTATE REMOTE DB's - ONLY STORE PAST 90 DAYS AND FIRST OF EVERY MONTH  ------- #
