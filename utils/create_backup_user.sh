#!/bin/bash

# Ensure the script is run as root
if [[ $EUID -ne 0 ]]; then
  echo "This script must be run as root or with sudo privileges."
  exit 1
fi

# Function to check if a command exists
command_exists() {
  command -v "$1" &>/dev/null
}

# Check for required commands
REQUIRED_COMMANDS=("useradd" "passwd" "curl" "jq" "rclone" "gzip")
for cmd in "${REQUIRED_COMMANDS[@]}"; do
  if ! command_exists "$cmd"; then
    echo "Error: Required command '$cmd' is not available. Please install it and try again."
    exit 1
  fi
done

# Detect OS
OS=$(lsb_release -is 2>/dev/null || grep '^ID=' /etc/os-release | cut -d'=' -f2 | tr -d '"')
OS="${OS,,}"
if [[ "$OS" != "debian" && "$OS" != "ubuntu" ]]; then
  echo "Error: Unsupported OS. This script supports only Debian or Ubuntu."
  exit 1
fi

# Input validation
if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <username> <password_file>"
  exit 1
fi

USERNAME="$1"
PASSWORD_FILE="$2"

if [ ! -f $PASSWORD_FILE ]; then
  echo "File containing user password not found."
  exit 1
fi

USER_PASSWORD=$(< $PASSWORD_FILE)

# Check if the password is provided via the USER_PASSWORD environment variable
if [[ -z "$USER_PASSWORD" ]]; then
  echo "Error: Password not provided. Set the USER_PASSWORD environment variable."
  exit 1
fi

# Check if user already exists
if id "$USERNAME" &>/dev/null; then
  echo "Error: User '$USERNAME' already exists."
  rm $PASSWORD_FILE
  exit 1
fi

# Create the user with no shell
echo "Creating user '$USERNAME' with no shell..."
if ! useradd -m -s /usr/sbin/nologin "$USERNAME"; then
  echo "Error: Failed to create user '$USERNAME'."
  exit 1
fi

# Set the user's password
echo "Setting password for user '$USERNAME'..."
if ! echo "$USERNAME:$USER_PASSWORD" | chpasswd; then
  echo "Error: Failed to set password for user '$USERNAME'."
  # Rollback user creation
  userdel -r "$USERNAME" &>/dev/null
  exit 1
fi

echo "Disabling passwords for user"
if ! passwd -l "$USERNAME"; then
  echo "Error: Failed to disable passwords for '$USERNAME'."
  exit 1
fi

# Create bin directory in user's folder for only allowed commands
echo "Creating the user's bin directory"
USER_BIN="/home/$USERNAME/bin"
mkdir -p $USER_BIN
echo "Success: Made user's bin directory"

# Create symlinks
ln -s /usr/bin/docker "$USER_BIN/docker"
ln -s /usr/bin/gzip "$USER_BIN/gzip"
ln -s /usr/bin/jq "$USER_BIN/jq"
ln -s /usr/bin/echo "$USER_BIN/echo"
ln -s /usr/bin/cat "$USER_BIN/cat"
ln -s /usr/bin/date "$USER_BIN/date"
ln -s /usr/bin/rm "$USER_BIN/rm"
ln -s /usr/bin/find "$USER_BIN/find"
ln -s /usr/bin/sort "$USER_BIN/sort"
ln -s /usr/bin/head "$USER_BIN/head"
ln -s /usr/bin/wc "$USER_BIN/wc"
ln -s /usr/bin/cut "$USER_BIN/cut"
ln -s /usr/bin/cp "$USER_BIN/cp"
ln -s /usr/bin/dirname "$USER_BIN/dirname"
ln -s /usr/bin/realpath "$USER_BIN/realpath"
ln -s /usr/bin/rclone "$USER_BIN/rclone"

# Need a specific cURL wrapper script to allow curl to only specified endpoints
CURL_WRAPPER_SCRIPT="$USER_BIN/restricted_curl"
if [ -f $CURL_WRAPPER_SCRIPT ]; then
  rm -f $CURL_WRAPPER_SCRIPT
fi


cat << 'EOF' > "$CURL_WRAPPER_SCRIPT"
#!/bin/bash
set -e

# Fixed URLs
ALLOWED_URL_1="https://app.infisical.com/api/v1/auth/universal-auth/login"
ALLOWED_URL_2="https://us.infisical.com/api/v3/secrets/raw?environment=prod&workspaceSlug=u4-i-fv-ya&tagSlugs=prod-pull"

# Check the URL and method
if [[ "$1" == "POST" && "$2" == "$ALLOWED_URL_1" ]]; then
    /usr/bin/curl -s --location --request POST "$ALLOWED_URL_1" \
      --header 'Content-Type: application/x-www-form-urlencoded'\
      --data-urlencode "clientId=$3" \
      --data-urlencode "clientSecret=$4"
elif [[ "$1" == "GET" && "$2" == "$ALLOWED_URL_2" ]]; then
    /usr/bin/curl -s --request GET "${ALLOWED_URL_2}" \
      --header "Authorization: Bearer $3"
else
    echo "Error: Unauthorized URL or method"
    exit 1
fi
EOF

chmod +x $CURL_WRAPPER_SCRIPT

