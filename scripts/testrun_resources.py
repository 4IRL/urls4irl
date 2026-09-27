"""Per-run test-resource naming and leasing, shared by every pytest fixture site.

xdist's `worker_id` is unique only inside one pytest invocation, so two runs on
one host collided on the same databases and Redis indices. Everything here is
keyed on the run (`testrun_uid`) instead:

- Postgres test databases are named `{prefix}_{uid8}_{worker}`.
- Redis indices are leased with self-expiring `SET NX EX` owner keys on the
  shared redis DB 0, so a crashed run's leases lapse on their own.
- Flask port probes start at a run-derived offset inside each worker's band.

Unique names turn collisions into leaks, so the module is also the
`make reset-test-dbs` reaper (`python -m scripts.testrun_resources reap`): it
drops idle, aged per-run test databases and deletes the leases their runs left.

The module name deliberately does not match `test_*.py`, so pytest never
collects it.
"""

from __future__ import annotations

import argparse
import re
import string
import time
from collections.abc import Iterable
from typing import Protocol

from redis import Redis
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError

from backend.config import (
    POSTGRES_PASSWORD,
    POSTGRES_TEST_DB,
    POSTGRES_TEST_USER,
    TEST_DB_HOST,
    TEST_REDIS_URI,
)
from backend.utils.db_uri_builder import build_db_uri

DB_NAME_PATTERN: re.Pattern[str] = re.compile(r"^[a-z0-9_]+$")
WORKER_ID_PATTERN: re.Pattern[str] = re.compile(r"gw[0-9]+|master")
MAX_IDENTIFIER_BYTES: int = 63  # Postgres NAMEDATALEN - 1
UID_SEGMENT_LENGTH: int = 8
DEV_DB_PREFIX: str = "u4i_dev_"

LEASE_KEY_PREFIX: str = "u4i:test_lease"
LEASE_TTL_SECONDS: int = 6 * 60 * 60
SESSION_POOL: str = "redis"
METRICS_POOL: str = "metrics"
METRICS_RESERVED_INDICES: frozenset[int] = frozenset({0})

# Compare-and-delete: only the owner that set a lease may release it.
RELEASE_SCRIPT: str = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('del', KEYS[1]) else return 0 end"
)

PORT_BASE: int = 10000
PORT_BAND_PER_WORKER: int = 1000
PORT_JITTER_RANGE: int = 500

_LOWERCASE_HEX_DIGITS: frozenset[str] = frozenset(string.hexdigits.lower())
_DEV_SLUG_DISALLOWED: re.Pattern[str] = re.compile(r"[^a-z0-9_]")

# `worker_db_uri` stamps every per-run database with this comment at creation.
CREATED_EPOCH_COMMENT_PATTERN: re.Pattern[str] = re.compile(
    r"^u4i-test created_epoch=([0-9]+)\Z"
)
REAP_DEFAULT_TTL_MINUTES: int = 10
SECONDS_PER_MINUTE: int = 60
LEASE_SCAN_PATTERN: str = f"{LEASE_KEY_PREFIX}:*"
LEASE_SCAN_BATCH: int = 500
REDIS_URI_WITH_DB_PATTERN: re.Pattern[str] = re.compile(r"^(.+)/([0-9]+)\Z")
MEMORY_REDIS_URI: str = "memory://"
# Pause between the reaper's two `pg_database` listings; see `main`.
STALE_CONFIRM_DELAY_SECONDS: float = 1.0
# SQLSTATEs a per-database DROP may hit without the reap as a whole being wrong:
# a connection opened after the selection (object_in_use), or a matching name
# the reaper's role does not own (insufficient_privilege).
DROP_SKIPPABLE_SQLSTATES: frozenset[str] = frozenset({"55006", "42501"})
DATABASE_ROWS_QUERY: str = (
    "SELECT d.datname, shobj_description(d.oid, 'pg_database'), "
    "(SELECT count(*) FROM pg_stat_activity a WHERE a.datname = d.datname) "
    "FROM pg_database d"
)


