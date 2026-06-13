# URLS4IRL Daily Workflow Cron Jobs
#
# IMPORTANT — env-var inheritance for cron jobs:
# Cron runs each line in a fresh /bin/sh with NO container env vars present.
# To give a job access to REDIS_URI, POSTGRES_*, etc., the job must source
# /app/container_environment (a `KEY=value` dump written by startup-workflow.sh).
# However: the `.` / `source` builtin only SETS shell variables — it does NOT
# mark them as exported, so child processes (python, psql, …) inherit nothing.
# Wrap the source with `set -a` / `set +a` to auto-export every assignment:
#
#   * * * * * set -a && . /app/container_environment && set +a && /path/to/cmd
#
# Self-contained scripts (like daily-docker.sh) that do their own env-loading
# don't need this — see the daily backup line below.
#
# Guaranteed env vars (sourced from /app/container_environment):
#   ACCESS_KEY
#   DEV_SERVER
#   METRICS_FLUSH_LIVENESS_THRESHOLD_SECONDS
#   METRICS_REDIS_URI
#   NOTIFICATION_URL
#   POSTGRES_DB
#   POSTGRES_HOST
#   POSTGRES_PASSWORD
#   POSTGRES_PORT
#   POSTGRES_USER
#   PRODUCTION
#   R2_ENDPOINT
#   SECRET_ACCESS_KEY
# Deliberately excluded are container metadata (HOSTNAME, HOME, PATH, LANG, LC_*,
# TERM, SHLVL, PWD), the raw REDIS_PASSWORD (replaced by the pre-assembled
# METRICS_REDIS_URI), and workflow-service env vars that the cron scripts do not
# read at runtime (e.g. METRICS_BUCKET_SECONDS — consumed only by the web container).
# Canonical allow-list lives in docker/startup-workflow.sh:ALLOW_VARS; drift is enforced by tests/unit/test_workflow_env_allowlist.py.
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
MAILTO=""

# Daily backup workflow at 1 AM (daily-docker.sh handles its own env-loading)
0 1 * * * /app/daily-docker.sh >> /app/workflow_logs/cron.log 2>&1

# Anonymous metrics flush — every minute (uses the set -a env pattern above)
* * * * * set -a && . /app/container_environment && set +a && /opt/metrics-venv/bin/python /app/flush_metrics.py >> /app/workflow_logs/metrics-flush.log 2>&1
