#!/usr/bin/env bash
#
# One-shot provisioning for the merged local Postgres cluster, run by the compose
# `db-init` service on every `up`. The postgres image's initdb hooks never re-run
# on a non-empty pgdata volume, so everything here is idempotent. Every value
# reaches SQL through psql variables (\getenv), never through shell-built SQL.
#
# In order:
#   1. create/update the test role (attributes, connection limit and password re-applied)
#   2. rename the legacy dev DB (.env POSTGRES_DB) to U4I_DEV_DB, once
#   3. create U4I_DEV_DB if missing
#   4. isolate the dev DB: re-allow connections, revoke PUBLIC CONNECT (the test role must not reach it)
#   5. revoke PUBLIC CONNECT on a legacy DB left orphaned (both it and U4I_DEV_DB exist), with a warning
#   6. create the base POSTGRES_TEST_DB owned by the test role if missing
# If any step fails, a recovery pass re-allows connections on the legacy DB (step 2 blocks them).
set -euo pipefail

: "${PGHOST:?PGHOST is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
: "${POSTGRES_TEST_DB:?POSTGRES_TEST_DB is required}"
: "${U4I_DEV_DB:?U4I_DEV_DB is required}"
: "${U4I_TEST_ROLE:?U4I_TEST_ROLE is required}"
: "${U4I_PG_TEST_CONN_LIMIT:?U4I_PG_TEST_CONN_LIMIT is required}"
export LEGACY_DEV_DB="${LEGACY_DEV_DB:-}"

fail() {
  echo "db-provision: $1" >&2
  exit 1
}

if [[ ! "$U4I_PG_TEST_CONN_LIMIT" =~ ^[0-9]{1,5}$ ]]; then
  fail "U4I_PG_TEST_CONN_LIMIT must be a non-negative integer of at most 5 digits, got '$U4I_PG_TEST_CONN_LIMIT'"
fi
# The role is altered to NOSUPERUSER below; aiming it at the cluster superuser would demote it.
if [[ "$U4I_TEST_ROLE" == "$POSTGRES_USER" ]]; then
  fail "U4I_TEST_ROLE must differ from POSTGRES_USER ('$POSTGRES_USER')"
fi
if [[ "$U4I_TEST_ROLE" == pg_* ]]; then
  fail "U4I_TEST_ROLE must not start with 'pg_' (reserved), got '$U4I_TEST_ROLE'"
fi
if [[ "$POSTGRES_TEST_DB" == "$U4I_DEV_DB" ]]; then
  fail "POSTGRES_TEST_DB must differ from U4I_DEV_DB ('$U4I_DEV_DB')"
fi
# Step 6 hands POSTGRES_TEST_DB to the test role, so it must never name a system database.
case "$POSTGRES_TEST_DB" in
  postgres | template0 | template1) fail "POSTGRES_TEST_DB must not be a system database, got '$POSTGRES_TEST_DB'" ;;
esac
# Otherwise the rename is skipped and step 6 hands the real dev data to the test role.
if [[ -n "$LEGACY_DEV_DB" && "$LEGACY_DEV_DB" == "$POSTGRES_TEST_DB" ]]; then
  fail "POSTGRES_DB and POSTGRES_TEST_DB are both '$POSTGRES_TEST_DB'; set distinct POSTGRES_DB and POSTGRES_TEST_DB in .env"
fi

export PGPASSWORD="$POSTGRES_PASSWORD"
PSQL=(psql -v ON_ERROR_STOP=1 -q -h "$PGHOST" -U "$POSTGRES_USER" -d postgres)

if ! "${PSQL[@]}" <<'SQL'; then
\getenv role U4I_TEST_ROLE
\getenv pw POSTGRES_PASSWORD
\getenv conn_limit U4I_PG_TEST_CONN_LIMIT
\getenv dev U4I_DEV_DB
\getenv legacy LEGACY_DEV_DB
\getenv test_db POSTGRES_TEST_DB
\getenv pguser POSTGRES_USER

-- 1. Test role: created once, then attributes + connection limit + password re-applied every run.
SELECT format('CREATE ROLE %I LOGIN CREATEDB NOSUPERUSER', :'role')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'role') \gexec
SELECT format('ALTER ROLE %I WITH LOGIN CREATEDB NOSUPERUSER CONNECTION LIMIT %s',
  :'role', :'conn_limit'::int) \gexec
ALTER ROLE :"role" WITH PASSWORD :'pw';

-- 2. One-time rename of the legacy dev DB to the per-worktree name.
SELECT (:'legacy' <> ''
  AND :'legacy' <> :'dev'
  AND :'legacy' NOT IN ('postgres', 'template0', 'template1', :'test_db')
  AND EXISTS (SELECT FROM pg_database WHERE datname = :'legacy')
  AND NOT EXISTS (SELECT FROM pg_database WHERE datname = :'dev')) AS do_rename \gset
\if :do_rename
-- Block reconnects (e.g. a still-running old web pool) before terminating, so the rename cannot race them.
SELECT format('ALTER DATABASE %I ALLOW_CONNECTIONS false', :'legacy') \gexec
SELECT pg_terminate_backend(pid, 5000)
FROM pg_stat_activity WHERE datname = :'legacy' AND pid <> pg_backend_pid() \g /dev/null
SELECT format('ALTER DATABASE %I RENAME TO %I', :'legacy', :'dev') \gexec
\echo db-provision: renamed legacy dev database :legacy to :dev
\endif

-- 3. Dev DB exists (fresh volume, or a worktree whose slug differs from the legacy name).
SELECT format('CREATE DATABASE %I OWNER %I', :'dev', :'pguser')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'dev') \gexec

-- 4. Isolate the dev DB: Postgres grants CONNECT to PUBLIC by default. ALLOW_CONNECTIONS is
-- re-applied every run so a rename interrupted after step 2's block cannot leave it locked.
ALTER DATABASE :"dev" ALLOW_CONNECTIONS true;
REVOKE CONNECT ON DATABASE :"dev" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"dev" TO :"pguser";

-- 5. A legacy DB that was not renamed (U4I_DEV_DB already existed) is left intact but isolated too.
SELECT (:'legacy' <> ''
  AND :'legacy' <> :'dev'
  AND :'legacy' NOT IN ('postgres', 'template0', 'template1', :'test_db')
  AND EXISTS (SELECT FROM pg_database WHERE datname = :'legacy')) AS orphaned \gset
\if :orphaned
SELECT format('REVOKE CONNECT ON DATABASE %I FROM PUBLIC', :'legacy') \gexec
\echo db-provision: WARNING orphaned legacy database :legacy left untouched apart from revoking PUBLIC CONNECT
\endif

-- 6. Base test DB for the `test` bind / ConfigTest, owned by the test role.
SELECT format('CREATE DATABASE %I OWNER %I', :'test_db', :'role')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'test_db') \gexec
ALTER DATABASE :"test_db" OWNER TO :"role";

\echo db-provision: role :role, dev database :dev, test database :test_db ready
SQL
  echo "db-provision: provisioning failed; re-allowing connections on legacy database '$LEGACY_DEV_DB' if present" >&2
  "${PSQL[@]}" <<'SQL'
\getenv legacy LEGACY_DEV_DB
SELECT format('ALTER DATABASE %I ALLOW_CONNECTIONS true', :'legacy')
WHERE :'legacy' <> '' AND EXISTS (SELECT FROM pg_database WHERE datname = :'legacy') \gexec
SQL
  exit 1
fi
