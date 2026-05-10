# URLS4IRL Daily Workflow Cron Jobs
#
# IMPORTANT — env-var inheritance for cron jobs:
# Cron runs each line in a fresh /bin/sh with NO container env vars present.
# To give a job access to REDIS_URI, POSTGRES_*, etc., the job must source
# /app/container_environment (a `printenv` dump written by startup-workflow.sh).
# However: the `.` / `source` builtin only SETS shell variables — it does NOT
# mark them as exported, so child processes (python, psql, …) inherit nothing.
# Wrap the source with `set -a` / `set +a` to auto-export every assignment:
#
#   * * * * * set -a && . /app/container_environment && set +a && /path/to/cmd
#
# Self-contained scripts (like daily-docker.sh) that do their own env-loading
# don't need this — see the daily backup line below.
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
MAILTO=""

# Daily backup workflow at 1 AM (daily-docker.sh handles its own env-loading)
0 1 * * * /app/daily-docker.sh >> /app/workflow_logs/cron.log 2>&1

# Anonymous metrics flush — every minute (uses the set -a env pattern above)
* * * * * set -a && . /app/container_environment && set +a && /opt/metrics-venv/bin/python /app/flush_metrics.py >> /app/workflow_logs/metrics-flush.log 2>&1
