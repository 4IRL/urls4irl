#!/usr/bin/env bash
#
# One-shot provisioning for the shared local Postgres cluster (the per-user hub `db`), in one of two
# scopes picked by U4I_PROVISION_SCOPE. The postgres image's initdb hooks never re-run on a non-empty
# pgdata volume, so everything here is idempotent. Every value reaches SQL through psql variables
# (\getenv), never through shell-built SQL.
#
# U4I_PROVISION_SCOPE=cluster (the hub's `cluster-init`, run by every `make hub-up`), cluster-wide:
#   1. create/update the test role (attributes, connection limit and password re-applied)
#   2. create the base POSTGRES_TEST_DB owned by the test role if missing
#   Both run in one psql session holding a session-level advisory lock, so two concurrent
#   cluster-inits (two spokes' first `hub-up` at once) serialize: the second waits, then finds the
#   role and DB present and takes the idempotent ALTER path, instead of losing the
#   NOT EXISTS ... \gexec check-then-act race with a duplicate_object error. The lock is not
#   transactional (so step 2's CREATE DATABASE may run under it) and is released when the session
#   ends, including on an ON_ERROR_STOP abort.
#
# U4I_PROVISION_SCOPE=spoke (each spoke's `db-init`, run by every `make up`), this spoke's dev DB only:
#   1. create U4I_DEV_DB if missing
#   2. isolate it: allow connections, revoke PUBLIC CONNECT (the test role must not reach it)
#   No lock: its only cluster-wide write is CREATE DATABASE of its own U4I_DEV_DB, which never
#   collides across spokes.
#
# Both scopes first wait (up to 60s) for PGHOST to accept TCP connections.
set -euo pipefail

: "${PGHOST:?PGHOST is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
# Both scopes: cluster creates and owns it, spoke needs it for the collision guard.
: "${POSTGRES_TEST_DB:?POSTGRES_TEST_DB is required}"

READY_TIMEOUT_SECONDS=60

fail() {
  echo "db-provision: $1" >&2
  exit 1
}

PROVISION_SCOPE="${U4I_PROVISION_SCOPE:-}"
case "$PROVISION_SCOPE" in
  cluster)
    : "${U4I_TEST_ROLE:?U4I_TEST_ROLE is required}"
    : "${U4I_PG_TEST_CONN_LIMIT:?U4I_PG_TEST_CONN_LIMIT is required}"
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
    # Cluster step 2 hands POSTGRES_TEST_DB to the test role, so it must never name a system database.
    case "$POSTGRES_TEST_DB" in
      postgres | template0 | template1) fail "POSTGRES_TEST_DB must not be a system database, got '$POSTGRES_TEST_DB'" ;;
    esac
    ;;
  spoke)
    : "${U4I_DEV_DB:?U4I_DEV_DB is required}"
    if [[ "$POSTGRES_TEST_DB" == "$U4I_DEV_DB" ]]; then
      fail "POSTGRES_TEST_DB must differ from U4I_DEV_DB ('$U4I_DEV_DB')"
    fi
    ;;
  *) fail "U4I_PROVISION_SCOPE must be 'cluster' or 'spoke', got '$PROVISION_SCOPE'" ;;
esac

export PGPASSWORD="$POSTGRES_PASSWORD"

# The hub db may still be starting (or, on a fresh volume, in its socket-only first-init phase).
# pg_isready exits 1 (rejecting connections, e.g. starting up) or 2 (no response) while the server
# comes up: retry those. Exit 3 means no attempt was made (bad parameters), which never heals.
ready_output=""
for attempt in $(seq 1 "$READY_TIMEOUT_SECONDS"); do
  ready_status=0
  ready_output="$(pg_isready -t 1 -h "$PGHOST" -U "$POSTGRES_USER" -d postgres 2>&1)" || ready_status=$?
  if [[ "$ready_status" == 0 ]]; then
    break
  fi
  if [[ "$ready_status" != 1 && "$ready_status" != 2 ]]; then
    fail "pg_isready against $PGHOST exited $ready_status (no connection attempt made): $ready_output"
  fi
  if [[ "$attempt" == "$READY_TIMEOUT_SECONDS" ]]; then
    fail "$PGHOST not ready after ${READY_TIMEOUT_SECONDS}s: $ready_output"
  fi
  if [[ "$attempt" == 1 ]]; then
    echo "db-provision: waiting for $PGHOST"
  fi
  sleep 1
done

PSQL=(psql -v ON_ERROR_STOP=1 -q -h "$PGHOST" -U "$POSTGRES_USER" -d postgres)

case "$PROVISION_SCOPE" in
  cluster)
    "${PSQL[@]}" <<'SQL'
\getenv role U4I_TEST_ROLE
\getenv pw POSTGRES_PASSWORD
\getenv conn_limit U4I_PG_TEST_CONN_LIMIT
\getenv test_db POSTGRES_TEST_DB

-- Bound the lock wait: a wedged cluster-init session holding the lock would otherwise hang every
-- later hub-up forever. Session-level, so it covers the advisory lock below in this same session.
SET lock_timeout = '120s';
SELECT pg_advisory_lock(hashtext('u4i-cluster-provision')) \g /dev/null

-- 1. Test role: created once, then attributes + connection limit + password re-applied every run.
SELECT format('CREATE ROLE %I LOGIN CREATEDB NOSUPERUSER', :'role')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'role') \gexec
SELECT format('ALTER ROLE %I WITH LOGIN CREATEDB NOSUPERUSER CONNECTION LIMIT %s',
  :'role', :'conn_limit'::int) \gexec
ALTER ROLE :"role" WITH PASSWORD :'pw';

-- 2. Base test DB for the `test` bind / ConfigTest, owned by the test role.
SELECT format('CREATE DATABASE %I OWNER %I', :'test_db', :'role')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'test_db') \gexec
ALTER DATABASE :"test_db" OWNER TO :"role";

SELECT pg_advisory_unlock(hashtext('u4i-cluster-provision')) \g /dev/null

\echo db-provision: role :role and test database :test_db ready
SQL
    ;;
  spoke)
    "${PSQL[@]}" <<'SQL'
\getenv dev U4I_DEV_DB
\getenv pguser POSTGRES_USER

-- 1. This spoke's dev DB exists.
SELECT format('CREATE DATABASE %I OWNER %I', :'dev', :'pguser')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'dev') \gexec

-- 2. Isolate the dev DB: Postgres grants CONNECT to PUBLIC by default.
ALTER DATABASE :"dev" ALLOW_CONNECTIONS true;
REVOKE CONNECT ON DATABASE :"dev" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"dev" TO :"pguser";

\echo db-provision: dev database :dev ready
SQL
    ;;
esac
