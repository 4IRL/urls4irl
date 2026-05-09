# URLS4IRL Daily Workflow Cron Jobs
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
MAILTO=""

# Daily backup workflow at 1 AM
0 1 * * * /app/daily-docker.sh >> /app/workflow_logs/cron.log 2>&1

# Anonymous metrics flush — every minute
* * * * * . /app/container_environment && /opt/metrics-venv/bin/python /app/flush_metrics.py >> /app/workflow_logs/metrics-flush.log 2>&1
