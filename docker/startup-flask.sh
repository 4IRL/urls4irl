
#!/bin/bash
set +x # Disable command echoing

echo "!!######################################################################################################!!"
echo -e "\nSTARTING FLASK CONTAINER: $(date +%Y%m%d_%H%M%S)\n"
echo "!!######################################################################################################!!"

# Allow time for database containers to build
sleep 5

# Function to load secrets from Docker secrets
load_secrets() {
    # Load secrets from files and export them
    for secret_file in /run/secrets/*; do
        if [ -f "$secret_file" ]; then
            secret_name=$(basename "$secret_file")
            secret_value=$(cat "$secret_file")
            export "$secret_name"="$secret_value"
        fi
    done
}

if [[ "$PRODUCTION" == "true" || "$DEV_SERVER" == "true" ]]; then
    echo -e "\nLoading production environment...\n"
    export ASSET_VERSION=$(date +%s)
    load_secrets
fi

. /code/venv/bin/activate
flask db upgrade
flask shorturls add

if [[ "$PRODUCTION" != "true" && "$DEV_SERVER" != "true" ]]; then
    echo 'Running on 127.0.0.1:8659!'
    flask utils start-log
    exec flask run --host=0.0.0.0 --port=5000 --cert=adhoc
else
    flask assets build
    flask utils start-log
    exec gunicorn --workers 4 --bind 0.0.0.0:5000 --access-logfile - --error-logfile - run:app
fi

