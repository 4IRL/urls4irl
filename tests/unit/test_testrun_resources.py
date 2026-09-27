"""Unit tests for per-run test-resource naming and leasing (`scripts/testrun_resources.py`).

No Postgres or Redis is touched: lease operations run against `_FakeLeaseClient`,
an in-memory stand-in that honors `SET NX EX` and the compare-and-delete script.
`test_db_name` / `test_db_name_regex` are reached through the module rather than
imported by name, so pytest never collects them as tests of this file.
"""

from __future__ import annotations

import fnmatch

import pytest

from scripts import capacity, testrun_resources
from scripts.testrun_resources import (
    DB_NAME_PATTERN,
    LEASE_KEY_PREFIX,
    LEASE_TTL_SECONDS,
    MAX_IDENTIFIER_BYTES,
    METRICS_POOL,
    METRICS_RESERVED_INDICES,
    RELEASE_SCRIPT,
    SESSION_POOL,
    acquire_lease,
    dev_db_name,
    lease_key,
    lease_owner,
    lease_pool,
    port_probe_start,
    release_lease,
    worker_index,
)

pytestmark = pytest.mark.unit

PREFIX: str = "u4i_test"
UID_A: str = "3fa9c2d1b4e5f60718293a4b5c6d7e8f"
UID_B: str = "0badc0de0badc0de0badc0de0badc0de"


class _FakeLeaseClient:
    """In-memory lease store: honors `SET NX EX` and the release script, records calls."""

    def __init__(self, preheld_keys: dict[str, str] | None = None) -> None:
        self.store: dict[str, str] = dict(preheld_keys or {})
        self.set_calls: list[tuple[str, str, bool, int]] = []
        self.eval_calls: list[tuple[str, int, str, str]] = []

    def set(
        self, name: str, value: str, /, *, nx: bool = False, ex: int = 0
    ) -> bool | None:
        self.set_calls.append((name, value, nx, ex))
        if nx and name in self.store:
            return None
        self.store[name] = value
        return True

    def eval(self, script: str, numkeys: int, /, *keys_and_args: str) -> int:
        key, owner = keys_and_args
        self.eval_calls.append((script, numkeys, key, owner))
        if self.store.get(key) == owner:
            del self.store[key]
            return 1
        return 0


# --- constants ----------------------------------------------------------------


def test_constants_have_the_documented_values() -> None:
    assert MAX_IDENTIFIER_BYTES == 63
    assert LEASE_KEY_PREFIX == "u4i:test_lease"
    assert LEASE_TTL_SECONDS == 6 * 60 * 60
    assert SESSION_POOL == "redis"
    assert METRICS_POOL == "metrics"
    assert METRICS_RESERVED_INDICES == frozenset({0})


def test_capacity_sizes_metrics_redis_for_the_reserved_indices() -> None:
    """`capacity.py` is stdlib-only, so it mirrors this set's size as a constant."""
    assert capacity.METRICS_REDIS_RESERVED_DBS == len(METRICS_RESERVED_INDICES)


@pytest.mark.parametrize(
    "candidate_name, is_valid",
    [("u4i_test", True), ("postgres", True), ("U4I_TEST", False), ("u4i-test", False)],
)
def test_db_name_pattern_accepts_only_lowercase_identifiers(
    candidate_name: str, is_valid: bool
) -> None:
    assert (DB_NAME_PATTERN.fullmatch(candidate_name) is not None) is is_valid


# --- test_db_name ---------------------------------------------------------------


def test_master_and_gw0_get_different_db_names_within_one_run() -> None:
    master_name = testrun_resources.test_db_name(PREFIX, UID_A, "master")
    gw0_name = testrun_resources.test_db_name(PREFIX, UID_A, "gw0")

    assert master_name == "u4i_test_3fa9c2d1_master"
    assert gw0_name == "u4i_test_3fa9c2d1_gw0"
    assert master_name != gw0_name


def test_same_worker_in_two_runs_gets_different_db_names() -> None:
    assert testrun_resources.test_db_name(
        PREFIX, UID_A, "gw3"
    ) != testrun_resources.test_db_name(PREFIX, UID_B, "gw3")


def test_full_hex_uid_contributes_an_eight_character_segment() -> None:
    worker_db_name = testrun_resources.test_db_name(PREFIX, UID_A, "gw1")
    uid_segment = worker_db_name.removeprefix(f"{PREFIX}_").split("_")[0]

    assert len(UID_A) == 32
    assert uid_segment == UID_A[:8]
    assert len(uid_segment) == 8


