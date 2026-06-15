from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from flask import Flask

from backend.metrics.gauges import (
    GAUGE_REGISTRY,
    GaugeName,
)
from backend.metrics.query_service import (
    gauge_timeseries_one,
    gauges_timeseries_all,
    latest_gauge_snapshot,
    list_gauges,
)
from tests.integration.system.metrics_helpers import (
    build_pg_conn,
    truncate_gauges_tables,
)

pytestmark = pytest.mark.cli


_INSERT_GAUGE_SQL = (
    'INSERT INTO "AnonymousGauges" '
    '("gaugeName", "sampledAt", "valueInt", "valueFloat", "dimensions") '
    "VALUES (%s, %s, %s, %s, '{}'::jsonb)"
)


def _seed_gauge_row(
    pg_conn: Any,
    *,
    gauge_name: str,
    sampled_at: datetime,
    value_int: int | None = None,
    value_float: float | None = None,
) -> None:
    with pg_conn.cursor() as cursor:
        cursor.execute(
            _INSERT_GAUGE_SQL,
            (gauge_name, sampled_at, value_int, value_float),
        )
    pg_conn.commit()


def _count_gauge_rows(pg_conn: Any) -> int:
    with pg_conn.cursor() as cursor:
        cursor.execute('SELECT COUNT(*) FROM "AnonymousGauges"')
        return cursor.fetchone()[0]


def _bucket_inside_window() -> datetime:
    """A UTC-aware sample timestamp comfortably inside a 1-day lookback."""
    return datetime.now(timezone.utc) - timedelta(hours=1)


