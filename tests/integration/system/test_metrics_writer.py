from __future__ import annotations

import logging
from typing import Generator
from unittest import mock
from unittest.mock import patch

import pytest
import redis as redis_module
from flask import Flask
from redis import Redis

from backend.extensions.metrics.dimensions import canonicalize_dimensions
from backend.extensions.metrics.writer import MetricsWriter, record_event
from backend.metrics.events import EventName
from backend.utils.strings.config_strs import CONFIG_ENVS
from tests.integration.system.metrics_helpers import find_counter_keys

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
    assert find_counter_keys(provide_metrics_redis, EventName.API_HIT) == []

    with app.app_context():
        record_event(
            EventName.API_HIT,
            endpoint="/utubs",
            method="POST",
            status_code=200,
        )

    keys = find_counter_keys(provide_metrics_redis, EventName.API_HIT)
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

    keys = find_counter_keys(provide_metrics_redis, EventName.UI_URL_ACCESS)
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

    keys = find_counter_keys(provide_metrics_redis, EventName.API_HIT)
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
        record.message == "metrics: record_event failed"
        and record.levelno == logging.ERROR
        for record in caplog.records
    ), "Expected an ERROR log with message 'metrics: record_event failed' on validation failure"
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
        record.message == "metrics: record_event failed"
        and record.levelno == logging.ERROR
        for record in caplog.records
    ), "Expected an ERROR log with message 'metrics: record_event failed' on Redis failure"


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


_URI_PARAM_CASES = [
    pytest.param("redis://localhost:6379/3", id="standard-host-port-db3"),
    pytest.param(
        "redis://:s3cr3t@redis-host:6380/5", id="custom-port-and-password-db5"
    ),
    pytest.param("redis://localhost:6379/12", id="high-db-index-db12"),
    pytest.param("redis://localhost:6379/0", id="default-db-index-db0"),
]


@pytest.mark.parametrize("uri", _URI_PARAM_CASES)
def test_writer_uses_metrics_redis_uri(app: Flask, uri: str):
    """
    GIVEN a MetricsWriter initialized with a specific METRICS_REDIS_URI
    WHEN init_app builds the underlying Redis client
    THEN Redis.from_url is invoked with the exact URI from app.config.

    Parametrized to cover standard URIs, URIs with custom ports and
    passwords, high DB indices, and the default DB-0 case.
    """
    config_overrides = {
        CONFIG_ENVS.METRICS_ENABLED: True,
        CONFIG_ENVS.METRICS_REDIS_URI: uri,
    }
    with mock.patch.dict(app.config, config_overrides):
        writer = MetricsWriter()
        # Patch Redis.from_url to avoid real network connections; capture the URI passed.
        with patch("backend.extensions.metrics.writer.Redis") as mock_redis_class:
            writer.init_app(app)
            mock_redis_class.from_url.assert_called_once_with(uri)


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

    keys = find_counter_keys(provide_metrics_redis, EventName.UI_UTUB_SELECT)
    assert len(keys) == 1
    assert provide_metrics_redis.get(keys[0]) == b"1"
    canonical_dims = canonicalize_dimensions({"search_active": "true"})
    assert canonical_dims.encode() in keys[0]
