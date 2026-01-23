#!/bin/bash
set +x # Disable command echoing


echo "!!######################################################################################################!!"
echo -e "\nSTARTING DAILY WORKFLOW CONTAINER: $(date +%Y%m%d_%H%M%S)\n"
echo "!!######################################################################################################!!"

# Fix permissions for mounted volumes (running as root)
echo "Setting up volume permissions..."
chown -R workflow:workflow /app/volume /app/workflow_logs /backups 2>/dev/null || true
chmod -R 755 /backups /app/volume /app/workflow_logs 2>/dev/null || true

# Function to load secrets from Docker secrets
load_secrets() {
    echo -e "Loading secrets..."
    
    # Load secrets from files and export them
    for secret_file in /run/secrets/*; do
        if [ -f "$secret_file" ]; then
            secret_name=$(basename "$secret_file")
            secret_value=$(cat "$secret_file")
            export "$secret_name"="$secret_value"
            echo -e "Loaded secret: $secret_name"
        fi
    done
}

if [ "$PRODUCTION" == "true" ]; then
    echo -e "\nLoading environments...\n"
    load_secrets
else
    echo -e "\nRunning workflow in development mode\n"
fi

# Dump current env to a file readable by cron jobs
echo "Saving environment for cron jobs..."
printenv | grep -v "no_proxy" > /app/container_environment

# Ensure proper permissions
chmod 644 /app/container_environment
chown workflow:workflow /app/container_environment

# Install crontab NOW (after environment file exists)
echo "Installing crontab for workflow user..."
crontab -u workflow /tmp/crontab.workflow

echo -e "\nStarting cron daemon...\n"
exec cron -f
