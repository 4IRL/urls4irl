#!/bin/bash

# STEPS
# 1) Create a secrets folder within same directory as this file
# 2) Create db_credentials.conf within the secrets folder
# 3) Add the following to the db_credentials.conf, replacing the values with your relevant data
#
# DB_NAME=database_name_here
# DB_USER=database_user_here
# DB_PASSWORD=database_password_here
# CONTAINER_NAME=docker_container_running_postgres
#
# 4) Ensure the gzip'd backup file is in this directory, and pass it as an argument when running this file
# 5) Should lead you to a successful restore of backup :)

# Load credentials from a configuration file
CREDENTIALS_FILE="secrets/db_credentials.conf"

if [ ! -f "$CREDENTIALS_FILE" ]; then
    echo "Error: Credentials file '$CREDENTIALS_FILE' not found!"
    exit 1
fi

# Read credentials
source "$CREDENTIALS_FILE"

# Ensure all required variables are set
if [[ -z "$CONTAINER_NAME" || -z "$DB_NAME" || -z "$DB_USER" || -z "$DB_PASSWORD" ]]; then
    echo "Error: Missing required database credentials in '$CREDENTIALS_FILE'"
    exit 1
fi

# Check if a filename was provided as an argument
if [ $# -eq 0 ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    exit 1
fi

BACKUP_FILE="$1"
TMP_FILE="tmp.db"

# Check if the backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file '$BACKUP_FILE' not found!"
    exit 1
fi

echo "Unzipping backup file..."
gunzip -c "$BACKUP_FILE" > "$TMP_FILE"

echo "Modifying owner references in backup file..."
sed -i "s/Owner: [^ ]*/Owner: $DB_USER/g" "$TMP_FILE"
sed -i "s/OWNER TO [^ ]*/OWNER TO $DB_USER;/g" "$TMP_FILE"

# Export the password to avoid interactive prompts
export PGPASSWORD="$DB_PASSWORD"

# Ensure the database is empty
echo "Checking if database '$DB_NAME' is empty..."
TABLE_COUNT=$(docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT count(*) FROM pg_tables WHERE schemaname='public';" | tr -d '[:space:]')

if [[ "$TABLE_COUNT" -ne 0 ]]; then
    echo "Warning: Database '$DB_NAME' is not empty. Dropping all tables..."
    docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
fi

echo "Copying modified backup file into Docker container..."
# Copy the backup file into the container
docker cp "$TMP_FILE" "$CONTAINER_NAME:/tmp/$TMP_FILE"

# Restore the database inside the container
echo "Restoring database from backup file: $BACKUP_FILE..."
docker exec -i "$CONTAINER_NAME" psql -U $DB_USER -d $DB_NAME -f "/tmp/$TMP_FILE"

# Clean up the backup file inside the container
echo "Cleaning up..."
docker exec -i "$CONTAINER_NAME" rm /tmp/$TMP_FILE
rm -f "$TMP_FILE"

unset CONTAINER_NAME
unset DB_NAME
unset DB_USER
unset DB_PASSWORD
unset PGPASSWORD

echo "Restore completed successfully!"
