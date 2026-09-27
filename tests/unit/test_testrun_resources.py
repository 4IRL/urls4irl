"""Unit tests for per-run test-resource naming and leasing (`scripts/testrun_resources.py`).

No Postgres or Redis is touched: lease operations run against `_FakeLeaseClient`,
an in-memory stand-in that honors `SET NX EX` and the compare-and-delete script.
`test_db_name` / `test_db_name_regex` are reached through the module rather than
imported by name, so pytest never collects them as tests of this file.
"""

from __future__ import annotations

import fnmatch

import pytest
from sqlalchemy.exc import DBAPIError
from sqlalchemy.sql.elements import TextClause

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
    confirm_stale,
    dev_db_name,
    drop_idle_databases,
    lease_db_uri,
    lease_key,
    lease_owner,
    lease_pool,
    live_test_run_uid8s,
    main,
    parse_created_epoch,
    port_probe_start,
    release_lease,
    release_orphan_leases,
    scan_leases,
    select_orphan_leases,
    select_stale_test_dbs,
    split_redis_uri,
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


# --- reaper: parse_created_epoch ---------------------------------------------------

NOW_EPOCH: int = 1_800_000_000
TEN_MINUTES: int = 10 * 60


def _epoch_comment(created_epoch: int) -> str:
    return f"u4i-test created_epoch={created_epoch}"


def test_parse_created_epoch_reads_the_fixture_comment() -> None:
    assert parse_created_epoch(_epoch_comment(NOW_EPOCH)) == NOW_EPOCH


@pytest.mark.parametrize(
    "comment",
    [
        None,
        "",
        "u4i-test created_epoch=",
        "u4i-test created_epoch=abc",
        "u4i-test created_epoch=-5",
        "u4i-test created_epoch=12 extra",
        "created_epoch=12",
        "someone else's comment",
    ],
)
def test_parse_created_epoch_returns_none_for_anything_else(
    comment: str | None,
) -> None:
    assert parse_created_epoch(comment) is None


# --- reaper: select_stale_test_dbs -------------------------------------------------


def _worker_db(worker_id: str = "gw0", testrun_uid: str = UID_A) -> str:
    return testrun_resources.test_db_name(PREFIX, testrun_uid, worker_id)


def _select(
    rows: list[tuple[str, str | None, int]], ttl_seconds: int = TEN_MINUTES
) -> list[str]:
    return select_stale_test_dbs(rows, PREFIX, NOW_EPOCH, ttl_seconds)


def test_idle_database_older_than_the_ttl_is_selected() -> None:
    stale_name = _worker_db()

    assert _select([(stale_name, _epoch_comment(NOW_EPOCH - TEN_MINUTES - 1), 0)]) == [
        stale_name
    ]


def test_idle_database_exactly_at_the_ttl_is_selected() -> None:
    stale_name = _worker_db()

    assert _select([(stale_name, _epoch_comment(NOW_EPOCH - TEN_MINUTES), 0)]) == [
        stale_name
    ]


def test_idle_database_younger_than_the_ttl_is_kept() -> None:
    young_name = _worker_db()

    assert _select([(young_name, _epoch_comment(NOW_EPOCH - TEN_MINUTES + 1), 0)]) == []


@pytest.mark.parametrize("comment", [None, "", "not a u4i comment"])
def test_idle_database_without_a_parseable_epoch_is_selected(
    comment: str | None,
) -> None:
    unaged_name = _worker_db("master")

    assert _select([(unaged_name, comment, 0)]) == [unaged_name]


@pytest.mark.parametrize(
    "comment", [None, _epoch_comment(0), _epoch_comment(NOW_EPOCH)]
)
@pytest.mark.parametrize("active_connections", [1, 7])
def test_connected_database_is_never_selected_whatever_its_age(
    comment: str | None, active_connections: int
) -> None:
    assert _select([(_worker_db(), comment, active_connections)], ttl_seconds=0) == []


def test_ttl_zero_selects_every_idle_test_database() -> None:
    fresh_name = _worker_db()

    assert _select([(fresh_name, _epoch_comment(NOW_EPOCH), 0)], ttl_seconds=0) == [
        fresh_name
    ]


@pytest.mark.parametrize(
    "datname",
    [
        PREFIX,
        "postgres",
        "template0",
        "template1",
        "u4i_dev_urls4irl",
        f"u4i_dev_{UID_A[:8]}_gw0",
        f"other_prefix_{UID_A[:8]}_gw0",
        f"{PREFIX}_{UID_A[:8]}_gw0_extra",
        f"{PREFIX}_{UID_A[:8].upper()}_gw0",
    ],
)
def test_non_test_databases_are_never_selected(datname: str) -> None:
    assert _select([(datname, None, 0)], ttl_seconds=0) == []


