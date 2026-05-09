from __future__ import annotations

import logging
from typing import Generator

import pytest
import redis as redis_module
from flask import Flask
from redis import Redis

from backend.extensions.metrics.dimensions import canonicalize_dimensions
from backend.extensions.metrics.writer import MetricsWriter, record_event
from backend.metrics.events import EventName
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.metrics_strs import METRICS_REDIS

pytestmark = pytest.mark.cli


@pytest.fixture
def writer_with_metrics_enabled(
    app: Flask, provide_metrics_redis: Redis
) -> Generator[MetricsWriter, None, None]:
    """Initialize a fresh MetricsWriter against the per-worker metrics DB
    with `METRICS_ENABLED=True`. Restores the original config flag on teardown.
    """
    original_metrics_enabled = app.config.get(CONFIG_ENVS.METRICS_ENABLED, False)
    app.config[CONFIG_ENVS.METRICS_ENABLED] = True
    metrics_writer = MetricsWriter()
    metrics_writer.init_app(app)
    yield metrics_writer
    app.config[CONFIG_ENVS.METRICS_ENABLED] = original_metrics_enabled


def _find_counter_keys(metrics_redis: Redis, event: EventName) -> list[bytes]:
    pattern = f"{METRICS_REDIS.COUNTER_KEY_PREFIX}*:{event.value}:*"
    return list(metrics_redis.scan_iter(match=pattern))


def test_writer_increments_redis_counter_for_api_hit(
    app: Flask,
    writer_with_metrics_enabled: MetricsWriter,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a MetricsWriter wired to the metrics Redis DB
    WHEN record_event is called for API_HIT with endpoint/method/status_code
    THEN exactly one matching counter key exists with value b"1".
    """
    with app.app_context():
        record_event(
            EventName.API_HIT,
            endpoint="/utubs",
            method="POST",
            status_code=200,
        )

    keys = _find_counter_keys(provide_metrics_redis, EventName.API_HIT)
    assert len(keys) == 1
    assert provide_metrics_redis.get(keys[0]) == b"1"


def test_writer_uses_canonical_dimensions_in_key(
    app: Flask,
    writer_with_metrics_enabled: MetricsWriter,
    provide_metrics_redis: Redis,
):
    """
    GIVEN two record_event calls whose dimensions dicts have the same
        contents but different key insertion order
    WHEN both are recorded
    THEN exactly one counter key exists with value b"2"
        (canonicalize_dimensions sorts keys).
    """
    with app.app_context():
        record_event(
            EventName.UI_URL_ACCESS,
            dimensions={
                "trigger": "main_button",
                "search_active": "false",
                "active_tag_count": 0,
            },
        )
        record_event(
            EventName.UI_URL_ACCESS,
            dimensions={
                "active_tag_count": 0,
                "search_active": "false",
                "trigger": "main_button",
            },
        )

    keys = _find_counter_keys(provide_metrics_redis, EventName.UI_URL_ACCESS)
    assert len(keys) == 1
    assert provide_metrics_redis.get(keys[0]) == b"2"


def test_writer_separate_keys_for_distinct_dimensions(
    app: Flask,
    writer_with_metrics_enabled: MetricsWriter,
    provide_metrics_redis: Redis,
):
    """
    GIVEN two record_event calls with distinct dimension values
    WHEN both are recorded
    THEN two distinct counter keys exist, each with value b"1".
    """
    with app.app_context():
        record_event(
            EventName.API_HIT,
            endpoint="/utubs",
            method="POST",
            status_code=200,
        )
        record_event(
            EventName.API_HIT,
            endpoint="/urls",
            method="GET",
            status_code=200,
        )

    keys = _find_counter_keys(provide_metrics_redis, EventName.API_HIT)
    assert len(keys) == 2
    for key in keys:
        assert provide_metrics_redis.get(key) == b"1"


def test_writer_log_and_drop_on_invalid_dimensions(
    app: Flask,
    writer_with_metrics_enabled: MetricsWriter,
    provide_metrics_redis: Redis,
    caplog: pytest.LogCaptureFixture,
):
    """
    GIVEN a record_event call with a Literal-mismatch dimension
    WHEN the writer attempts to record the event
    THEN the call returns None without raising, the failure is logged,
        and the metrics DB is empty.
    """
    caplog.set_level(logging.WARNING)
    with app.app_context():
        result = record_event(
            EventName.UI_URL_COPY,
            dimensions={"result": "maybe"},
        )

    assert result is None
    assert any(
        "metrics" in record.message.lower() for record in caplog.records
    ), "Expected a metrics log entry on validation failure"
    assert provide_metrics_redis.dbsize() == 0


def test_writer_log_and_drop_on_redis_failure(
    app: Flask,
    writer_with_metrics_enabled: MetricsWriter,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    GIVEN the writer's Redis client raises ConnectionError on incr
    WHEN record_event is called
    THEN the call returns None without raising and the exception is logged.
    """

    class _BrokenRedis:
        def pipeline(self):
            raise redis_module.exceptions.ConnectionError("simulated redis failure")

    monkeypatch.setattr(writer_with_metrics_enabled, "_redis", _BrokenRedis())

    caplog.set_level(logging.ERROR)
    with app.app_context():
        result = record_event(
            EventName.API_HIT,
            endpoint="/utubs",
            method="POST",
            status_code=200,
        )

    assert result is None
    assert any(
        "metrics" in record.message.lower() for record in caplog.records
    ), "Expected a metrics log entry on Redis failure"


def test_writer_disabled_when_metrics_enabled_false(
    app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN METRICS_ENABLED is False (the ConfigTest default)
    WHEN record_event is called
    THEN the writer is a no-op: no Redis client built, no key written.
    """
    metrics_writer = MetricsWriter()
    metrics_writer.init_app(app)
    assert metrics_writer._redis is None

    with app.app_context():
        record_event(
            EventName.API_HIT,
            endpoint="/utubs",
            method="POST",
            status_code=200,
        )

    assert provide_metrics_redis.dbsize() == 0


def test_writer_uses_metrics_redis_db(
    app: Flask,
    writer_with_metrics_enabled: MetricsWriter,
):
    """
    GIVEN a MetricsWriter initialized for tests
    WHEN the writer's underlying Redis connection is inspected
    THEN it connects to the per-worker DB index from app.config[METRICS_REDIS_DB].
    """
    expected_db = app.config[CONFIG_ENVS.METRICS_REDIS_DB]
    redis_client = writer_with_metrics_enabled._redis
    assert redis_client is not None
    assert redis_client.connection_pool.connection_kwargs["db"] == expected_db


def test_writer_increments_redis_counter_for_ui_event(
    app: Flask,
    writer_with_metrics_enabled: MetricsWriter,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a UI event with dimensions (non-API_HIT path)
    WHEN record_event is called
    THEN exactly one counter key exists for the event with value b"1",
        and its dimensions segment matches the canonical-dimensions JSON.
    """
    with app.app_context():
        record_event(
            EventName.UI_UTUB_SELECT,
            dimensions={"search_active": "true"},
        )

    keys = _find_counter_keys(provide_metrics_redis, EventName.UI_UTUB_SELECT)
    assert len(keys) == 1
    assert provide_metrics_redis.get(keys[0]) == b"1"
    canonical_dims = canonicalize_dimensions({"search_active": "true"})
    assert canonical_dims.encode() in keys[0]