# Set the specific commands the user can perform
SUDOERS_FILE="/etc/sudoers.d/allowed-commands"
if [ -f $SUDOERS_FILE ]; then
  rm -f $SUDOERS_FILE
fi

echo "Creating sudoers file with specified commands..."
# Add multiple commands with varying levels of specificity
{
  echo "Defaults secure_path=$USER_BIN"

  # Prevent other commands
  echo "$USERNAME ALL=(ALL) !ALL"
  # Allow only `docker exec -t u4i-prod-postgres` without any arguments
  echo "$USERNAME ALL=(ALL) NOPASSWD: $USER_BIN/docker exec -i u4i-prod-postgres pg_dump -U *"

  # Allow gzip
  echo "$USERNAME ALL=(ALL) NOPASSWD: $USER_BIN/gzip -c *"

  # Allow jq
  echo "$USERNAME ALL=(ALL) NOPASSWD: $USER_BIN/jq -r *"

  # Allow curl POST to infisical token generator
  echo "$USERNAME ALL=(ALL) NOPASSWD: $USER_BIN/restricted_curl"

  # Allow the user to perform echo, cat, date, rm
  echo "$USERNAME ALL=(ALL) NOPASSWD: $USER_BIN/echo"
  echo "$USERNAME ALL=(ALL) NOPASSWD: $USER_BIN/cat"
  echo "$USERNAME ALL=(ALL) NOPASSWD: $USER_BIN/date"
  echo "$USERNAME ALL=(ALL) NOPASSWD: $USER_BIN/rm /home/$USERNAME/backups/*"
  echo "$USERNAME ALL=(ALL) NOPASSWD: $USER_BIN/cp /home/$USERNAME/backups/* /home/$USERNAME/backups/*"
  echo "$USERNAME ALL=(ALL) NOPASSWD: $USER_BIN/find /home/$USERNAME/backups -maxdepth 1 -type f *"
  echo "$USERNAME ALL=(ALL) NOPASSWD: $USER_BIN/sort"
  echo "$USERNAME ALL=(ALL) NOPASSWD: $USER_BIN/head -n 1"
  echo "$USERNAME ALL=(ALL) NOPASSWD: $USER_BIN/wc -1"
  echo "$USERNAME ALL=(ALL) NOPASSWD: $USER_BIN/cut -d ' ' -f2-"
  echo "$USERNAME ALL=(ALL) NOPASSWD: $USER_BIN/dirname"
  echo "$USERNAME ALL=(ALL) NOPASSWD: $USER_BIN/realpath"
  echo "$USERNAME ALL=(ALL) NOPASSWD: $USER_BIN/rclone"

} >> "$SUDOERS_FILE"
echo "Success: Sudoers file created with specified commands"

# Validate the sudoers command
visudo -cf "$SUDOERS_FILE" && echo "Sudoers file updated successfully!" || echo "Error in sudoers file!"

# Create cronjob to run the backups for this user
#TODO: Change the commands here to match the backup script
BACKUP_LOGS_DIR="/home/$USERNAME/backup_logs/"
mkdir -p "$BACKUP_LOGS_DIR"
chown $USERNAME $BACKUP_LOGS_DIR
chgrp $USERNAME $BACKUP_LOGS_DIR
chmod 700 $BACKUP_LOGS_DIR

#TODO:The cron file needs to be edited manually to allow for specific date naming, as this line causes the date function to expand
CRON_JOB="0 0 * * * /home/$USERNAME/backup-database.sh > $BACKUP_LOGS_DIR$(/$USER_BIN/date +\%Y_\%m_\%d)-backup-logs.txt 2>&1"

# Retrieve the user's current crontab
CURRENT_CRON=$(mktemp)
crontab -u "$USERNAME" -l 2>/dev/null > "$CURRENT_CRON" || echo "" > "$CURRENT_CRON"

# Check if the cron job already exists
if ! grep -Fxq "$CRON_JOB" "$CURRENT_CRON"; then
    echo "PATH=$USER_BIN" >> "$CURRENT_CRON"
    echo "$CRON_JOB" >> "$CURRENT_CRON"
    crontab -u "$USERNAME" "$CURRENT_CRON"
    echo "Cron job added for user $USERNAME."
else
    echo "Cron job already exists for user $USERNAME."
fi

# Clean up cron job
rm "$CURRENT_CRON"

# Make secrets folder
SECRETS_FOLDER="/home/$USERNAME/secrets"
mkdir -p "$SECRETS_FOLDER"
chown $USERNAME $SECRETS_FOLDER
chgrp $USERNAME $SECRETS_FOLDER
chmod 700 $SECRETS_FOLDER

# Make username file
echo "$USERNAME" > "$SECRETS_FOLDER/username"

# Make backup folder
BACKUP_FOLDER="/home/$USERNAME/backups"
mkdir -p "$BACKUP_FOLDER"
chown $USERNAME $BACKUP_FOLDER
chgrp $USERNAME $BACKUP_FOLDER
chmod 700 $BACKUP_FOLDER

# Final message
usermod -aG docker $USERNAME
echo "User '$USERNAME' created successfully with no shell."
rm $PASSWORD_FILE

