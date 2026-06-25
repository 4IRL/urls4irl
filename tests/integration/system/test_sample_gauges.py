from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock

import pytest
from flask import Flask
from redis import Redis

from backend.metrics.gauges import GaugeName
from scripts.sample_gauges import (
    GAUGE_FAILURE_FLAG_KEY,
    run_sample,
    run_sample_job,
)
from tests.integration.system.metrics_helpers import (
    build_pg_conn,
    truncate_gauges_tables,
)

pytestmark = pytest.mark.cli


_SEED_PASSWORD = "hashed-placeholder"
_SEED_TIMESTAMP = "2025-01-01 00:00:00+00"


def _truncate_all(pg_conn: Any) -> None:
    """Reset every relational table the gauges sample plus AnonymousGauges.

    TRUNCATE ... CASCADE on the parent tables clears the child association
    tables (UtubUrls, UtubMembers, UtubTags, UtubUrlTags) via their foreign
    keys, so the gauge population is deterministic for every test.
    """
    with pg_conn.cursor() as cursor:
        cursor.execute(
            'TRUNCATE TABLE "Users", "Utubs", "Urls" RESTART IDENTITY CASCADE'
        )
    pg_conn.commit()
    truncate_gauges_tables(pg_conn)


def _seed_user(pg_conn: Any, username: str) -> int:
    with pg_conn.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "Users" '
            '(username, email, password, "createdAt", role, "emailValidated") '
            "VALUES (%s, %s, %s, %s, 'USER', true) RETURNING id",
            (username, f"{username}@example.com", _SEED_PASSWORD, _SEED_TIMESTAMP),
        )
        user_id = cursor.fetchone()[0]
    pg_conn.commit()
    return user_id


def _seed_utub(pg_conn: Any, name: str, creator_id: int) -> int:
    with pg_conn.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "Utubs" '
            '("utubName", "utubCreator", "createdAt", "lastUpdated") '
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (name, creator_id, _SEED_TIMESTAMP, _SEED_TIMESTAMP),
        )
        utub_id = cursor.fetchone()[0]
    pg_conn.commit()
    return utub_id


def _seed_url(pg_conn: Any, url_string: str, creator_id: int) -> int:
    with pg_conn.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "Urls" ("urlString", "createdBy", "createdAt") '
            "VALUES (%s, %s, %s) RETURNING id",
            (url_string, creator_id, _SEED_TIMESTAMP),
        )
        url_id = cursor.fetchone()[0]
    pg_conn.commit()
    return url_id


def _seed_utub_url(pg_conn: Any, utub_id: int, url_id: int, user_id: int) -> None:
    with pg_conn.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "UtubUrls" '
            '("utubID", "urlID", "userID", "urlTitle", "addedAt", "lastAccessed") '
            "VALUES (%s, %s, %s, '', %s, %s)",
            (utub_id, url_id, user_id, _SEED_TIMESTAMP, _SEED_TIMESTAMP),
        )
    pg_conn.commit()


def _count_gauge_rows(pg_conn: Any) -> int:
    with pg_conn.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) FROM "AnonymousGauges"')
        return cursor.fetchone()[0]


def _gauge_value(pg_conn: Any, gauge: GaugeName) -> tuple[Any, Any]:
    """Return (valueInt, valueFloat) for the single row of one gauge."""
    with pg_conn.cursor() as cursor:
        cursor.execute(
            'SELECT "valueInt", "valueFloat" FROM "AnonymousGauges" '
            'WHERE "gaugeName" = %s',
            (gauge.value,),
        )
        rows = cursor.fetchall()
    assert len(rows) == 1, f"expected exactly one row for {gauge.value}, got {rows}"
    return rows[0]


def test_run_sample_writes_one_row_per_gauge(metrics_enabled_runner_app: Flask):
    """
    GIVEN an empty AnonymousGauges table and a minimal relational fixture
    WHEN run_sample is invoked once
    THEN exactly one row is written per GaugeName member and every gauge value
        appears exactly once.
    """
    app = metrics_enabled_runner_app
    pg_conn = build_pg_conn(app)
    try:
        _truncate_all(pg_conn)
        assert _count_gauge_rows(pg_conn) == 0
        creator_id = _seed_user(pg_conn, "creator")
        _seed_utub(pg_conn, "utub-a", creator_id)

        inserted = run_sample(pg_conn=pg_conn, now_epoch=int(time.time()))

        assert inserted == len(GaugeName)
        assert _count_gauge_rows(pg_conn) == len(GaugeName)
        with pg_conn.cursor() as cursor:
            cursor.execute('SELECT "gaugeName" FROM "AnonymousGauges"')
            seen = [row[0] for row in cursor.fetchall()]
        assert sorted(seen) == sorted(member.value for member in GaugeName)
    finally:
        _truncate_all(pg_conn)
        pg_conn.close()


