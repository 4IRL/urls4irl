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
REQUIRED_COMMANDS=("useradd" "passwd" "curl")
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

# Final message
echo "User '$USERNAME' created successfully with no shell."
rm $PASSWORD_FILE

