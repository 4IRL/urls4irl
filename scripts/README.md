# scripts/

Operational shell scripts for server administration and the daily workflow container.

## Automatic (run by the workflow Docker container)

| Script | Trigger | Purpose |
|---|---|---|
| `daily-docker.sh` | Daily cron (midnight) | Orchestrator: runs DB backup, log backup, and remote upload in sequence. Cleans up sensitive env vars on exit. |
| `backup-database.sh` | Called by `daily-docker.sh` | `pg_dump` the PostgreSQL database, compress it, and rotate local copies to keep the most recent 90 days. |
| `backup-logs.sh` | Called by `daily-docker.sh` | Compress yesterday's app log file and rotate local copies to keep the most recent 90 days. |
| `remote-object-storage.sh` | Called by `daily-docker.sh` | Upload compressed DB and log backups to Cloudflare R2 via rclone. Skips upload in non-production environments. Also sends a monthly copy on the 1st of each month. |
| `restricted-curl.sh` | Replaces `/usr/bin/curl` inside the workflow container | Wrapper that only permits `POST` to Discord webhook URLs, blocking all other requests. |

## Manual (run by an operator on the host)

| Script | Prerequisites | Purpose |
|---|---|---|
| `db_backup_loader.sh` | Requires a `secrets/db_credentials.conf` file (see script header). Docker must be running with the target Postgres container. | Restores a gzip'd `pg_dump` backup into a running Docker Postgres container. Drops the public schema first if the DB is non-empty. Usage: `./db_backup_loader.sh <backup_file.sql.gz>` |