def test_selection_keeps_row_order_and_filters_a_mixed_listing() -> None:
    stale_gw0 = _worker_db("gw0")
    connected_gw1 = _worker_db("gw1")
    young_gw2 = _worker_db("gw2")
    unaged_master = _worker_db("master", UID_B)
    rows: list[tuple[str, str | None, int]] = [
        ("postgres", None, 3),
        (stale_gw0, _epoch_comment(0), 0),
        (connected_gw1, _epoch_comment(0), 2),
        (young_gw2, _epoch_comment(NOW_EPOCH), 0),
        ("u4i_dev_urls4irl", None, 0),
        (unaged_master, None, 0),
    ]

    assert _select(rows) == [stale_gw0, unaged_master]


def test_select_stale_rejects_a_dev_overlapping_prefix() -> None:
    with pytest.raises(ValueError, match="POSTGRES_TEST_DB"):
        select_stale_test_dbs([], "u4i_dev", NOW_EPOCH, TEN_MINUTES)


# --- reaper: confirm_stale ---------------------------------------------------------


def test_confirm_stale_keeps_only_names_stale_in_both_passes_in_second_order() -> None:
    gw0_name = _worker_db("gw0")
    gw1_name = _worker_db("gw1")
    gw2_name = _worker_db("gw2")
    master_name = _worker_db("master")

    assert confirm_stale(
        [gw0_name, gw1_name, gw2_name], [gw2_name, master_name, gw0_name]
    ) == [gw2_name, gw0_name]


def test_confirm_stale_drops_a_db_stamped_between_the_two_listings() -> None:
    """A fresh DB caught before its COMMENT is stale only in the first pass."""
    unstamped_name = _worker_db("gw3")
    first_pass = _select([(unstamped_name, None, 0)])
    second_pass = _select([(unstamped_name, _epoch_comment(NOW_EPOCH), 0)])

    assert first_pass == [unstamped_name]
    assert confirm_stale(first_pass, second_pass) == []


@pytest.mark.parametrize(
    "first_pass, second_pass", [([], []), ([_worker_db()], []), ([], [_worker_db()])]
)
def test_confirm_stale_returns_nothing_when_either_pass_is_empty(
    first_pass: list[str], second_pass: list[str]
) -> None:
    assert confirm_stale(first_pass, second_pass) == []


# --- reaper: select_orphan_leases --------------------------------------------------


def test_lease_whose_run_has_no_database_is_an_orphan() -> None:
    orphan_key = lease_key(SESSION_POOL, 3)

    assert select_orphan_leases(
        [(orphan_key, lease_owner(UID_B, "gw0"))], {UID_A[:8]}
    ) == [orphan_key]


def test_lease_whose_run_still_has_a_database_is_kept() -> None:
    live_items = [
        (lease_key(SESSION_POOL, 2), lease_owner(UID_A, "gw0")),
        (lease_key(METRICS_POOL, 1), lease_owner(UID_A, "master")),
    ]

    assert select_orphan_leases(live_items, {UID_A[:8]}) == []


def test_every_lease_is_an_orphan_when_no_test_database_remains() -> None:
    lease_items = [
        (lease_key(SESSION_POOL, 2), lease_owner(UID_A, "gw0")),
        (lease_key(METRICS_POOL, 1), lease_owner(UID_B, "gw3")),
    ]

    assert select_orphan_leases(lease_items, set()) == [
        lease_key(SESSION_POOL, 2),
        lease_key(METRICS_POOL, 1),
    ]


@pytest.mark.parametrize("malformed_owner", ["", "short", "ZZZZZZZZ:gw0"])
def test_lease_with_a_malformed_owner_is_an_orphan(malformed_owner: str) -> None:
    orphan_key = lease_key(SESSION_POOL, 4)

    assert select_orphan_leases([(orphan_key, malformed_owner)], {UID_A[:8]}) == [
        orphan_key
    ]


@pytest.mark.parametrize(
    "foreign_key",
    [
        "session:abc",
        "username-change:1",
        "u4i:test_leasex:redis:1",
        "u4i:test_lease",
        "metrics:counter:x",
    ],
)
def test_keys_outside_the_lease_namespace_are_never_selected(foreign_key: str) -> None:
    assert select_orphan_leases([(foreign_key, lease_owner(UID_B, "gw0"))], set()) == []


