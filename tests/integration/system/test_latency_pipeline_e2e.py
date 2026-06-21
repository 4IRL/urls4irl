from __future__ import annotations

from typing import Any

import pytest
from flask import Flask
from redis import Redis

from backend import db
from backend.extensions.metrics.registry_sync import sync_event_registry
from backend.metrics.events import EventName
from backend.metrics.latency import LatencyMetricName
from backend.models.event_registry import Event_Registry
from backend.utils.strings.metrics_strs import METRICS_REDIS
from scripts.flush_metrics import FLUSH_LOCK_KEY, run_flush
from tests.integration.system.conftest import reset_postgres_enum_to_lowercase_values
from tests.integration.system.metrics_helpers import (
    build_pg_conn,
    find_latency_keys,
    truncate_latency_tables,
    truncate_metrics_tables,
)

pytestmark = pytest.mark.cli

_METRIC_VALUE = LatencyMetricName.API_REQUEST_DURATION.value


def _select_latency_rows(pg_conn: Any) -> list[tuple]:
    with pg_conn.cursor() as cur:
        cur.execute(
            'SELECT "metricName", "endpoint", "method"'
            ' FROM "AnonymousLatencySamples" ORDER BY id'
        )
        return cur.fetchall()


@pytest.fixture(autouse=True)
def _release_flush_lock(provide_metrics_redis: Redis):
    provide_metrics_redis.delete(FLUSH_LOCK_KEY)
    provide_metrics_redis.delete(METRICS_REDIS.LATENCY_LAST_PRUNE_KEY)
    yield
    provide_metrics_redis.delete(FLUSH_LOCK_KEY)
    provide_metrics_redis.delete(METRICS_REDIS.LATENCY_LAST_PRUNE_KEY)


def test_latency_pipeline_end_to_end(
    metrics_enabled_runner_app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN the metrics_writer extension enabled with a real metrics-DB Redis
        client and the request_timing/middleware hooks on the request path
    WHEN a real GET request is driven through the app (firing before/after
        request hooks) and run_flush is invoked
    THEN a metrics:latency:* Redis list key appears after the request, the flush
        drains it into AnonymousLatencySamples, and at least one row lands with
        the request's endpoint/method.
    """
    app = metrics_enabled_runner_app

    # The real request fires the api_hit counter, whose flushed AnonymousMetrics
    # row carries an FK to EventRegistry — sync the registry first so the counter
    # drain inside run_flush does not raise a ForeignKeyViolation.
    setup_conn = build_pg_conn(app)
    try:
        reset_postgres_enum_to_lowercase_values(setup_conn)
    finally:
        setup_conn.close()

    with app.app_context():
        sync_event_registry(app)
        assert db.session.query(Event_Registry).count() == len(EventName)

    pg_conn = build_pg_conn(app)
    try:
        truncate_latency_tables(pg_conn)
        truncate_metrics_tables(pg_conn)
        assert find_latency_keys(provide_metrics_redis, _METRIC_VALUE) == []

        flask_client = app.test_client()
        response = flask_client.get("/")
        assert response.status_code == 200

        latency_keys = find_latency_keys(provide_metrics_redis, _METRIC_VALUE)
        assert len(latency_keys) >= 1

        run_flush(redis_client=provide_metrics_redis, pg_conn=pg_conn)

        rows = _select_latency_rows(pg_conn)
        assert len(rows) >= 1
        for metric_name, endpoint, method in rows:
            assert metric_name == _METRIC_VALUE
            assert endpoint is not None
            assert method == "GET"

        assert find_latency_keys(provide_metrics_redis, _METRIC_VALUE) == []
    finally:
        truncate_latency_tables(pg_conn)
        truncate_metrics_tables(pg_conn)
        pg_conn.close()