@pytest.mark.parametrize("bad_prefix", ["U4I_TEST", "u4i-test", "u4i test", ""])
def test_invalid_prefix_is_rejected_naming_postgres_test_db(bad_prefix: str) -> None:
    with pytest.raises(ValueError, match="POSTGRES_TEST_DB"):
        testrun_resources.test_db_name(bad_prefix, UID_A, "gw0")


def test_name_at_exactly_63_bytes_is_accepted() -> None:
    worker_suffix = "_3fa9c2d1_gw0"
    exact_prefix = "p" * (MAX_IDENTIFIER_BYTES - len(worker_suffix))

    worker_db_name = testrun_resources.test_db_name(exact_prefix, UID_A, "gw0")

    assert len(worker_db_name.encode()) == MAX_IDENTIFIER_BYTES


def test_name_over_63_bytes_is_rejected_naming_postgres_test_db() -> None:
    worker_suffix = "_3fa9c2d1_gw0"
    long_prefix = "p" * (MAX_IDENTIFIER_BYTES - len(worker_suffix) + 1)

    with pytest.raises(ValueError, match="POSTGRES_TEST_DB"):
        testrun_resources.test_db_name(long_prefix, UID_A, "gw0")


@pytest.mark.parametrize(
    "bad_uid", ["zzzzzzzz" + UID_A[8:], "3fa9c2dZ" + UID_A[8:], "3FA9C2D1" + UID_A[8:]]
)
def test_non_hex_uid_is_rejected_naming_postgres_test_db(bad_uid: str) -> None:
    with pytest.raises(ValueError, match="POSTGRES_TEST_DB"):
        testrun_resources.test_db_name(PREFIX, bad_uid, "gw0")


def test_uid_shorter_than_eight_characters_is_rejected() -> None:
    with pytest.raises(ValueError, match="POSTGRES_TEST_DB"):
        testrun_resources.test_db_name(PREFIX, "3fa9", "gw0")


@pytest.mark.parametrize(
    "bad_worker_id",
    ["gw", "GW0", "gw0;x", "", 'gw0"; DROP DATABASE x; --'],
)
def test_invalid_worker_id_is_rejected_in_test_db_name(bad_worker_id: str) -> None:
    with pytest.raises(ValueError, match="gw<N> or master"):
        testrun_resources.test_db_name(PREFIX, UID_A, bad_worker_id)


@pytest.mark.parametrize("dev_like_prefix", ["u4i_dev", "u4i_dev_foo", ""])
def test_prefix_overlapping_dev_prefix_is_rejected(dev_like_prefix: str) -> None:
    with pytest.raises(ValueError, match="POSTGRES_TEST_DB"):
        testrun_resources.test_db_name(dev_like_prefix, UID_A, "gw0")
    with pytest.raises(ValueError, match="POSTGRES_TEST_DB"):
        testrun_resources.test_db_name_regex(dev_like_prefix)


# --- test_db_name_regex -----------------------------------------------------------


@pytest.mark.parametrize(
    "datname",
    ["u4i_test_3fa9c2d1_gw12", "u4i_test_3fa9c2d1_master", "u4i_test_00000000_gw0"],
)
def test_regex_matches_per_run_worker_databases(datname: str) -> None:
    assert testrun_resources.test_db_name_regex(PREFIX).match(datname) is not None


@pytest.mark.parametrize(
    "datname",
    [
        "u4i_test",
        "postgres",
        "template1",
        "u4i_dev_x",
        "u4i_test_3fa9c2d1_gw",
        "u4i_test_3fa9c2d1_gw12_extra",
        "u4i_test_3FA9C2D1_gw0",
        "xu4i_test_3fa9c2d1_gw0",
        "u4i_test_3fa9c2d1_gw0\n",
    ],
)
def test_regex_rejects_non_test_databases(datname: str) -> None:
    assert testrun_resources.test_db_name_regex(PREFIX).match(datname) is None


def test_regex_rejects_prefix_containing_regex_metacharacters() -> None:
    """A prefix with a regex metacharacter fails DB_NAME_PATTERN validation before
    it ever reaches `re.escape`, so it can never leak unescaped into the pattern."""
    with pytest.raises(ValueError, match="POSTGRES_TEST_DB"):
        testrun_resources.test_db_name_regex("u4i.test")


