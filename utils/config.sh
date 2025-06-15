#!/bin/bash
set +x # Disable command echoing

echo "----------------------------------------------------"
echo -e "\n\n START CONFIG SESSION  $(date +%Y%m%d_%H%M%S)\n\n"

# ------- GET SECRETS ------- #
export USERNAME=$(< ./secrets/username)

# Get infisical login parameters
INF_ID=$(< ./secrets/inf_id)
INF_SECRET=$(< ./secrets/inf_secret)
INFISICAL_URL="https://us.infisical.com/api/v3/secrets/raw/"
ENVIRONMENT_WORKSPACE="?environment=prod&workspaceSlug=u4-i-fv-ya"

# Make cURL request to get the access token
echo "Fetching access token..."
response=$(restricted_curl POST "https://app.infisical.com/api/v1/auth/universal-auth/login" "$INF_ID" "$INF_SECRET")

unset INF_ID INF_SECRET

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

unset ACCESS_TOKEN

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
export DB_PASS

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
export DB_USER

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
export DB_NAME

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
export ACCESS_KEY

# Parse for R2 Secret Access Key
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
export SECRET_ACCESS_KEY

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
export R2_ENDPOINT

# Parse for R2 Endpoint
echo "Parsing Notification URL..."
NOTIFICATION_URL=$(echo $response | jq -r --arg key "NOTIFICATION_URL" '.secrets[] | select(.secretKey == $key) | .secretValue')
if [ "$?" -ne 0 ]; then
  echo "Error: Failure in parsing for Notification URL"
  exit 1
fi
if [[ ! $NOTIFICATION_URL ]]; then
  echo "Error: Empty Notification URL"
  exit 1
fi
echo "Success: Parsed Notification URL"
export NOTIFICATION_URL

unset response

# Set environment variables for backups
export BACKUP_DIR="/home/$USERNAME/backups/"
export BACKUP_FILE="${DB_NAME}_$(date +%Y%m%d_%H%M%S).sql"
export COMPRESSED_BACKUP_FILE="${BACKUP_FILE}"
export LOG_DIR="/home/$USERNAME/app_logs/"
export TMP_LOG_DIR="/home/$USERNAME/tmp_app_logs/"
export LOG_FILE="log_$(date +%Y%m%d_%H%M%S).txt"
export COMPRESSED_LOG_FILE="${LOG_FILE}"

echo -e "\n\n FINISH CONFIG SESSION $(date +%Y%m%d_%H%M%S)\n\n"
echo "----------------------------------------------------"
