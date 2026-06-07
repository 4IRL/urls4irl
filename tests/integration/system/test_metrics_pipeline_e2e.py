from __future__ import annotations

from typing import Any

import psycopg2
import pytest
from flask import Flask
from redis import Redis

from backend import db
from backend.extensions.metrics.registry_sync import sync_event_registry
from backend.metrics.events import DeviceType, EventName
from backend.models.event_registry import Event_Registry
from backend.utils.strings.metrics_strs import METRICS_REDIS
from scripts.flush_metrics import run_flush
from tests.integration.system.conftest import reset_postgres_enum_to_lowercase_values

pytestmark = pytest.mark.cli

INGEST_URL = "/api/metrics"


def _build_pg_conn(app: Flask) -> Any:
    return psycopg2.connect(app.config["SQLALCHEMY_DATABASE_URI"])


def _truncate_metrics_tables(pg_conn: Any) -> None:
    with pg_conn.cursor() as cur:
        cur.execute('TRUNCATE TABLE "AnonymousMetrics" RESTART IDENTITY CASCADE')
    pg_conn.commit()


MULTI_EVENT_PAYLOAD: list[dict[str, object]] = [
    {
        "event_name": EventName.UI_URL_COPY.value,
        "dimensions": {"result": "success", "device_type": DeviceType.MOBILE},
    },
    {
        "event_name": EventName.UI_TAG_APPLY.value,
        "dimensions": {"device_type": DeviceType.MOBILE},
    },
    {
        "event_name": EventName.UI_UTUB_CREATE_OPEN.value,
        "dimensions": {"device_type": DeviceType.MOBILE},
    },
    {
        "event_name": EventName.UI_URL_CREATE_OPEN.value,
        "dimensions": {"device_type": DeviceType.MOBILE},
    },
]

# Set of event names used in MULTI_EVENT_PAYLOAD (for assertion lookups).
# Kept as an explicit literal (rather than derived from MULTI_EVENT_PAYLOAD) so
# the type checker can see a `frozenset[str]` directly without an `arg-type`
# ignore comment, and so the test source documents the expected events inline.
MULTI_EVENT_NAMES: frozenset[str] = frozenset(
    {
        EventName.UI_URL_COPY.value,
        EventName.UI_TAG_APPLY.value,
        EventName.UI_UTUB_CREATE_OPEN.value,
        EventName.UI_URL_CREATE_OPEN.value,
    }
)