class LeaseClient(Protocol):
    """The subset of the redis-py client the lease functions use."""

    def set(
        self, name: str, value: str, /, *, nx: bool = ..., ex: int = ...
    ) -> object: ...

    def eval(self, script: str, numkeys: int, /, *keys_and_args: str) -> object: ...


class LeaseScanClient(LeaseClient, Protocol):
    """The lease client plus the `SCAN MATCH` and `GET` the reaper uses."""

    def scan_iter(self, match: str, count: int) -> Iterable[str]: ...

    def get(self, name: str, /) -> str | None: ...


def _validate_test_db_prefix(prefix: str) -> None:
    """Validate a POSTGRES_TEST_DB prefix, shared by test_db_name and test_db_name_regex."""
    if not DB_NAME_PATTERN.fullmatch(prefix):
        raise ValueError(
            f"POSTGRES_TEST_DB {prefix!r} must match {DB_NAME_PATTERN.pattern} "
            "to be used as a per-run test database name prefix"
        )
    dev_prefix = DEV_DB_PREFIX.rstrip("_")
    if prefix.startswith(dev_prefix):
        raise ValueError(
            f"POSTGRES_TEST_DB {prefix!r} must not start with {dev_prefix!r}; "
            "a test prefix that overlaps the dev database prefix could make the "
            "reaper match dev databases"
        )


def _uid_segment(testrun_uid: str) -> str:
    """Return the validated lowercase-hex first 8 characters of `testrun_uid`."""
    # Lowercase is required because xdist derives testrun_uid from uuid4().hex,
    # and the reaper regex / DB_NAME_PATTERN only accept [0-9a-f].
    uid_segment = testrun_uid[:UID_SEGMENT_LENGTH]
    if len(uid_segment) != UID_SEGMENT_LENGTH or not set(uid_segment).issubset(
        _LOWERCASE_HEX_DIGITS
    ):
        raise ValueError(
            f"testrun_uid {testrun_uid!r} must start with {UID_SEGMENT_LENGTH} "
            "lowercase hex characters to build a POSTGRES_TEST_DB worker database name"
        )
    return uid_segment


def test_db_name(prefix: str, testrun_uid: str, worker_id: str) -> str:
    """Return the run-scoped database name for one xdist worker (`master` included)."""
    _validate_test_db_prefix(prefix)
    if not WORKER_ID_PATTERN.fullmatch(worker_id):
        raise ValueError(
            f"worker_id {worker_id!r} must be gw<N> or master to build a "
            "POSTGRES_TEST_DB worker database name"
        )
    uid_segment = _uid_segment(testrun_uid)
    worker_db_name = f"{prefix}_{uid_segment}_{worker_id}"
    if len(worker_db_name.encode()) > MAX_IDENTIFIER_BYTES:
        raise ValueError(
            f"Test database name {worker_db_name!r} exceeds {MAX_IDENTIFIER_BYTES} "
            "bytes; shorten POSTGRES_TEST_DB"
        )
    return worker_db_name


def test_db_name_regex(prefix: str) -> re.Pattern[str]:
    """Return the pattern the reaper uses to select per-run test databases."""
    _validate_test_db_prefix(prefix)
    return re.compile(rf"^{re.escape(prefix)}_([0-9a-f]{{8}})_(gw[0-9]+|master)\Z")


def dev_db_name(slug: str) -> str:
    """Return the per-worktree dev database name, `u4i_dev_<sanitized slug>`."""
    # The sanitizer only allows [a-z0-9_], so the output is pure ASCII and this
    # character slice doubles as a byte-length bound. Non-ASCII slugs are
    # unsupported here and differ from the Makefile's byte-wise `tr` sanitizer.
    sanitized = _DEV_SLUG_DISALLOWED.sub("_", slug.lower())[
        : MAX_IDENTIFIER_BYTES - len(DEV_DB_PREFIX)
    ]
    if not sanitized:
        raise ValueError("U4I_SLUG must be non-empty to derive the dev database name")
    return DEV_DB_PREFIX + sanitized


