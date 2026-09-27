"""Per-run test-resource naming and leasing, shared by every pytest fixture site.

xdist's `worker_id` is unique only inside one pytest invocation, so two runs on
one host collided on the same databases and Redis indices. Everything here is
keyed on the run (`testrun_uid`) instead:

- Postgres test databases are named `{prefix}_{uid8}_{worker}`.
- Redis indices are leased with self-expiring `SET NX EX` owner keys on the
  shared redis DB 0, so a crashed run's leases lapse on their own.
- Flask port probes start at a run-derived offset inside each worker's band.

The module name deliberately does not match `test_*.py`, so pytest never
collects it.
"""

from __future__ import annotations

import re
import string
from typing import Protocol

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


class LeaseClient(Protocol):
    """The subset of the redis-py client the lease functions use."""

    def set(
        self, name: str, value: str, /, *, nx: bool = ..., ex: int = ...
    ) -> object: ...

    def eval(self, script: str, numkeys: int, /, *keys_and_args: str) -> object: ...


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
