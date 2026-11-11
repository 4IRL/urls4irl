# scripts/

Operational shell scripts for server administration and the daily workflow container.

## Automatic (run by the workflow Docker container)

| Script | Trigger | Purpose |
|---|---|---|
| `daily-docker.sh` | Daily cron (midnight) | Orchestrator: runs DB backup, log backup, and remote upload in sequence. Cleans up sensitive env vars on exit. On every exit path after `container_environment` is sourced, its `EXIT` trap sends one `daily_backup` heartbeat (`/fail` unless the DB backup, log backup and remote upload all succeeded); a manual trigger logs a skip and pings nothing. |
| `flush_metrics.py`, `sample_gauges.py`, `purge_audit_log.py`, `purge_trash.py`, `purge_short_links.py`, `purge_invite_links.py` | Cron (every minute / hourly / nightly) | On finish each sends one heartbeat (`metrics_flush`, `gauge_sample`, `purge_*`) via `notifs_hub.safe_ping`, or `/fail` on error, without changing its exit code. `metrics_flush` (1m period, 5m grace) can show a pings gap while `workflow` is recreated on a deploy. |
| `backup-database.sh` | Called by `daily-docker.sh` | `pg_dump` the PostgreSQL database, compress it, and rotate local copies to keep the most recent 90 days. |
| `backup-logs.sh` | Called by `daily-docker.sh` | Compress yesterday's app log file and rotate local copies to keep the most recent 90 days. |
| `remote-object-storage.sh` | Called by `daily-docker.sh` | Upload compressed DB and log backups to Cloudflare R2 via rclone. Skips upload in non-production environments. Also sends a monthly copy on the 1st of each month. |
| `restricted-curl.sh` | Replaces `/usr/bin/curl` inside the workflow container | Wrapper that only permits `POST` to Discord webhook URLs, blocking all other requests. |
| `notifs_hub.py` | Imported by the scheduled jobs; CLI `notifs_hub.py ping <check> [--fail]` | Stdlib client that sends dead-man's-switch heartbeats to the notification hub. Does nothing unless `PRODUCTION == "true"`. Reads the delivery key and Access credentials fresh from `NOTIFS_KEY_DIR` (mounted read-only at `/run/notifs`) on every call, never logs them, and never raises: a failed ping returns `False` and the job's exit code is unaffected. |

## Manual (run by an operator on the host)

| Script | Prerequisites | Purpose |
|---|---|---|
| `db_backup_loader.sh` | Requires a `secrets/db_credentials.conf` file (see script header). Docker must be running with the target Postgres container. | Restores a gzip'd `pg_dump` backup into a running Docker Postgres container. Drops the public schema first if the DB is non-empty. Usage: `./db_backup_loader.sh <backup_file.sql.gz>` |