def lease_key(pool: str, index: int) -> str:
    return f"{LEASE_KEY_PREFIX}:{pool}:{index}"


def lease_owner(testrun_uid: str, worker_id: str) -> str:
    return f"{testrun_uid}:{worker_id}"


def lease_pool(database_count: int, reserved: frozenset[int]) -> list[int]:
    """Return the ascending leasable indices of a Redis instance."""
    candidates = [index for index in range(database_count) if index not in reserved]
    if not candidates:
        raise ValueError(
            f"No leasable Redis databases: {database_count} configured, "
            f"reserved {sorted(reserved)}"
        )
    return candidates


def acquire_lease(
    lease_client: LeaseClient,
    pool: str,
    candidates: list[int],
    owner: str,
    ttl_seconds: int = LEASE_TTL_SECONDS,
) -> int:
    """Lease the first free index in `candidates` for `owner`, or raise if all are held."""
    for index in candidates:
        if lease_client.set(lease_key(pool, index), owner, nx=True, ex=ttl_seconds):
            return index
    raise RuntimeError(
        f"Redis lease pool {pool!r} is exhausted: all {len(candidates)} candidate "
        "indices are leased. Run `make reset-test-dbs` to reclaim leaked leases, "
        "lower n, or re-run `make capacity` to grow the pool."
    )


def release_lease(lease_client: LeaseClient, pool: str, index: int, owner: str) -> bool:
    """Release `owner`'s lease on `index`; idempotent, never touches another owner's lease."""
    return bool(lease_client.eval(RELEASE_SCRIPT, 1, lease_key(pool, index), owner))


def worker_index(worker_id: str) -> int:
    """Return the xdist worker number (`master` is 0); never use it to pick a shared resource."""
    if not WORKER_ID_PATTERN.fullmatch(worker_id):
        raise ValueError(f"worker_id {worker_id!r} must be gw<N> or master")
    if worker_id == "master":
        return 0
    return int(worker_id.removeprefix("gw"))


def port_probe_start(testrun_uid: str, worker_number: int) -> int:
    """Return where a worker starts probing for a free Flask port, de-correlated per run."""
    uid_segment = _uid_segment(testrun_uid)
    return (
        PORT_BASE
        + worker_number * PORT_BAND_PER_WORKER
        + int(uid_segment[:4], 16) % PORT_JITTER_RANGE
    )


# --- reaper (`make reset-test-dbs`) ------------------------------------------------


def parse_created_epoch(comment: str | None) -> int | None:
    """Return the creation epoch `worker_db_uri` stamped on a test DB, else None."""
    if comment is None:
        return None
    epoch_match = CREATED_EPOCH_COMMENT_PATTERN.match(comment)
    return int(epoch_match.group(1)) if epoch_match else None


def select_stale_test_dbs(
    rows: list[tuple[str, str | None, int]],
    prefix: str,
    now_epoch: int,
    ttl_seconds: int,
) -> list[str]:
    """Return the per-run test DBs that are safe to drop, in row order.

    Each row is `(datname, comment, active_connections)`. A DB is selected only
    when its name is a per-run test DB name for `prefix`, it has no connections,
    and it either has no parseable creation epoch or is at least `ttl_seconds`
    old. The bare prefix, `postgres`, `template*` and `u4i_dev_*` never match
    the name pattern, and a connected DB is never selected, whatever its age.
    """
    test_db_pattern = test_db_name_regex(prefix)
    stale_names: list[str] = []
    for datname, comment, active_connections in rows:
        if not test_db_pattern.match(datname):
            continue
        if active_connections != 0:
            continue
        created_epoch = parse_created_epoch(comment)
        if created_epoch is None or now_epoch - created_epoch >= ttl_seconds:
            stale_names.append(datname)
    return stale_names


def confirm_stale(first_pass: list[str], second_pass: list[str]) -> list[str]:
    """Return the names stale in both listings, in `second_pass` order."""
    first_pass_names = set(first_pass)
    return [datname for datname in second_pass if datname in first_pass_names]


