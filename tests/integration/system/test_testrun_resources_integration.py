"""Real Postgres + Redis round-trips for per-run leasing and the reaper.

The unit tests cover the pure selection logic; these prove it against the live
shared Redis DB 0 and the cluster's `pg_database`. Every key and database the
tests seed carries a unique `uuid4` name and is cleaned up in `finally`.
"""

from __future__ import annotations

import re
import threading
import time
import uuid
from typing import Generator

import pytest
from redis import Redis
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from backend.config import (
    POSTGRES_PASSWORD,
    POSTGRES_TEST_DB,
    POSTGRES_TEST_USER,
    TEST_DB_HOST,
    TEST_REDIS_URI,
)
from backend.utils.db_uri_builder import build_db_uri
from scripts import testrun_resources

pytestmark = pytest.mark.cli

CONCURRENT_LEASE_THREADS: int = 8
IT_POOL_CANDIDATE_COUNT: int = 16
REAP_SUMMARY_PATTERN: re.Pattern[str] = re.compile(
    r"^dropped \d+ databases, released \d+ leases\Z"
)


@pytest.fixture
def shared_lease_client() -> Generator[Redis, None, None]:
    """String-decoding client on the shared-redis DB 0, where every lease lives."""
    lease_uri = testrun_resources.lease_db_uri(TEST_REDIS_URI)
    if lease_uri is None:
        pytest.skip("shared redis backend not configured (memory://)")
    client = Redis.from_url(lease_uri, decode_responses=True)
    try:
        yield client
    finally:
        client.close()


@pytest.fixture
def admin_connection() -> Generator[Connection, None, None]:
    """AUTOCOMMIT connection to `postgres` as the test role, like the reaper's."""
    engine = create_engine(
        build_db_uri(
            username=POSTGRES_TEST_USER,
            password=POSTGRES_PASSWORD,
            database="postgres",
            database_host=TEST_DB_HOST,
        ),
        isolation_level="AUTOCOMMIT",
    )
    try:
        with engine.connect() as connection:
            yield connection
    finally:
        engine.dispose()


def _it_pool() -> str:
    """A test-only pool name, so no real run's leases are ever touched."""
    return f"it-{uuid.uuid4().hex}"


def _absent_uid(live_uid8s: set[str]) -> str:
    """A 32-hex testrun_uid whose uid8 segment matches no live test database."""
    while True:
        fake_uid = uuid.uuid4().hex
        if fake_uid[:8] not in live_uid8s:
            return fake_uid


def _live_uid8s(admin_connection: Connection) -> set[str]:
    assert POSTGRES_TEST_DB
    return testrun_resources.live_test_run_uid8s(
        (
            datname
            for datname, _, _ in testrun_resources.fetch_database_rows(admin_connection)
        ),
        POSTGRES_TEST_DB,
    )


def test_concurrent_acquires_get_distinct_indices_and_all_release(
    shared_lease_client: Redis, testrun_uid: str, worker_id: str
) -> None:
    """
    GIVEN one test-only lease pool on the real shared redis DB 0
    WHEN 8 threads call `acquire_lease` over it at the same moment
    THEN every thread gets a distinct index, and releasing them leaves no key behind.
    """
    pool = _it_pool()
    candidates = list(range(IT_POOL_CANDIDATE_COUNT))
    start_barrier = threading.Barrier(CONCURRENT_LEASE_THREADS)
    leased: dict[str, int] = {}
    thread_errors: list[BaseException] = []
    leased_lock = threading.Lock()

    def _acquire(thread_number: int) -> None:
        owner = testrun_resources.lease_owner(
            testrun_uid, f"{worker_id}-t{thread_number}"
        )
        try:
            start_barrier.wait()
            index = testrun_resources.acquire_lease(
                shared_lease_client, pool, candidates, owner
            )
            with leased_lock:
                leased[owner] = index
        except BaseException as thread_error:
            with leased_lock:
                thread_errors.append(thread_error)

    threads = [
        threading.Thread(target=_acquire, args=(thread_number,))
        for thread_number in range(CONCURRENT_LEASE_THREADS)
    ]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert thread_errors == []
        assert len(leased) == CONCURRENT_LEASE_THREADS
        assert len(set(leased.values())) == CONCURRENT_LEASE_THREADS
    finally:
        for owner, index in leased.items():
            testrun_resources.release_lease(shared_lease_client, pool, index, owner)

    remaining = list(
        shared_lease_client.scan_iter(
            match=f"{testrun_resources.LEASE_KEY_PREFIX}:{pool}:*"
        )
    )
    assert remaining == []


def test_lease_of_a_run_without_databases_is_an_orphan(
    shared_lease_client: Redis,
    admin_connection: Connection,
    worker_db_uri: str,
    testrun_uid: str,
    worker_id: str,
) -> None:
    """
    GIVEN a real lease owned by this live run, read back by `scan_leases`, plus a
        synthetic in-memory lease of a run with no DB
    WHEN `select_orphan_leases` runs on them against the real `pg_database`
    THEN only the lease of the run without databases is returned.

    The orphan is never written to Redis: a concurrent run's reaper would
    rightly delete a real orphan key mid-test.
    """
    pool = _it_pool()
    live_uid8s = _live_uid8s(admin_connection)
    assert testrun_uid[:8] in live_uid8s
    live_key = testrun_resources.lease_key(pool, 0)
    orphan_key = testrun_resources.lease_key(pool, 1)
    live_owner = testrun_resources.lease_owner(testrun_uid, worker_id)
    shared_lease_client.set(
        live_key, live_owner, ex=testrun_resources.LEASE_TTL_SECONDS
    )
    try:
        scanned_leases = testrun_resources.scan_leases(shared_lease_client)
        assert scanned_leases.get(live_key) == live_owner
        lease_items = [
            (key, owner)
            for key, owner in scanned_leases.items()
            if key.startswith(f"{testrun_resources.LEASE_KEY_PREFIX}:{pool}:")
        ]
        lease_items.append(
            (orphan_key, testrun_resources.lease_owner(_absent_uid(live_uid8s), "gw0"))
        )

        assert testrun_resources.select_orphan_leases(lease_items, live_uid8s) == [
            orphan_key
        ]
    finally:
        shared_lease_client.delete(live_key)