def test_metrics_pipeline_end_to_end(
    metrics_enabled_runner_app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a freshly-synced EventRegistry (one row per EventName), the
        metrics_writer extension enabled with a real metrics-DB Redis
        client, and an inline psycopg2 connection to the test DB
    WHEN the browser-side flow is exercised end-to-end:
        1. POST /api/metrics with a single ui_url_copy event
        2. invoke run_flush(...) to drain Redis into AnonymousMetrics
    THEN every stage of the pipeline succeeds: the registry sync writes
        len(EventName) rows; the ingest returns 200 with accepted=1 and
        sets exactly one metrics:counter:* key with value b"1"; the flush
        upserts one AnonymousMetrics row with the expected dimensions and
        count, and clears the counter key from Redis.

    Chained e2e regression guard for the EventCategory enum + ingest +
    flush pipeline. Mirrors `test_flush_metrics.py`'s `runner` + inline
    psycopg2 pattern to avoid the SAVEPOINT/inline-conn deadlock the
    `app` fixture causes when both transaction owners write to the same
    rows in the same test.
    """
    app = metrics_enabled_runner_app

    # Step 1 — rebuild the Postgres enum to lowercase values (matches
    # production) via an inline psycopg2 conn, then sync EventRegistry
    # from the EventName enum.
    # The reset is required because `db.create_all()` builds the test
    # enum from SQLAlchemy member NAMES by default; without it, the F1
    # serialization mismatch is invisible in test (NAMES on both sides
    # agree by coincidence). With the reset, the F1 fix's
    # `values_callable=...` is the only thing that lets
    # `sync_event_registry` insert lowercase 'api'/'domain'/'ui' values
    # into the enum column.
    setup_conn = _build_pg_conn(app)
    try:
        reset_postgres_enum_to_lowercase_values(setup_conn)
    finally:
        setup_conn.close()

    with app.app_context():
        sync_event_registry(app)
        assert db.session.query(Event_Registry).count() == len(EventName)

    # POST /api/metrics
    flask_client = app.test_client()

    ingest_response = flask_client.post(
        INGEST_URL,
        json={
            "events": [
                {
                    "event_name": EventName.UI_URL_COPY.value,
                    "dimensions": {
                        "result": "success",
                        "device_type": DeviceType.MOBILE,
                    },
                }
            ]
        },
    )

    assert ingest_response.status_code == 200
    assert ingest_response.get_json()["accepted"] == 1

    # Step 3 — exactly one counter key exists for ui_url_copy with value b"1".
    counter_pattern = (
        f"{METRICS_REDIS.COUNTER_KEY_PREFIX}*:{EventName.UI_URL_COPY.value}:*"
    )
    counter_keys = list(provide_metrics_redis.scan_iter(match=counter_pattern))
    assert len(counter_keys) == 1
    assert provide_metrics_redis.get(counter_keys[0]) == b"1"

    # Step 4 — flush Redis into AnonymousMetrics via inline psycopg2 conn
    inline_conn = _build_pg_conn(app)
    try:
        upserted = run_flush(redis_client=provide_metrics_redis, pg_conn=inline_conn)
        assert upserted == 1

        with inline_conn.cursor() as cur:
            cur.execute(
                'SELECT "eventName", "dimensions", "count"'
                ' FROM "AnonymousMetrics" ORDER BY id'
            )
            rows = cur.fetchall()
        assert len(rows) == 1
        event_name, dimensions, count = rows[0]
        assert event_name == EventName.UI_URL_COPY.value
        assert dimensions == {"result": "success", "device_type": DeviceType.MOBILE}
        assert count == 1

        remaining_counter_keys = list(
            provide_metrics_redis.scan_iter(
                match=f"{METRICS_REDIS.COUNTER_KEY_PREFIX}*"
            )
        )
        assert remaining_counter_keys == []
    finally:
        _truncate_metrics_tables(inline_conn)
        inline_conn.close()


def test_metrics_pipeline_multi_event_payload(
    metrics_enabled_runner_app: Flask,
    provide_metrics_redis: Redis,
) -> None:
    """
    GIVEN a freshly-synced EventRegistry, the metrics_writer extension enabled,
        and an inline psycopg2 connection to the test DB
    WHEN a single POST /api/metrics is made with multiple events of different
        EventName types in one payload (MULTI_EVENT_PAYLOAD, 4 events)
    THEN the ingest returns 200 with accepted == len(MULTI_EVENT_PAYLOAD);
        one counter key is set in Redis for each distinct event; run_flush(...)
        upserts one AnonymousMetrics row per distinct event; and all counter
        keys are cleared from Redis after the flush.

    Covers the typical browser-batch path where several user interactions are
    buffered and shipped to the endpoint together.
    """
    app = metrics_enabled_runner_app

    setup_conn = _build_pg_conn(app)
    try:
        reset_postgres_enum_to_lowercase_values(setup_conn)
    finally:
        setup_conn.close()

    with app.app_context():
        sync_event_registry(app)
        assert db.session.query(Event_Registry).count() == len(EventName)

    flask_client = app.test_client()

    ingest_response = flask_client.post(
        INGEST_URL,
        json={"events": MULTI_EVENT_PAYLOAD},
    )

    assert ingest_response.status_code == 200
    assert ingest_response.get_json()["accepted"] == len(MULTI_EVENT_PAYLOAD)

    # One counter key per distinct event name submitted — value b"1" each.
    for event_name_value in MULTI_EVENT_NAMES:
        event_pattern = f"{METRICS_REDIS.COUNTER_KEY_PREFIX}*:{event_name_value}:*"
        event_counter_keys = list(provide_metrics_redis.scan_iter(match=event_pattern))
        assert len(event_counter_keys) == 1
        assert provide_metrics_redis.get(event_counter_keys[0]) == b"1"

    inline_conn = _build_pg_conn(app)
    try:
        upserted = run_flush(redis_client=provide_metrics_redis, pg_conn=inline_conn)
        assert upserted == len(MULTI_EVENT_NAMES)

        with inline_conn.cursor() as cur:
            cur.execute(
                'SELECT "eventName", "dimensions", "count"'
                ' FROM "AnonymousMetrics" ORDER BY "eventName"'
            )
            rows = cur.fetchall()

        assert len(rows) == len(MULTI_EVENT_NAMES)

        flushed_event_names = {row[0] for row in rows}
        assert flushed_event_names == MULTI_EVENT_NAMES

        device_only_event_names = {
            EventName.UI_TAG_APPLY.value,
            EventName.UI_UTUB_CREATE_OPEN.value,
            EventName.UI_URL_CREATE_OPEN.value,
        }
        for event_name_value, dimensions, count in rows:
            assert count == 1
            # ui_url_copy carries an event-specific dim (`result`) alongside the
            # auto-injected `device_type`. The formerly-None events now carry
            # only `device_type` via `_DimDeviceOnly`.
            if event_name_value == EventName.UI_URL_COPY.value:
                expected_dims = {"result": "success", "device_type": DeviceType.MOBILE}
                assert dimensions == expected_dims
            elif event_name_value in device_only_event_names:
                assert dimensions == {"device_type": DeviceType.MOBILE}

        remaining_counter_keys = list(
            provide_metrics_redis.scan_iter(
                match=f"{METRICS_REDIS.COUNTER_KEY_PREFIX}*"
            )
        )
        assert remaining_counter_keys == []
    finally:
        _truncate_metrics_tables(inline_conn)
        inline_conn.close()