def test_gauges_timeseries_all_groups_per_gauge_with_folded_metadata(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN two gauges seeded with multiple samples each inside the window
    WHEN gauges_timeseries_all is called over that window
    THEN one GaugeSeries is returned per gauge with rows, samples ordered by
        sampled_at, and each series' kind/description folded in from the registry.
    """
    app = metrics_enabled_runner_app
    pg_conn = build_pg_conn(app)
    try:
        truncate_gauges_tables(pg_conn)
        assert _count_gauge_rows(pg_conn) == 0

        base = _bucket_inside_window()
        earlier = base - timedelta(minutes=30)
        _seed_gauge_row(
            pg_conn,
            gauge_name=GaugeName.TOTAL_USERS.value,
            sampled_at=earlier,
            value_int=10,
        )
        _seed_gauge_row(
            pg_conn,
            gauge_name=GaugeName.TOTAL_USERS.value,
            sampled_at=base,
            value_int=12,
        )
        _seed_gauge_row(
            pg_conn,
            gauge_name=GaugeName.AVG_URLS_PER_UTUB.value,
            sampled_at=base,
            value_float=4.5,
        )

        window_start = base - timedelta(days=1)
        window_end = base + timedelta(hours=1)
        with app.app_context():
            response = gauges_timeseries_all(
                window="day",
                window_start=window_start,
                window_end=window_end,
            )

        assert response.window == "day"
        series_by_name = {series.gauge_name: series for series in response.gauges}
        assert set(series_by_name) == {
            GaugeName.TOTAL_USERS.value,
            GaugeName.AVG_URLS_PER_UTUB.value,
        }

        users_series = series_by_name[GaugeName.TOTAL_USERS.value]
        assert users_series.kind == GAUGE_REGISTRY[GaugeName.TOTAL_USERS].kind.value
        assert (
            users_series.description
            == GAUGE_REGISTRY[GaugeName.TOTAL_USERS].description
        )
        # Ordered by sampled_at ascending: earlier (10) then base (12).
        assert [sample.value_int for sample in users_series.samples] == [10, 12]

        avg_series = series_by_name[GaugeName.AVG_URLS_PER_UTUB.value]
        assert avg_series.kind == GAUGE_REGISTRY[GaugeName.AVG_URLS_PER_UTUB].kind.value
        assert len(avg_series.samples) == 1
        assert avg_series.samples[0].value_float == 4.5
    finally:
        truncate_gauges_tables(pg_conn)
        pg_conn.close()


def test_gauges_timeseries_all_excludes_samples_outside_window(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN one sample inside the window and one outside it
    WHEN gauges_timeseries_all is called
    THEN only the in-window sample appears in the returned series.
    """
    app = metrics_enabled_runner_app
    pg_conn = build_pg_conn(app)
    try:
        truncate_gauges_tables(pg_conn)
        assert _count_gauge_rows(pg_conn) == 0

        base = _bucket_inside_window()
        outside = base - timedelta(days=10)
        _seed_gauge_row(
            pg_conn,
            gauge_name=GaugeName.TOTAL_UTUBS.value,
            sampled_at=base,
            value_int=3,
        )
        _seed_gauge_row(
            pg_conn,
            gauge_name=GaugeName.TOTAL_UTUBS.value,
            sampled_at=outside,
            value_int=99,
        )

        window_start = base - timedelta(days=1)
        window_end = base + timedelta(hours=1)
        with app.app_context():
            response = gauges_timeseries_all(
                window="day",
                window_start=window_start,
                window_end=window_end,
            )

        assert len(response.gauges) == 1
        series = response.gauges[0]
        assert [sample.value_int for sample in series.samples] == [3]
    finally:
        truncate_gauges_tables(pg_conn)
        pg_conn.close()


def test_gauges_timeseries_all_returns_empty_gauges_on_no_data(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN no gauge rows in the table
    WHEN gauges_timeseries_all is called over the window
    THEN the response carries an empty gauges list (no padding).
    """
    app = metrics_enabled_runner_app
    pg_conn = build_pg_conn(app)
    try:
        truncate_gauges_tables(pg_conn)
        assert _count_gauge_rows(pg_conn) == 0

        base = _bucket_inside_window()
        window_start = base - timedelta(days=1)
        window_end = base + timedelta(hours=1)
        with app.app_context():
            response = gauges_timeseries_all(
                window="day",
                window_start=window_start,
                window_end=window_end,
            )

        assert response.window == "day"
        assert response.gauges == []
    finally:
        truncate_gauges_tables(pg_conn)
        pg_conn.close()


def test_gauge_timeseries_one_returns_single_gauge_ordered_samples(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN two gauges seeded inside the window
    WHEN gauge_timeseries_one is called for one of them
    THEN only that gauge's samples are returned, ordered by sampled_at.
    """
    app = metrics_enabled_runner_app
    pg_conn = build_pg_conn(app)
    try:
        truncate_gauges_tables(pg_conn)
        assert _count_gauge_rows(pg_conn) == 0

        base = _bucket_inside_window()
        earlier = base - timedelta(minutes=20)
        _seed_gauge_row(
            pg_conn,
            gauge_name=GaugeName.TOTAL_URLS.value,
            sampled_at=base,
            value_int=8,
        )
        _seed_gauge_row(
            pg_conn,
            gauge_name=GaugeName.TOTAL_URLS.value,
            sampled_at=earlier,
            value_int=5,
        )
        _seed_gauge_row(
            pg_conn,
            gauge_name=GaugeName.TOTAL_TAGS.value,
            sampled_at=base,
            value_int=2,
        )

        window_start = base - timedelta(days=1)
        window_end = base + timedelta(hours=1)
        with app.app_context():
            samples = gauge_timeseries_one(
                gauge_name=GaugeName.TOTAL_URLS,
                window_start=window_start,
                window_end=window_end,
            )

        assert [sample.value_int for sample in samples] == [5, 8]
    finally:
        truncate_gauges_tables(pg_conn)
        pg_conn.close()


def test_latest_gauge_snapshot_returns_newest_row_per_gauge(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN a gauge with three samples at different timestamps
    WHEN latest_gauge_snapshot is called
    THEN exactly one row per gauge is returned, carrying the newest sample.
    """
    app = metrics_enabled_runner_app
    pg_conn = build_pg_conn(app)
    try:
        truncate_gauges_tables(pg_conn)
        assert _count_gauge_rows(pg_conn) == 0

        base = _bucket_inside_window()
        _seed_gauge_row(
            pg_conn,
            gauge_name=GaugeName.TOTAL_USERS.value,
            sampled_at=base - timedelta(hours=2),
            value_int=1,
        )
        _seed_gauge_row(
            pg_conn,
            gauge_name=GaugeName.TOTAL_USERS.value,
            sampled_at=base,
            value_int=3,
        )
        _seed_gauge_row(
            pg_conn,
            gauge_name=GaugeName.TOTAL_USERS.value,
            sampled_at=base - timedelta(hours=1),
            value_int=2,
        )
        _seed_gauge_row(
            pg_conn,
            gauge_name=GaugeName.TOTAL_UTUBS.value,
            sampled_at=base,
            value_int=7,
        )

        with app.app_context():
            rows = latest_gauge_snapshot()

        by_name = {row.gauge_name: row for row in rows}
        assert set(by_name) == {
            GaugeName.TOTAL_USERS.value,
            GaugeName.TOTAL_UTUBS.value,
        }
        assert by_name[GaugeName.TOTAL_USERS.value].value_int == 3
        assert by_name[GaugeName.TOTAL_UTUBS.value].value_int == 7
    finally:
        truncate_gauges_tables(pg_conn)
        pg_conn.close()


def test_list_gauges_covers_every_gauge_with_matching_metadata(
    metrics_enabled_runner_app: Flask,
) -> None:
    """
    GIVEN no database dependency (list_gauges is a pure registry walk)
    WHEN list_gauges is called
    THEN one row per GaugeName is returned, each row's kind/description matching
        the registry.
    """
    app = metrics_enabled_runner_app
    with app.app_context():
        rows = list_gauges()

    assert len(rows) == len(GaugeName)
    by_name = {row.gauge_name: row for row in rows}
    assert set(by_name) == {member.value for member in GaugeName}
    for gauge_name in GaugeName:
        row = by_name[gauge_name.value]
        assert row.kind == GAUGE_REGISTRY[gauge_name].kind.value
        assert row.description == GAUGE_REGISTRY[gauge_name].description