def test_volume_gauges_match_seeded_counts(metrics_enabled_runner_app: Flask):
    """
    GIVEN N seeded users and M seeded UTubs
    WHEN run_sample is invoked
    THEN total_users == N and total_utubs == M (hand-computed expectations).
    """
    app = metrics_enabled_runner_app
    pg_conn = build_pg_conn(app)
    try:
        _truncate_all(pg_conn)
        assert _count_gauge_rows(pg_conn) == 0
        expected_users = 4
        expected_utubs = 3
        user_ids = [_seed_user(pg_conn, f"user{idx}") for idx in range(expected_users)]
        for utub_index in range(expected_utubs):
            _seed_utub(pg_conn, f"utub{utub_index}", user_ids[0])

        run_sample(pg_conn=pg_conn, now_epoch=int(time.time()))

        assert _gauge_value(pg_conn, GaugeName.TOTAL_USERS)[0] == expected_users
        assert _gauge_value(pg_conn, GaugeName.TOTAL_UTUBS)[0] == expected_utubs
    finally:
        _truncate_all(pg_conn)
        pg_conn.close()


def test_distribution_max_and_avg(metrics_enabled_runner_app: Flask):
    """
    GIVEN >= MIN_GAUGE_POPULATION UTubs with known URL counts (2, 4, 6, 4, 4)
    WHEN run_sample is invoked
    THEN max_urls_per_utub == 6 and avg_urls_per_utub == 4.0 (hand-computed:
        (2+4+6+4+4)/5 == 4.0).
    """
    app = metrics_enabled_runner_app
    pg_conn = build_pg_conn(app)
    try:
        _truncate_all(pg_conn)
        assert _count_gauge_rows(pg_conn) == 0
        creator_id = _seed_user(pg_conn, "creator")
        url_counts = [2, 4, 6, 4, 4]
        url_serial = 0
        for utub_index, count in enumerate(url_counts):
            utub_id = _seed_utub(pg_conn, f"utub{utub_index}", creator_id)
            for _ in range(count):
                url_id = _seed_url(pg_conn, f"https://e.com/{url_serial}", creator_id)
                _seed_utub_url(pg_conn, utub_id, url_id, creator_id)
                url_serial += 1

        run_sample(pg_conn=pg_conn, now_epoch=int(time.time()))

        assert _gauge_value(pg_conn, GaugeName.MAX_URLS_PER_UTUB)[0] == 6
        assert float(_gauge_value(pg_conn, GaugeName.AVG_URLS_PER_UTUB)[1]) == 4.0
    finally:
        _truncate_all(pg_conn)
        pg_conn.close()


def test_distribution_max_k_anonymity_below_threshold(
    metrics_enabled_runner_app: Flask,
):
    """
    GIVEN fewer than MIN_GAUGE_POPULATION distinct UTubs with URLs
    WHEN run_sample is invoked
    THEN max_urls_per_utub is suppressed (valueInt IS NULL) while
        avg_urls_per_utub is non-null — averages are unaffected by k-anonymity.
    """
    app = metrics_enabled_runner_app
    pg_conn = build_pg_conn(app)
    try:
        _truncate_all(pg_conn)
        assert _count_gauge_rows(pg_conn) == 0
        creator_id = _seed_user(pg_conn, "creator")
        url_serial = 0
        for utub_index in range(3):
            utub_id = _seed_utub(pg_conn, f"utub{utub_index}", creator_id)
            for _ in range(2):
                url_id = _seed_url(pg_conn, f"https://e.com/{url_serial}", creator_id)
                _seed_utub_url(pg_conn, utub_id, url_id, creator_id)
                url_serial += 1

        run_sample(pg_conn=pg_conn, now_epoch=int(time.time()))

        assert _gauge_value(pg_conn, GaugeName.MAX_URLS_PER_UTUB)[0] is None
        assert _gauge_value(pg_conn, GaugeName.AVG_URLS_PER_UTUB)[1] is not None
    finally:
        _truncate_all(pg_conn)
        pg_conn.close()