def test_regex_round_trips_generated_names() -> None:
    worker_db_name = testrun_resources.test_db_name(PREFIX, UID_A, "gw7")
    matched = testrun_resources.test_db_name_regex(PREFIX).match(worker_db_name)

    assert matched is not None
    assert matched.groups() == (UID_A[:8], "gw7")


# --- dev_db_name ------------------------------------------------------------------


@pytest.mark.parametrize(
    "slug, expected_name",
    [
        ("My-Worktree.2", "u4i_dev_my_worktree_2"),
        ("urls4irl", "u4i_dev_urls4irl"),
        ("already_ok_9", "u4i_dev_already_ok_9"),
    ],
)
def test_dev_db_name_sanitizes_the_slug(slug: str, expected_name: str) -> None:
    assert dev_db_name(slug) == expected_name


def test_dev_db_name_truncates_to_63_bytes() -> None:
    dev_name = dev_db_name("w" * 200)

    assert len(dev_name.encode()) == MAX_IDENTIFIER_BYTES
    assert dev_name.startswith("u4i_dev_")


def test_dev_db_name_rejects_an_empty_slug() -> None:
    with pytest.raises(ValueError):
        dev_db_name("")


# --- lease keys / owners / pools ---------------------------------------------------


def test_lease_key_and_owner_formats() -> None:
    assert lease_key(SESSION_POOL, 5) == "u4i:test_lease:redis:5"
    assert lease_key(METRICS_POOL, 12) == "u4i:test_lease:metrics:12"
    assert lease_owner(UID_A, "gw2") == f"{UID_A}:gw2"


def test_lease_pool_excludes_reserved_indices() -> None:
    assert lease_pool(16, frozenset({0, 1})) == list(range(2, 16))


def test_lease_pool_with_no_reserved_indices_is_the_full_range() -> None:
    assert lease_pool(4, frozenset()) == [0, 1, 2, 3]


@pytest.mark.parametrize(
    "database_count, reserved",
    [(1, frozenset({0})), (0, frozenset()), (2, frozenset({0, 1}))],
)
def test_lease_pool_raises_when_nothing_is_leasable(
    database_count: int, reserved: frozenset[int]
) -> None:
    with pytest.raises(ValueError):
        lease_pool(database_count, reserved)


@pytest.mark.parametrize(
    "cleanup_pattern",
    [
        "username-change:*",
        "reauth-fail:*",
        "email-change:*",
        "member-add-lookup:*",
        "metrics:counter:*",
        "metrics:batch:*",
    ],
)
@pytest.mark.parametrize("pool", [SESSION_POOL, METRICS_POOL])
def test_lease_keys_never_match_test_cleanup_patterns(
    cleanup_pattern: str, pool: str
) -> None:
    assert not fnmatch.fnmatch(lease_key(pool, 3), cleanup_pattern)


# --- acquire_lease ------------------------------------------------------------------


def test_acquire_lease_takes_the_first_free_index_with_nx_and_ttl() -> None:
    lease_client = _FakeLeaseClient()
    owner = lease_owner(UID_A, "gw0")

    leased_index = acquire_lease(lease_client, SESSION_POOL, [2, 3, 4], owner)

    assert leased_index == 2
    assert lease_client.set_calls == [
        (lease_key(SESSION_POOL, 2), owner, True, LEASE_TTL_SECONDS)
    ]
    assert lease_client.store == {lease_key(SESSION_POOL, 2): owner}


def test_acquire_lease_skips_indices_already_held() -> None:
    other_owner = lease_owner(UID_B, "gw0")
    lease_client = _FakeLeaseClient(
        preheld_keys={
            lease_key(METRICS_POOL, 1): other_owner,
            lease_key(METRICS_POOL, 2): other_owner,
        }
    )
    owner = lease_owner(UID_A, "master")

    leased_index = acquire_lease(
        lease_client, METRICS_POOL, [1, 2, 3], owner, ttl_seconds=60
    )

    assert leased_index == 3
    assert [set_call[0] for set_call in lease_client.set_calls] == [
        lease_key(METRICS_POOL, 1),
        lease_key(METRICS_POOL, 2),
        lease_key(METRICS_POOL, 3),
    ]
    assert lease_client.set_calls[-1][3] == 60
    assert lease_client.store[lease_key(METRICS_POOL, 1)] == other_owner