def test_own_connected_worker_database_is_never_selected(
    admin_connection: Connection,
    worker_db_uri: str,
    testrun_uid: str,
    worker_id: str,
) -> None:
    """
    GIVEN this worker's own per-run database, with a connection held open to it
    WHEN the reaper's real `pg_database` query runs with a TTL of zero
    THEN the DB is listed with a parseable creation epoch and at least one
        connection, and `select_stale_test_dbs` does not select it.
    """
    assert POSTGRES_TEST_DB
    own_db_name = testrun_resources.test_db_name(
        POSTGRES_TEST_DB, testrun_uid, worker_id
    )
    worker_engine = create_engine(worker_db_uri)
    try:
        with worker_engine.connect() as worker_connection:
            worker_connection.execute(text("SELECT 1"))
            rows = testrun_resources.fetch_database_rows(admin_connection)
    finally:
        worker_engine.dispose()

    own_rows = [row for row in rows if row[0] == own_db_name]
    assert len(own_rows) == 1
    _, own_comment, own_connections = own_rows[0]
    assert testrun_resources.parse_created_epoch(own_comment) is not None
    assert own_connections >= 1
    assert own_db_name not in testrun_resources.select_stale_test_dbs(
        rows, POSTGRES_TEST_DB, int(time.time()), ttl_seconds=0
    )


def test_reap_drops_leaked_resources_and_never_touches_other_db0_keys(
    shared_lease_client: Redis,
    admin_connection: Connection,
    worker_db_uri: str,
    testrun_uid: str,
    worker_id: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    GIVEN an unrelated sentinel key on shared-redis DB 0, a leaked test DB with an
        ancient creation epoch, that leaked run's lease, and a lease of this live run
    WHEN the real `main(["reap", ...])` flow runs end to end
    THEN the leaked DB and its lease are reclaimed, while the sentinel, the live
        lease and this worker's own DB all survive.

    This is the real end-to-end `main`. Its TTL is the lease lifetime rather than
    0, so it never drops sibling workers' (or a concurrent run's) fresh, idle DBs.
    Assertions are state-based: a concurrent reaper from another run may reclaim
    the leaked DB or lease first, so the per-item output lines are not required.
    Every seeded key expires with the lease TTL, so a SIGKILL mid-test leaves no
    permanent keys.
    """
    assert POSTGRES_TEST_DB
    unique_suffix = uuid.uuid4().hex
    sentinel_key = f"it-sentinel:{unique_suffix}"
    pool = f"it-{unique_suffix}"
    leaked_uid = _absent_uid(_live_uid8s(admin_connection))
    leaked_db_name = testrun_resources.test_db_name(
        POSTGRES_TEST_DB, leaked_uid, "gw999"
    )
    leaked_lease_key = testrun_resources.lease_key(pool, 0)
    live_lease_key = testrun_resources.lease_key(pool, 1)
    own_db_name = testrun_resources.test_db_name(
        POSTGRES_TEST_DB, testrun_uid, worker_id
    )
    reap_ttl_minutes = (
        testrun_resources.LEASE_TTL_SECONDS // testrun_resources.SECONDS_PER_MINUTE
    )
    key_ttl_seconds = testrun_resources.LEASE_TTL_SECONDS

    shared_lease_client.set(sentinel_key, "must-survive", ex=key_ttl_seconds)
    shared_lease_client.set(
        leaked_lease_key,
        testrun_resources.lease_owner(leaked_uid, "gw999"),
        ex=key_ttl_seconds,
    )
    shared_lease_client.set(
        live_lease_key,
        testrun_resources.lease_owner(testrun_uid, worker_id),
        ex=key_ttl_seconds,
    )
    admin_connection.execute(text(f'CREATE DATABASE "{leaked_db_name}"'))
    admin_connection.execute(
        text(f"COMMENT ON DATABASE \"{leaked_db_name}\" IS 'u4i-test created_epoch=0'")
    )
    try:
        assert (
            testrun_resources.main(["reap", "--ttl-minutes", str(reap_ttl_minutes)])
            == 0
        )
        reap_output = capsys.readouterr().out

        remaining_names = {
            datname
            for datname, _, _ in testrun_resources.fetch_database_rows(admin_connection)
        }
        assert leaked_db_name not in remaining_names
        assert own_db_name in remaining_names
        assert shared_lease_client.get(sentinel_key) == "must-survive"
        assert shared_lease_client.exists(leaked_lease_key) == 0
        assert shared_lease_client.exists(live_lease_key) == 1
        assert REAP_SUMMARY_PATTERN.match(reap_output.splitlines()[0])
    finally:
        shared_lease_client.delete(sentinel_key, leaked_lease_key, live_lease_key)
        admin_connection.execute(text(f'DROP DATABASE IF EXISTS "{leaked_db_name}"'))