# --- reaper: helpers ---------------------------------------------------------------


def test_live_uid8s_are_read_from_test_database_names_only() -> None:
    datnames = [
        _worker_db("gw0", UID_A),
        _worker_db("gw1", UID_A),
        _worker_db("master", UID_B),
        "postgres",
        PREFIX,
        "u4i_dev_urls4irl",
    ]

    assert live_test_run_uid8s(datnames, PREFIX) == {UID_A[:8], UID_B[:8]}


@pytest.mark.parametrize(
    "redis_uri, expected_uri",
    [
        ("redis://redis:6379/1", "redis://redis:6379/0"),
        ("redis://localhost:6379/12", "redis://localhost:6379/0"),
        ("rediss://host:6380/3", "rediss://host:6380/0"),
        ("memory://", None),
        ("", None),
    ],
)
def test_lease_db_uri_points_at_db_zero(
    redis_uri: str, expected_uri: str | None
) -> None:
    assert lease_db_uri(redis_uri) == expected_uri


@pytest.mark.parametrize(
    "bad_uri", ["redis://redis:6379", "redis://redis:6379/1?x=1", "redis://redis:6379/"]
)
def test_lease_db_uri_rejects_uris_without_a_db_index(bad_uri: str) -> None:
    with pytest.raises(ValueError, match="TEST_REDIS_URI"):
        lease_db_uri(bad_uri)


@pytest.mark.parametrize(
    "redis_uri, expected_split",
    [
        ("redis://redis:6379/1", ("redis://redis:6379", 1)),
        ("redis://localhost:6379/12", ("redis://localhost:6379", 12)),
        ("rediss://host:6380/3", ("rediss://host:6380", 3)),
        ("redis://redis-metrics:6379/0", ("redis://redis-metrics:6379", 0)),
    ],
)
def test_split_redis_uri_returns_the_base_uri_and_db_index(
    redis_uri: str, expected_split: tuple[str, int]
) -> None:
    assert split_redis_uri(redis_uri, "TEST_REDIS_URI") == expected_split


@pytest.mark.parametrize(
    "bad_uri",
    ["redis://redis:6379", "redis://redis:6379/1?x=1", "redis://redis:6379/1\n", ""],
)
def test_split_redis_uri_rejects_uris_without_a_trailing_db_index_naming_the_env(
    bad_uri: str,
) -> None:
    with pytest.raises(ValueError, match="TEST_METRICS_REDIS_URI"):
        split_redis_uri(bad_uri, "TEST_METRICS_REDIS_URI")


class _FakePgError(Exception):
    def __init__(self, pgcode: str) -> None:
        super().__init__(pgcode)
        self.pgcode = pgcode


class _FakeDropConnection:
    """Records DROP statements; raises a DBAPIError carrying `pgcode` for chosen DBs."""

    def __init__(self, failing_pgcodes: dict[str, str] | None = None) -> None:
        self.failing_pgcodes: dict[str, str] = failing_pgcodes or {}
        self.statements: list[str] = []

    def execute(self, statement: TextClause) -> None:
        sql = str(statement)
        self.statements.append(sql)
        for datname, pgcode in self.failing_pgcodes.items():
            if f'"{datname}"' in sql:
                raise DBAPIError(sql, None, _FakePgError(pgcode))


def test_drop_idle_databases_drops_without_force() -> None:
    fake_connection = _FakeDropConnection()
    stale_names = [_worker_db("gw0"), _worker_db("gw1")]

    assert drop_idle_databases(fake_connection, stale_names) == (stale_names, [])
    assert fake_connection.statements == [
        f'DROP DATABASE IF EXISTS "{datname}"' for datname in stale_names
    ]


@pytest.mark.parametrize("skippable_pgcode", ["55006", "42501"])
def test_drop_idle_databases_skips_in_use_or_unowned_databases(
    skippable_pgcode: str,
) -> None:
    busy_name = _worker_db("gw0")
    idle_name = _worker_db("gw1")
    fake_connection = _FakeDropConnection({busy_name: skippable_pgcode})

    assert drop_idle_databases(fake_connection, [busy_name, idle_name]) == (
        [idle_name],
        [busy_name],
    )


def test_drop_idle_databases_reraises_unexpected_errors() -> None:
    broken_name = _worker_db("gw0")
    fake_connection = _FakeDropConnection({broken_name: "08006"})

    with pytest.raises(DBAPIError):
        drop_idle_databases(fake_connection, [broken_name])


