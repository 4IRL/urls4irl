#!/bin/bash
set +x # Disable command echoing


echo "!!######################################################################################################!!"
echo "\nSTARTING DAILY WORKFLOW CONTAINER: $(date +%Y%m%d_%H%M%S)\n"
echo "!!######################################################################################################!!"

# Function to load secrets from Docker secrets
load_secrets() {
    echo "Loading secrets..."
    
    # Load secrets from files and export them
    for secret_file in /run/secrets/*; do
        if [ -f "$secret_file" ]; then
            secret_name=$(basename "$secret_file")
            secret_value=$(cat "$secret_file")
            export "$secret_name"="$secret_value"
            echo "Loaded secret: $secret_name"
        fi
    done
}

if [ "$PRODUCTION" == "true" ]; then
    echo "\nLoading environments...\n"
    load_secrets
fi

# Dump current env to a file readable by cron jobs
printenv | grep -v "no_proxy" > /etc/container_environment

exec cron -f