def live_test_run_uid8s(datnames: Iterable[str], prefix: str) -> set[str]:
    """Return the `testrun_uid[:8]` segments of every per-run test DB in `datnames`."""
    test_db_pattern = test_db_name_regex(prefix)
    return {
        name_match.group(1)
        for name_match in map(test_db_pattern.match, datnames)
        if name_match is not None
    }


def select_orphan_leases(
    lease_items: list[tuple[str, str]], live_uid8s: set[str]
) -> list[str]:
    """Return the lease keys whose owning run no longer has any test DB.

    Each item is `(key, owner)`, where the owner is `lease_owner(...)`. Keys
    outside the `u4i:test_lease:` namespace are never returned.
    """
    lease_namespace = f"{LEASE_KEY_PREFIX}:"
    return [
        key
        for key, owner in lease_items
        if key.startswith(lease_namespace)
        and owner[:UID_SEGMENT_LENGTH] not in live_uid8s
    ]


def split_redis_uri(redis_uri: str, env_name: str) -> tuple[str, int]:
    """Split `redis://host:port/N` into its base URI and DB index.

    Raises ValueError, naming `env_name`, when the URI lacks a trailing
    `/<digits>` DB index (a query string is rejected too).
    """
    uri_match = REDIS_URI_WITH_DB_PATTERN.match(redis_uri)
    if uri_match is None:
        raise ValueError(
            f"{env_name}={redis_uri!r} must have the form redis://host:port/N"
        )
    return uri_match.group(1), int(uri_match.group(2))


def lease_db_uri(redis_uri: str) -> str | None:
    """Return the shared-redis DB 0 URI where leases live, or None for `memory://`."""
    if not redis_uri or redis_uri == MEMORY_REDIS_URI:
        return None
    redis_base_uri, _ = split_redis_uri(redis_uri, "TEST_REDIS_URI")
    return f"{redis_base_uri}/0"


def fetch_database_rows(connection: Connection) -> list[tuple[str, str | None, int]]:
    """Return `(datname, comment, active_connections)` for every database."""
    return [
        (datname, comment, int(active_connections))
        for datname, comment, active_connections in connection.execute(
            text(DATABASE_ROWS_QUERY)
        )
    ]


def drop_idle_databases(
    connection: Connection, datnames: list[str]
) -> tuple[list[str], list[str]]:
    """Drop each DB without FORCE; return `(dropped, skipped)`.

    `WITH (FORCE)` is deliberately never used: a DB someone connected to after
    the selection makes Postgres refuse the DROP, and that DB is skipped.
    """
    dropped: list[str] = []
    skipped: list[str] = []
    for datname in datnames:
        if not DB_NAME_PATTERN.fullmatch(datname):
            raise ValueError(f"Refusing to drop unexpected database name {datname!r}")
        try:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{datname}"'))
        except DBAPIError as drop_error:
            if getattr(drop_error.orig, "pgcode", None) not in DROP_SKIPPABLE_SQLSTATES:
                raise
            skipped.append(datname)
        else:
            dropped.append(datname)
    return dropped, skipped


def scan_leases(lease_client: LeaseScanClient) -> dict[str, str]:
    """Return `{key: owner}` for every `u4i:test_lease:*` key on the lease DB.

    Only keys matching the lease pattern are scanned; a key that expires or is
    released between the SCAN and its GET is skipped.
    """
    lease_owners: dict[str, str] = {}
    for key in lease_client.scan_iter(match=LEASE_SCAN_PATTERN, count=LEASE_SCAN_BATCH):
        owner = lease_client.get(key)
        if owner is not None:
            lease_owners[key] = owner
    return lease_owners


def release_orphan_leases(
    lease_client: LeaseClient, lease_owners: dict[str, str], live_uid8s: set[str]
) -> list[str]:
    """Delete the scanned leases whose run has no test DB; return the keys deleted.

    Each delete is the owner compare-and-delete, so a lease re-acquired by a
    different owner between the scan and the delete is kept. Nothing else on
    DB 0 is touched, and it is never flushed.
    """
    return [
        key
        for key in select_orphan_leases(list(lease_owners.items()), live_uid8s)
        if lease_client.eval(RELEASE_SCRIPT, 1, key, lease_owners[key])
    ]


