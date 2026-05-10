
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

# Each critical bootstrap step must abort the container on failure so deploy
# verification (docker compose ps) reports the real outage instead of a stale
# pre-failure web container. Without explicit `|| exit 1`, bash continues past
# the failed step and a later command (e.g. `flask metrics sync-registry`)
# crashes against an unmigrated schema, masking the true root cause.
flask db upgrade || { echo "FATAL: flask db upgrade failed" >&2; exit 1; }
flask utils verify-tables || { echo "FATAL: flask utils verify-tables failed" >&2; exit 1; }
flask shorturls add || { echo "FATAL: flask shorturls add failed" >&2; exit 1; }
# Reconciles the EventRegistry table with the EventName Python enum on every
# boot (inserts missing rows, updates drifted category/description, never
# deletes — historical AnonymousMetrics rows FK to retired enum values).
# Idempotent. Startup aborts only on hard failure (DB unreachable, ORM/schema
# mismatch). Adding new EventName members is a code-only change; only schema-
# shape changes (new columns, FK changes) require an Alembic migration.
flask metrics sync-registry || { echo "FATAL: flask metrics sync-registry failed" >&2; exit 1; }

if [[ "$PRODUCTION" != "true" && "$DEV_SERVER" != "true" ]]; then
    echo 'Running on 127.0.0.1:8659!'
    flask utils start-log
    if [[ "$ENABLE_SSL" == "true" ]]; then
        exec flask run --host=0.0.0.0 --port=5000 --cert=adhoc
    else
        exec flask run --host=0.0.0.0 --port=5000
    fi
else
    flask utils start-log
    exec gunicorn --workers 4 --bind 0.0.0.0:5000 --access-logfile - --error-logfile - run:app
fi