def test_drop_idle_databases_refuses_names_that_need_quoting() -> None:
    fake_connection = _FakeDropConnection()

    with pytest.raises(ValueError, match="Refusing to drop"):
        drop_idle_databases(fake_connection, ['evil"; DROP DATABASE "u4i_dev_x'])
    assert fake_connection.statements == []


class _FakeScanLeaseClient(_FakeLeaseClient):
    """Adds the `SCAN MATCH` + `GET` the reaper uses, over the same in-memory store."""

    def __init__(self, preheld_keys: dict[str, str]) -> None:
        super().__init__(preheld_keys)
        self.scan_patterns: list[str] = []

    def scan_iter(self, match: str, count: int) -> list[str]:
        self.scan_patterns.append(match)
        return [key for key in self.store if fnmatch.fnmatchcase(key, match)]

    def get(self, name: str) -> str | None:
        return self.store.get(name)


def test_scan_leases_reads_only_lease_pattern_keys() -> None:
    session_key = lease_key(SESSION_POOL, 2)
    metrics_key = lease_key(METRICS_POOL, 1)
    fake_client = _FakeScanLeaseClient(
        {
            session_key: lease_owner(UID_B, "gw0"),
            metrics_key: lease_owner(UID_A, "gw0"),
            "username-change:7": lease_owner(UID_B, "gw0"),
            "session:abc": "payload",
        }
    )

    assert scan_leases(fake_client) == {
        session_key: lease_owner(UID_B, "gw0"),
        metrics_key: lease_owner(UID_A, "gw0"),
    }
    assert fake_client.scan_patterns == [f"{LEASE_KEY_PREFIX}:*"]
    assert fake_client.eval_calls == []


def test_scan_leases_skips_a_key_that_vanishes_before_its_get() -> None:
    class _VanishingClient(_FakeScanLeaseClient):
        """The lease expires between the SCAN and the GET."""

        def get(self, name: str) -> str | None:
            self.store.pop(name, None)
            return super().get(name)

    fake_client = _VanishingClient(
        {lease_key(SESSION_POOL, 3): lease_owner(UID_B, "gw0")}
    )

    assert scan_leases(fake_client) == {}


def test_release_orphan_leases_deletes_only_orphaned_lease_keys() -> None:
    orphan_key = lease_key(SESSION_POOL, 2)
    live_key = lease_key(METRICS_POOL, 1)
    lease_owners = {
        orphan_key: lease_owner(UID_B, "gw0"),
        live_key: lease_owner(UID_A, "gw0"),
    }
    fake_client = _FakeScanLeaseClient({**lease_owners, "session:abc": "payload"})

    assert release_orphan_leases(fake_client, lease_owners, {UID_A[:8]}) == [orphan_key]
    assert fake_client.eval_calls == [
        (RELEASE_SCRIPT, 1, orphan_key, lease_owner(UID_B, "gw0"))
    ]
    assert set(fake_client.store) == {live_key, "session:abc"}


def test_release_orphan_leases_keeps_a_lease_reacquired_before_the_delete() -> None:
    contested_key = lease_key(SESSION_POOL, 5)
    scanned_owners = {contested_key: lease_owner(UID_B, "gw0")}
    # A different owner re-acquired the lease after the scan read it.
    fake_client = _FakeScanLeaseClient({contested_key: lease_owner(UID_A, "gw4")})

    assert release_orphan_leases(fake_client, scanned_owners, set()) == []
    assert fake_client.store == {contested_key: lease_owner(UID_A, "gw4")}


# --- reaper: CLI parsing -----------------------------------------------------------


@pytest.mark.parametrize(
    "bad_argv",
    [[], ["reap", "--ttl-minutes", "-1"], ["reap", "--ttl-minutes", "ten"], ["drop"]],
)
def test_main_rejects_invalid_arguments_before_touching_anything(
    bad_argv: list[str],
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(bad_argv)

    assert exit_info.value.code == 2


def test_main_refuses_to_run_without_postgres_test_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard runs before any engine or Redis client is created."""

    def _fail_on_connect(*args: object, **kwargs: object) -> None:
        raise AssertionError("main must not connect without POSTGRES_TEST_DB")

    monkeypatch.setattr(testrun_resources, "POSTGRES_TEST_DB", "")
    monkeypatch.setattr(testrun_resources, "create_engine", _fail_on_connect)
    monkeypatch.setattr(testrun_resources.Redis, "from_url", _fail_on_connect)

    with pytest.raises(SystemExit, match="POSTGRES_TEST_DB"):
        main(["reap"])