def test_relational_max_utubs_per_url_and_urls_per_user(
    metrics_enabled_runner_app: Flask,
):
    """
    GIVEN UtubUrls seeded so the most-shared URL appears in a known number of
        UTubs and the most-prolific member adds a known number of associations,
        across >= MIN_GAUGE_POPULATION distinct urlID and userID values
    WHEN run_sample is invoked
    THEN max_utubs_per_url and max_urls_per_user equal the hand-computed maxima.
    """
    app = metrics_enabled_runner_app
    pg_conn = build_pg_conn(app)
    try:
        _truncate_all(pg_conn)
        assert _count_gauge_rows(pg_conn) == 0

        # Six distinct users (each creates its own UTub) and six distinct URLs,
        # so both group populations (urlID, userID) exceed MIN_GAUGE_POPULATION.
        user_ids = [_seed_user(pg_conn, f"user{idx}") for idx in range(6)]
        utub_ids = [
            _seed_utub(pg_conn, f"utub{idx}", user_ids[idx]) for idx in range(6)
        ]
        url_ids = [
            _seed_url(pg_conn, f"https://e.com/{idx}", user_ids[idx])
            for idx in range(6)
        ]

        # url_ids[0] is shared across 4 distinct UTubs -> max_utubs_per_url == 4.
        for utub_index in range(4):
            _seed_utub_url(
                pg_conn, utub_ids[utub_index], url_ids[0], user_ids[utub_index]
            )
        # Give every other url at least one association so the population of
        # distinct urlID values is >= 5 (urls 0..5 all appear).
        for url_index in range(1, 6):
            _seed_utub_url(
                pg_conn, utub_ids[url_index], url_ids[url_index], user_ids[url_index]
            )

        # user_ids[0] adds 5 URL associations across its own UTub -> the most
        # prolific contributor. Distinct userID values present: 0..5 (>= 5).
        for url_index in range(1, 6):
            _seed_utub_url(pg_conn, utub_ids[0], url_ids[url_index], user_ids[0])

        run_sample(pg_conn=pg_conn, now_epoch=int(time.time()))

        # url_ids[0]: appears in utubs 0,1,2,3 (the k-anon loop) == 4 UTubs.
        assert _gauge_value(pg_conn, GaugeName.MAX_UTUBS_PER_URL)[0] == 4
        # user_ids[0] associations: url0->utub0, plus url1..5 -> utub0 == 6.
        assert _gauge_value(pg_conn, GaugeName.MAX_URLS_PER_USER)[0] == 6
    finally:
        _truncate_all(pg_conn)
        pg_conn.close()


def test_relational_max_below_threshold_is_suppressed(
    metrics_enabled_runner_app: Flask,
):
    """
    GIVEN fewer than MIN_GAUGE_POPULATION distinct urlID and userID values in
        UtubUrls
    WHEN run_sample is invoked
    THEN both max_utubs_per_url and max_urls_per_user are suppressed
        (valueInt IS NULL).
    """
    app = metrics_enabled_runner_app
    pg_conn = build_pg_conn(app)
    try:
        _truncate_all(pg_conn)
        assert _count_gauge_rows(pg_conn) == 0

        creator_id = _seed_user(pg_conn, "creator")
        # Only three distinct UTubs / URLs / contributing user (one) -> both the
        # urlID and userID populations are below MIN_GAUGE_POPULATION.
        for index in range(3):
            utub_id = _seed_utub(pg_conn, f"utub{index}", creator_id)
            url_id = _seed_url(pg_conn, f"https://e.com/{index}", creator_id)
            _seed_utub_url(pg_conn, utub_id, url_id, creator_id)

        run_sample(pg_conn=pg_conn, now_epoch=int(time.time()))

        assert _gauge_value(pg_conn, GaugeName.MAX_UTUBS_PER_URL)[0] is None
        assert _gauge_value(pg_conn, GaugeName.MAX_URLS_PER_USER)[0] is None
    finally:
        _truncate_all(pg_conn)
        pg_conn.close()


def test_run_sample_job_sets_failure_flag_then_clears_on_recovery(
    metrics_enabled_runner_app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a real metrics Redis and run_sample_job driven first with a forced
        failure (a deliberately-closed pg_conn) and then with a healthy run
    WHEN run_sample_job is invoked across the failure -> recovery transition
    THEN GAUGE_FAILURE_FLAG_KEY is absent before the failure, set after the
        failure (which re-raises), and cleared after the subsequent success —
        proving the transition-throttle flag is round-tripped against real
        Redis, not just a MagicMock.
    """
    app = metrics_enabled_runner_app
    spy_notifier = MagicMock(return_value=0)

    # Before-state: the flag must be absent so the assertions measure this run.
    provide_metrics_redis.delete(GAUGE_FAILURE_FLAG_KEY)
    assert provide_metrics_redis.get(GAUGE_FAILURE_FLAG_KEY) is None

    try:
        # Forced failure: a closed connection makes run_sample raise (psycopg2
        # raises InterfaceError on a closed connection).
        closed_pg_conn = build_pg_conn(app)
        closed_pg_conn.close()
        with pytest.raises(Exception):
            run_sample_job(
                pg_conn=closed_pg_conn,
                redis_client=provide_metrics_redis,
                now_epoch=int(time.time()),
                notifier=spy_notifier,
            )
        assert provide_metrics_redis.get(GAUGE_FAILURE_FLAG_KEY) is not None

        # Recovery: a healthy sample over a clean table clears the flag.
        healthy_pg_conn = build_pg_conn(app)
        try:
            _truncate_all(healthy_pg_conn)
            run_sample_job(
                pg_conn=healthy_pg_conn,
                redis_client=provide_metrics_redis,
                now_epoch=int(time.time()),
                notifier=spy_notifier,
            )
            assert provide_metrics_redis.get(GAUGE_FAILURE_FLAG_KEY) is None
        finally:
            _truncate_all(healthy_pg_conn)
            healthy_pg_conn.close()
    finally:
        provide_metrics_redis.delete(GAUGE_FAILURE_FLAG_KEY)
