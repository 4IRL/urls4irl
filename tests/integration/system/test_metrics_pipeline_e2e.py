from __future__ import annotations

from typing import Any, Generator, Tuple

import psycopg2
import pytest
from flask import Flask
from flask.testing import FlaskCliRunner
from redis import Redis

from backend import db, metrics_writer as app_metrics_writer
from backend.extensions.metrics.registry_sync import sync_event_registry
from backend.metrics.events import EventName
from backend.models.event_registry import Event_Registry
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.metrics_strs import METRICS_REDIS
from scripts.flush_metrics import run_flush
from tests.utils_for_test import get_csrf_token

pytestmark = pytest.mark.cli

INGEST_URL = "/api/metrics"


@pytest.fixture
def metrics_enabled_runner_app(
    runner: Tuple[Flask, FlaskCliRunner],
    provide_metrics_redis: Redis,
) -> Generator[Flask, None, None]:
    """Activate the metrics_writer extension on the `runner` fixture's app.

    The `runner` fixture is required (instead of the `app` fixture) because
    this test calls into `sync_event_registry(...)` and `run_flush(...)` —
    both of which open their own DB transactions. The `app` fixture wraps
    every test in a SAVEPOINT and rolls back at teardown, which deadlocks
    when an inline psycopg2 connection writes rows the SAVEPOINT-bound
    session cannot see (and vice versa). `runner` uses `clear_database`
    teardown instead, so inline psycopg2 + SQLAlchemy can coexist.

    Mutates the module-level `metrics_writer` singleton in place (rather
    than swapping a fresh instance) so the route's
    `from backend import metrics_writer` import and the proxy's
    `current_app.extensions["metrics_writer"]` lookup both resolve to the
    same writer that this fixture has just enabled.
    """
    app = runner[0]

    original_metrics_enabled = app.config.get(CONFIG_ENVS.METRICS_ENABLED, False)
    original_redis = app_metrics_writer._redis
    original_enabled = app_metrics_writer._enabled

    app.config[CONFIG_ENVS.METRICS_ENABLED] = True
    app_metrics_writer.init_app(app)

    yield app

    app.config[CONFIG_ENVS.METRICS_ENABLED] = original_metrics_enabled
    app_metrics_writer._redis = original_redis
    app_metrics_writer._enabled = original_enabled


def _build_pg_conn(app: Flask) -> Any:
    return psycopg2.connect(app.config["SQLALCHEMY_DATABASE_URI"])


def _reset_postgres_enum_to_lowercase_values(pg_conn: Any) -> None:
    """Force the Postgres `event_category_enum` type to contain only the
    lowercase StrEnum VALUES — matching the production migration's
    `postgresql.ENUM("api", "domain", "ui", name="event_category_enum")`.

    `db.create_all()` (used in test setup) generates the enum from the
    SQLAlchemy column definition. Without `values_callable`, SQLAlchemy
    emits the enum using the member NAMES (uppercase), so the test DB's
    enum disagrees with production. We rebuild the enum here so this test
    reproduces the exact mismatch production hits, ensuring this e2e
    chain exercises the F1 fix path (lowercase values via
    `values_callable=...` on the `Event_Registry.category` column).

    Uses an inline psycopg2 connection so the DDL commits before
    `sync_event_registry(...)` is invoked; using the SQLAlchemy session
    here would race with whatever transaction state the route handlers
    leave in place.
    """
    with pg_conn.cursor() as cur:
        cur.execute('DELETE FROM "EventRegistry"')
        cur.execute('ALTER TABLE "EventRegistry" ALTER COLUMN "category" TYPE TEXT')
        cur.execute("DROP TYPE IF EXISTS event_category_enum")
        cur.execute("CREATE TYPE event_category_enum AS ENUM ('api', 'domain', 'ui')")
        cur.execute(
            'ALTER TABLE "EventRegistry" ALTER COLUMN "category"'
            " TYPE event_category_enum USING category::event_category_enum"
        )
    pg_conn.commit()


def _truncate_metrics_tables(pg_conn: Any) -> None:
    with pg_conn.cursor() as cur:
        cur.execute('TRUNCATE TABLE "AnonymousMetrics" RESTART IDENTITY CASCADE')
    pg_conn.commit()


def test_metrics_pipeline_end_to_end(
    metrics_enabled_runner_app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a freshly-synced EventRegistry (one row per EventName), the
        metrics_writer extension enabled with a real metrics-DB Redis
        client, and an inline psycopg2 connection to the test DB
    WHEN the browser-side flow is exercised end-to-end:
        1. GET / to obtain a CSRF token
        2. POST /api/metrics with a single ui_url_copy event
        3. invoke run_flush(...) to drain Redis into AnonymousMetrics
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
        _reset_postgres_enum_to_lowercase_values(setup_conn)
    finally:
        setup_conn.close()

    with app.app_context():
        sync_event_registry(app)
        assert db.session.query(Event_Registry).count() == len(EventName)

    # Step 2 — POST /api/metrics with a CSRF token from GET /
    flask_client = app.test_client()
    splash_response = flask_client.get("/")
    csrf_token = get_csrf_token(splash_response.get_data(), meta_tag=True)

    ingest_response = flask_client.post(
        INGEST_URL,
        json={
            "events": [
                {
                    "event_name": EventName.UI_URL_COPY.value,
                    "dimensions": {"result": "success"},
                }
            ]
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert ingest_response.status_code == 200
    assert ingest_response.get_json()["accepted"] == 1

    # Step 3 — exactly one counter key exists for ui_url_copy with value b"1".
    # The api_hit middleware also records the GET / response as an api_hit
    # counter, but that is incidental to the e2e chain under test. Delete
    # those api_hit keys so the flush below only exercises the ui_url_copy
    # path the test asserts on.
    counter_pattern = (
        f"{METRICS_REDIS.COUNTER_KEY_PREFIX}*:{EventName.UI_URL_COPY.value}:*"
    )
    counter_keys = list(provide_metrics_redis.scan_iter(match=counter_pattern))
    assert len(counter_keys) == 1
    assert provide_metrics_redis.get(counter_keys[0]) == b"1"

    api_hit_pattern = f"{METRICS_REDIS.COUNTER_KEY_PREFIX}*:{EventName.API_HIT.value}:*"
    api_hit_keys = list(provide_metrics_redis.scan_iter(match=api_hit_pattern))
    if api_hit_keys:
        provide_metrics_redis.delete(*api_hit_keys)

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
        assert dimensions == {"result": "success"}
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
