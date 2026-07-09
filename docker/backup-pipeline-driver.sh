#!/usr/bin/env bash
#
# In-container test driver for the backup pipeline, run INSIDE the workflow
# image (as uid 1001 / workflow) by docker/backup-pipeline-test.sh. It exercises
# the real backup bash scripts against a Postgres sidecar that has already been
# provisioned with the real u4i schema (flask db upgrade + flask addmock all).
#
# `set -u` catches our own typos; we deliberately do NOT `set -e` globally —
# the sourced backup scripts carry `set -euo pipefail`, so each is sourced in a
# guarded subshell whose exit status we capture and assert on explicitly.
set -u

# Populated by the workflow container's startup (build_container_env.py): gives
# us POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_HOST, exactly as
# daily-docker.sh consumes them.
. /app/container_environment

PY=/opt/metrics-venv/bin/python
MAINT=/app/backup_maintenance.py

fail() {
  echo "❌ $1"
  exit 1
}
ok() { echo "✅ $1"; }

# Emit "table_name|row_count" for every base table in the public schema of the
# given database. query_to_xml runs a dynamic count per table in one round-trip;
# the result drives a drift-proof original-vs-restored comparison with no
# hardcoded table names or counts.
table_counts() {
  local dbname=$1
  PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$dbname" -At -F'|' -c "
SELECT t.table_name,
       (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM %I.%I', t.table_schema, t.table_name), false, true, '')))[1]::text::bigint
FROM information_schema.tables t
WHERE t.table_schema = 'public' AND t.table_type = 'BASE TABLE'
ORDER BY t.table_name;"
}

# ----------------------------------------------------------------------
# Leg 1 — real-schema DB backup + restore round-trip (crown jewel)
# ----------------------------------------------------------------------
leg_db_backup_and_restore() {
  echo "── Leg 1: DB backup + restore round-trip ──"
  # Mirror exactly the env daily-docker.sh exports before sourcing backup-database.sh.
  export DB_BACKUP_DIR="/backups/"
  DB_BACKUP_FILE="${DB_BACKUP_DIR}${POSTGRES_DB}_$(date +%Y%m%d_%H%M%S)_daily.sql"
  export DB_BACKUP_FILE
  export COMPRESSED_DB_BACKUP_FILE="${DB_BACKUP_FILE}.gz"
  export DB_USER="$POSTGRES_USER" DB_PASS="$POSTGRES_PASSWORD" DB_NAME="$POSTGRES_DB"

  # Capture the source-of-truth counts BEFORE the restore (the restore recreates
  # the DB via the dump's own --create/--clean, so we read the original first).
  local original_counts
  original_counts=$(table_counts "$POSTGRES_DB") || fail "Leg 1: could not read original table counts"

  local backup_rc
  (source /app/backup-database.sh)
  backup_rc=$?
  [ "$backup_rc" -eq 0 ] || fail "Leg 1: backup-database.sh exited $backup_rc"
  [ -f "$COMPRESSED_DB_BACKUP_FILE" ] || fail "Leg 1: compressed dump not created"
  [ ! -f "$DB_BACKUP_FILE" ] || fail "Leg 1: uncompressed .sql was not removed"
  "$PY" "$MAINT" verify-dump --path "$COMPRESSED_DB_BACKUP_FILE" --min-size 1024 ||
    fail "Leg 1: verify-dump rejected the dump"

  # Restore through the dump's real disaster-recovery path: connect to the
  # maintenance DB and let the dump's DROP/CREATE DATABASE + \connect recreate
  # and repopulate the target. ON_ERROR_STOP makes any restore error fatal.
  gunzip -c "$COMPRESSED_DB_BACKUP_FILE" |
    PGPASSWORD="$POSTGRES_PASSWORD" psql -q -h "$POSTGRES_HOST" -U "$POSTGRES_USER" \
      -d postgres -v ON_ERROR_STOP=1 >/dev/null ||
    fail "Leg 1: restore failed"

  local restored_counts table_count
  restored_counts=$(table_counts "$POSTGRES_DB") || fail "Leg 1: could not read restored table counts"
  table_count=$(printf '%s\n' "$original_counts" | grep -c .)

  [ "$table_count" -ge 8 ] || fail "Leg 1: only $table_count tables — restore looks empty (expected the full u4i schema)"
  [ "$original_counts" = "$restored_counts" ] || fail "Leg 1: row counts differ between original and restored DB"
  ok "Leg 1 PASSED: dump verified + restored; $table_count tables, all row counts match original"
}

# ----------------------------------------------------------------------
# Leg 2 — log backup
# ----------------------------------------------------------------------
leg_log_backup() {
  echo "── Leg 2: log backup ──"
  export LOG_DIR="/app/volume/logs"
  mkdir -p "$LOG_DIR"
  LOG_FILE="${LOG_DIR}/$(date -d yesterday +%Y-%m-%d)_daily.log"
  export LOG_FILE
  export COMPRESSED_LOG_FILE="${LOG_FILE}.gz"
  printf 'sample log line\n' >"$LOG_FILE"

  local log_rc
  (source /app/backup-logs.sh)
  log_rc=$?
  [ "$log_rc" -eq 0 ] || fail "Leg 2: backup-logs.sh exited $log_rc"
  [ -f "$COMPRESSED_LOG_FILE" ] || fail "Leg 2: compressed log not created"
  [ ! -f "$LOG_FILE" ] || fail "Leg 2: uncompressed log was not removed"
  "$PY" "$MAINT" verify-dump --path "$COMPRESSED_LOG_FILE" --min-size 0 ||
    fail "Leg 2: verify-dump rejected the log archive"
  ok "Leg 2 PASSED: log compressed, original removed, archive verified"
}

# ----------------------------------------------------------------------
# Leg 3 — prune wiring (bash → backup_maintenance.py, end to end)
# ----------------------------------------------------------------------
leg_prune() {
  echo "── Leg 3: prune wiring ──"
  local dir=/tmp/prune_test
  rm -rf "$dir"
  mkdir -p "$dir"
  # Distinct mtimes so survivor selection (sorted by mtime) is deterministic.
  local day
  for day in $(seq 1 95); do
    touch -d "$day days ago" "$dir/old_${day}_daily.sql.gz"
  done

  "$PY" "$MAINT" prune-logs --directory "$dir" --pattern '*.sql.gz' --max-files 90 >/dev/null ||
    fail "Leg 3: prune-logs exited non-zero"

  local remaining
  remaining=$(find "$dir" -name '*.sql.gz' | wc -l | tr -d ' ')
  [ "$remaining" -eq 90 ] || fail "Leg 3: expected 90 files to survive, found $remaining"
  for day in 91 92 93 94 95; do
    [ ! -f "$dir/old_${day}_daily.sql.gz" ] || fail "Leg 3: old_${day} should have been pruned"
  done
  ok "Leg 3 PASSED: 90 newest retained, 5 oldest pruned"
}

# ----------------------------------------------------------------------
# Leg 4 — remote (rclone) leg, with a stubbed rclone binary (no prod change).
# The scripts call bare `rclone`/`file`, so same-shell functions shadow them.
# ----------------------------------------------------------------------
leg_rclone_default() {
  echo "── Leg 4a: rclone leg (default day) ──"
  (
    rclone() {
      echo "rclone $*" >>/tmp/rclone-calls
      return 0
    }
    file() { echo "application/gzip"; }
    notify_step() { :; }
    export PRODUCTION=true
    export ACCESS_KEY=dummy SECRET_ACCESS_KEY=dummy R2_ENDPOINT=https://dummy.r2
    export COMPRESSED_DB_BACKUP_FILE=/tmp/fake_db_daily.sql.gz
    export COMPRESSED_LOG_FILE=/tmp/fake_log_daily.log.gz
    : >/tmp/rclone-calls
    : >"$COMPRESSED_DB_BACKUP_FILE"
    : >"$COMPRESSED_LOG_FILE"

    source /app/remote-object-storage.sh
    set +e # remote_backup returns its accumulated failure count
    remote_backup true true
    remote_rc=$?

    [ "$remote_rc" -eq 0 ] || {
      echo "❌ Leg 4a: remote_backup exited $remote_rc"
      exit 1
    }
    grep -q "copy .* remote:u4i-backups/" /tmp/rclone-calls || {
      echo "❌ Leg 4a: no database copy to u4i-backups"
      exit 1
    }
    grep -q "copy .* remote:u4i-logs/" /tmp/rclone-calls || {
      echo "❌ Leg 4a: no log copy to u4i-logs"
      exit 1
    }
  ) || exit 1
  ok "Leg 4a PASSED: db + log copies issued to the expected buckets"
}

leg_rclone_monthly() {
  echo "── Leg 4b: rclone leg (forced first-of-month) ──"
  (
    rclone() {
      echo "rclone $*" >>/tmp/rclone-calls-monthly
      return 0
    }
    file() { echo "application/gzip"; }
    # Force the day-of-month-1 branch regardless of the calendar.
    date() { if [ "${1:-}" = "+%d" ]; then echo "01"; else command date "$@"; fi; }
    notify_step() { :; }
    export PRODUCTION=true
    export ACCESS_KEY=dummy SECRET_ACCESS_KEY=dummy R2_ENDPOINT=https://dummy.r2
    export COMPRESSED_DB_BACKUP_FILE=/tmp/fake_db_daily.sql.gz
    export COMPRESSED_LOG_FILE=/tmp/fake_log_daily.log.gz
    : >/tmp/rclone-calls-monthly
    : >"$COMPRESSED_DB_BACKUP_FILE"
    : >"$COMPRESSED_LOG_FILE"

    source /app/remote-object-storage.sh
    set +e
    remote_backup true true
    remote_rc=$?

    [ "$remote_rc" -eq 0 ] || {
      echo "❌ Leg 4b: remote_backup exited $remote_rc"
      exit 1
    }
    backup_copies=$(grep -c "remote:u4i-backups/" /tmp/rclone-calls-monthly)
    [ "$backup_copies" -ge 2 ] || {
      echo "❌ Leg 4b: expected >=2 backup copies (daily+monthly), got $backup_copies"
      exit 1
    }
    monthly_file="${COMPRESSED_DB_BACKUP_FILE/daily/monthly}"
    [ ! -f "$monthly_file" ] || {
      echo "❌ Leg 4b: monthly temp file was not cleaned up"
      exit 1
    }
  ) || exit 1
  ok "Leg 4b PASSED: monthly copy issued and temp file cleaned"
}

# ----------------------------------------------------------------------
# Leg 6 — real rclone upload against a MinIO (S3-compatible) sidecar.
# Unlike Leg 4 (which stubs rclone), this runs the genuine upload code path —
# config assembly, auth, copy, --header-upload — against a real S3 server, and
# confirms the objects actually persisted. MinIO creds/endpoint come from the
# orchestrator via the environment (MINIO_USER / MINIO_PASS / MINIO_ENDPOINT).
# ----------------------------------------------------------------------
leg_rclone_minio() {
  echo "── Leg 6: real rclone upload to MinIO (S3) ──"
  (
    export PRODUCTION=true
    export ACCESS_KEY="$MINIO_USER" SECRET_ACCESS_KEY="$MINIO_PASS" R2_ENDPOINT="$MINIO_ENDPOINT"
    export COMPRESSED_DB_BACKUP_FILE=/tmp/minio_test_daily.sql.gz
    export COMPRESSED_LOG_FILE=/tmp/minio_test_daily.log.gz
    printf 'real db payload\n' | gzip >"$COMPRESSED_DB_BACKUP_FILE"
    printf 'real log payload\n' | gzip >"$COMPRESSED_LOG_FILE"
    notify_step() { :; }

    source /app/remote-object-storage.sh
    set +e
    remote_backup true true
    remote_rc=$?
    [ "$remote_rc" -eq 0 ] || {
      echo "❌ Leg 6: remote_backup exited $remote_rc (real upload failed)"
      exit 1
    }

    # Re-establish a minimal rclone config (remote_backup unset it) and confirm
    # the objects truly landed in MinIO.
    export RCLONE_CONFIG_REMOTE_TYPE=s3
    export RCLONE_CONFIG_REMOTE_PROVIDER=Other
    export RCLONE_CONFIG_REMOTE_ACCESS_KEY_ID="$MINIO_USER"
    export RCLONE_CONFIG_REMOTE_SECRET_ACCESS_KEY="$MINIO_PASS"
    export RCLONE_CONFIG_REMOTE_ENDPOINT="$MINIO_ENDPOINT"
    rclone ls remote:u4i-backups/ | grep -q "minio_test_daily.sql.gz" ||
      {
        echo "❌ Leg 6: db object not found in MinIO bucket"
        exit 1
      }
    rclone ls remote:u4i-logs/ | grep -q "minio_test_daily.log.gz" ||
      {
        echo "❌ Leg 6: log object not found in MinIO bucket"
        exit 1
      }
  ) || exit 1
  ok "Leg 6 PASSED: real upload landed in both MinIO buckets"
}

leg_db_backup_and_restore
leg_log_backup
leg_prune
leg_rclone_default
leg_rclone_monthly
leg_rclone_minio

echo "✅ ALL DRIVER LEGS PASSED"
