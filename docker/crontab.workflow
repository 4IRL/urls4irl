# URLS4IRL Daily Workflow Cron Jobs
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
MAILTO=""

# Daily backup workflow at 1 AM
0 1 * * * . /app/container_environment; /app/daily-docker.sh >> /app/workflow_logs/cron.log 2>&1