def test_two_workers_never_share_a_leased_index() -> None:
    lease_client = _FakeLeaseClient()
    candidates = [2, 3, 4]

    first_index = acquire_lease(
        lease_client, SESSION_POOL, candidates, lease_owner(UID_A, "gw0")
    )
    second_index = acquire_lease(
        lease_client, SESSION_POOL, candidates, lease_owner(UID_B, "gw0")
    )

    assert first_index != second_index


def test_acquire_lease_raises_with_corrective_text_when_pool_is_exhausted() -> None:
    other_owner = lease_owner(UID_B, "gw0")
    lease_client = _FakeLeaseClient(
        preheld_keys={lease_key(SESSION_POOL, index): other_owner for index in (2, 3)}
    )

    with pytest.raises(RuntimeError) as exhausted:
        acquire_lease(lease_client, SESSION_POOL, [2, 3], lease_owner(UID_A, "gw0"))

    message = str(exhausted.value)
    assert SESSION_POOL in message
    assert "all 2 candidate" in message
    assert "make reset-test-dbs" in message
    assert "lower n" in message
    assert "make capacity" in message


def test_acquire_lease_with_no_candidates_raises() -> None:
    with pytest.raises(RuntimeError, match="make reset-test-dbs"):
        acquire_lease(_FakeLeaseClient(), METRICS_POOL, [], lease_owner(UID_A, "gw0"))


# --- release_lease --------------------------------------------------------------


def test_release_lease_script_is_compare_and_delete() -> None:
    assert "redis.call('get', KEYS[1]) == ARGV[1]" in RELEASE_SCRIPT
    assert "redis.call('del', KEYS[1])" in RELEASE_SCRIPT


def test_release_by_owner_deletes_and_repeat_release_is_idempotent() -> None:
    lease_client = _FakeLeaseClient()
    owner = lease_owner(UID_A, "gw1")
    leased_index = acquire_lease(lease_client, SESSION_POOL, [5], owner)

    first_release = release_lease(lease_client, SESSION_POOL, leased_index, owner)
    second_release = release_lease(lease_client, SESSION_POOL, leased_index, owner)

    assert first_release
    assert not second_release
    assert lease_client.store == {}
    assert lease_client.eval_calls[0] == (
        RELEASE_SCRIPT,
        1,
        lease_key(SESSION_POOL, leased_index),
        owner,
    )


def test_release_with_wrong_owner_returns_false_and_keeps_the_lease() -> None:
    lease_client = _FakeLeaseClient()
    owner = lease_owner(UID_A, "gw1")
    leased_index = acquire_lease(lease_client, METRICS_POOL, [4], owner)

    released = release_lease(
        lease_client, METRICS_POOL, leased_index, lease_owner(UID_B, "gw1")
    )

    assert released is False
    assert lease_client.store == {lease_key(METRICS_POOL, leased_index): owner}


# --- worker_index / port_probe_start -----------------------------------------------


@pytest.mark.parametrize(
    "worker_id, expected_index", [("master", 0), ("gw0", 0), ("gw1", 1), ("gw15", 15)]
)
def test_worker_index(worker_id: str, expected_index: int) -> None:
    assert worker_index(worker_id) == expected_index


@pytest.mark.parametrize("bad_worker_id", ["gw", "gw-1", " 3", "gw+2", "GW0", ""])
def test_worker_index_rejects_invalid_worker_ids(bad_worker_id: str) -> None:
    with pytest.raises(ValueError, match="gw<N> or master"):
        worker_index(bad_worker_id)


def test_port_probe_start_rejects_non_hex_uid_naming_postgres_test_db() -> None:
    with pytest.raises(ValueError, match="POSTGRES_TEST_DB"):
        port_probe_start("zzzz" + UID_A[4:], 0)


def test_port_probe_start_formula() -> None:
    expected_offset = int(UID_A[:4], 16) % 500

    assert port_probe_start(UID_A, 0) == 10000 + expected_offset
    assert port_probe_start(UID_A, 3) == 13000 + expected_offset


def test_port_probe_start_decorrelates_two_runs_for_the_same_worker() -> None:
    assert port_probe_start(UID_A, 0) != port_probe_start(UID_B, 0)


@pytest.mark.parametrize("worker_number", [0, 1, 11])
def test_port_probe_start_stays_inside_the_worker_band(worker_number: int) -> None:
    band_start = 10000 + worker_number * 1000

    assert band_start <= port_probe_start(UID_A, worker_number) < band_start + 500