def _list_stale_test_dbs(connection: Connection, ttl_seconds: int) -> list[str]:
    return select_stale_test_dbs(
        fetch_database_rows(connection),
        POSTGRES_TEST_DB,
        int(time.time()),
        ttl_seconds,
    )


def _non_negative_int(raw_value: str) -> int:
    try:
        parsed_value = int(raw_value)
    except ValueError as conversion_error:
        raise argparse.ArgumentTypeError(
            f"{raw_value!r} is not an integer"
        ) from conversion_error
    if parsed_value < 0:
        raise argparse.ArgumentTypeError(f"{raw_value!r} must be 0 or more")
    return parsed_value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.testrun_resources",
        description="Per-run test resource maintenance.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    reap_parser = subcommands.add_parser(
        "reap",
        help="Drop leaked per-run test databases and delete orphaned Redis leases.",
    )
    reap_parser.add_argument(
        "--ttl-minutes",
        type=_non_negative_int,
        default=REAP_DEFAULT_TTL_MINUTES,
        help="Only drop idle test databases at least this old (default: %(default)s).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the reaper: drop idle, aged test DBs, then delete their runs' leases.

    It connects as the test role (`POSTGRES_TEST_USER`), which owns every
    per-run DB and cannot drop the dev databases, and never flushes Redis DB 0.

    Staleness is confirmed across two `pg_database` listings taken
    `STALE_CONFIRM_DELAY_SECONDS` apart. `worker_db_uri` runs CREATE DATABASE
    and COMMENT as separate statements, so for a few milliseconds a live
    worker's new DB has no epoch comment and no connections, which alone would
    select it as stale. A DB is dropped only when both listings select it.
    """
    arguments = _build_parser().parse_args(argv)
    if not POSTGRES_TEST_DB:
        raise SystemExit(
            "POSTGRES_TEST_DB must be set to select per-run test databases"
        )

    ttl_seconds = arguments.ttl_minutes * SECONDS_PER_MINUTE
    admin_uri = build_db_uri(
        username=POSTGRES_TEST_USER,
        password=POSTGRES_PASSWORD,
        database="postgres",
        database_host=TEST_DB_HOST,
    )
    lease_uri = lease_db_uri(TEST_REDIS_URI)
    released: list[str] = []
    engine = create_engine(admin_uri, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            first_pass = _list_stale_test_dbs(connection, ttl_seconds)
            time.sleep(STALE_CONFIRM_DELAY_SECONDS)
            second_pass = _list_stale_test_dbs(connection, ttl_seconds)
            dropped, skipped = drop_idle_databases(
                connection, confirm_stale(first_pass, second_pass)
            )

            if lease_uri is not None:
                # Ordering matters: SCAN first, list `pg_database` after. Fixtures
                # always create their DB before acquiring a lease, so a listing
                # taken after the scan covers the run of every scanned lease. A
                # listing taken before the scan would miss a run that started in
                # between, and its fresh lease would be deleted as an orphan.
                lease_client = Redis.from_url(lease_uri, decode_responses=True)
                try:
                    lease_owners = scan_leases(lease_client)
                    live_uid8s = live_test_run_uid8s(
                        (datname for datname, _, _ in fetch_database_rows(connection)),
                        POSTGRES_TEST_DB,
                    )
                    released = release_orphan_leases(
                        lease_client, lease_owners, live_uid8s
                    )
                finally:
                    lease_client.close()
    finally:
        engine.dispose()

    print(f"dropped {len(dropped)} databases, released {len(released)} leases")
    for datname in dropped:
        print(f"  dropped database {datname}")
    for datname in skipped:
        print(f"  skipped database {datname} (in use or not owned by the test role)")
    for key in released:
        print(f"  released lease {key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
