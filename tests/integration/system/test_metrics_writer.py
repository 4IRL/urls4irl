from __future__ import annotations

import logging
from datetime import datetime, timezone
from unittest import mock
from unittest.mock import patch

import pytest
import redis as redis_module
from flask import Flask
from redis import Redis

from backend.extensions.metrics.dimensions import canonicalize_dimensions
from backend.extensions.metrics.writer import (
    MetricsWriter,
    record_duration,
    record_event,
)
from backend.metrics.event_registry import DAILY_BUCKET_SECONDS
from backend.metrics.events import DEVICE_TYPE_DIM_KEY, DeviceType, EventName
from backend.metrics.latency import LatencyMetricName
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.metrics_strs import METRICS_REDIS
from tests.integration.system.metrics_helpers import (
    IPHONE_UA,
    WINDOWS_CHROME_UA,
    find_counter_keys,
    find_latency_keys,
    parse_dims,
)

pytestmark = pytest.mark.cli

# UTUB_OPENED requires both bucket dims; a bare call is silently dropped.
_UTUB_OPENED_DIMS: dict[str, str] = {"url_count_bucket": "1-5", "age_bucket": "0-6d"}
_DAILY_EVENT_DIMS: dict[EventName, dict[str, str]] = {
    EventName.UTUB_OPENED: _UTUB_OPENED_DIMS,
}


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
                "device_type": DeviceType.MOBILE,
            },
        )
        record_event(
            EventName.UI_URL_ACCESS,
            dimensions={
                "device_type": DeviceType.MOBILE,
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
            dimensions={"result": "maybe", "device_type": DeviceType.MOBILE},
        )

    assert result is None
    assert any(
        record.message == "metrics: record_event failed"
        and record.levelno == logging.ERROR
        for record in caplog.records
    ), (
        "Expected an ERROR log with message 'metrics: record_event failed' on validation failure"
    )
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
    ), (
        "Expected an ERROR log with message 'metrics: record_event failed' on Redis failure"
    )


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
            dimensions={"search_active": "true", "device_type": DeviceType.MOBILE},
        )

    keys = find_counter_keys(provide_metrics_redis, EventName.UI_UTUB_SELECT)
    assert len(keys) == 1
    assert provide_metrics_redis.get(keys[0]) == b"1"
    canonical_dims = canonicalize_dimensions(
        {"search_active": "true", "device_type": DeviceType.MOBILE}
    )
    assert canonical_dims.encode() in keys[0]


def test_record_domain_event_auto_injects_device_type_from_request_context(
    metrics_enabled_app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a domain event recorded inside a request context with a mobile UA
    WHEN record_event is called with no dimensions
    THEN the writer auto-injects `device_type` from the UA classification
        and the stored dims contain only `{"device_type": MOBILE}`.
    """
    with metrics_enabled_app.test_request_context(
        "/", headers={"User-Agent": IPHONE_UA}
    ):
        record_event(EventName.UTUB_OPENED, dimensions=_UTUB_OPENED_DIMS)

    keys = find_counter_keys(provide_metrics_redis, EventName.UTUB_OPENED)
    assert len(keys) == 1
    dims = parse_dims(keys[0])
    assert dims == {**_UTUB_OPENED_DIMS, DEVICE_TYPE_DIM_KEY: int(DeviceType.MOBILE)}


def test_record_domain_event_auto_injects_device_type_desktop_from_chrome_ua(
    metrics_enabled_app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a domain event recorded inside a request context with a desktop UA
    WHEN record_event is called with no dimensions
    THEN the writer auto-injects `device_type` from the UA classification
        and the stored dims contain only `{"device_type": DESKTOP}`.
    """
    with metrics_enabled_app.test_request_context(
        "/", headers={"User-Agent": WINDOWS_CHROME_UA}
    ):
        record_event(EventName.UTUB_OPENED, dimensions=_UTUB_OPENED_DIMS)

    keys = find_counter_keys(provide_metrics_redis, EventName.UTUB_OPENED)
    assert len(keys) == 1
    dims = parse_dims(keys[0])
    assert dims == {**_UTUB_OPENED_DIMS, DEVICE_TYPE_DIM_KEY: int(DeviceType.DESKTOP)}


def test_record_domain_event_outside_request_context_falls_back_to_desktop(
    metrics_enabled_app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a domain event recorded under app_context() but no request_context
    WHEN record_event is called with no dimensions
    THEN the writer's UA-fetch falls back to DESKTOP since
        `has_request_context()` returns False.
    """
    with metrics_enabled_app.app_context():
        record_event(EventName.UTUB_OPENED, dimensions=_UTUB_OPENED_DIMS)

    keys = find_counter_keys(provide_metrics_redis, EventName.UTUB_OPENED)
    assert len(keys) == 1
    dims = parse_dims(keys[0])
    assert dims == {**_UTUB_OPENED_DIMS, DEVICE_TYPE_DIM_KEY: int(DeviceType.DESKTOP)}


def test_record_ui_event_preserves_caller_supplied_device_type(
    metrics_enabled_app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a UI event whose caller already supplied `device_type=MOBILE`
    WHEN record_event is called inside a request context whose UA classifies
        as DESKTOP
    THEN the caller-supplied `device_type` wins (the UA-based fallback does
        NOT override).
    """
    with metrics_enabled_app.test_request_context(
        "/", headers={"User-Agent": WINDOWS_CHROME_UA}
    ):
        record_event(
            EventName.UI_UTUB_SELECT,
            dimensions={
                DEVICE_TYPE_DIM_KEY: int(DeviceType.MOBILE),
                "search_active": "false",
            },
        )

    keys = find_counter_keys(provide_metrics_redis, EventName.UI_UTUB_SELECT)
    assert len(keys) == 1
    dims = parse_dims(keys[0])
    assert dims == {
        DEVICE_TYPE_DIM_KEY: int(DeviceType.MOBILE),
        "search_active": "false",
    }


_DAY_START: int = int(datetime(2026, 6, 5, tzinfo=timezone.utc).timestamp())
_DAY_SECONDS: int = DAILY_BUCKET_SECONDS


def _record_at(epoch: int, event: EventName) -> None:
    with patch("backend.extensions.metrics.writer.time.time", return_value=epoch):
        record_event(event, dimensions=_DAILY_EVENT_DIMS.get(event))


def _bucket_of(key: bytes, prefix: str) -> int:
    return int(key.decode().removeprefix(prefix).split(":")[0])


@pytest.mark.parametrize("event", [EventName.UTUB_OPENED, EventName.TAG_APPLIED])
def test_daily_event_buckets_by_utc_day(
    app: Flask,
    writer_with_metrics_enabled: MetricsWriter,
    provide_metrics_redis: Redis,
    event: EventName,
) -> None:
    """
    GIVEN a daily-bucket event
    WHEN counts are recorded at 00:01 and 23:59 of one day, and at 00:00 of the next
    THEN the same-day counts share one key and the next day gets its own key
        with a 86460 second TTL.
    """
    with app.app_context():
        _record_at(_DAY_START + 60, event)
        _record_at(_DAY_START + _DAY_SECONDS - 1, event)
        _record_at(_DAY_START + _DAY_SECONDS, event)

    prefix = METRICS_REDIS.COUNTER_KEY_PREFIX
    keys = find_counter_keys(provide_metrics_redis, event)
    assert sorted(_bucket_of(key, prefix) for key in keys) == [
        _DAY_START,
        _DAY_START + _DAY_SECONDS,
    ]
    for key in keys:
        expected = b"2" if _bucket_of(key, prefix) == _DAY_START else b"1"
        assert provide_metrics_redis.get(key) == expected
        assert 86_400 < provide_metrics_redis.ttl(key) <= 86_460


def test_hourly_event_honours_configured_bucket_width(
    app: Flask,
    writer_with_metrics_enabled: MetricsWriter,
    provide_metrics_redis: Redis,
) -> None:
    """
    GIVEN a non-daily event and a non-default bucket width of 600 seconds
    WHEN counts are recorded 700 seconds apart
    THEN keys are bucketed by the configured width and use its TTL.
    """
    writer_with_metrics_enabled._bucket_seconds = 600
    with app.app_context():
        _record_at(_DAY_START + 10, EventName.UTUB_CREATED)
        _record_at(_DAY_START + 710, EventName.UTUB_CREATED)

    prefix = METRICS_REDIS.COUNTER_KEY_PREFIX
    keys = find_counter_keys(provide_metrics_redis, EventName.UTUB_CREATED)
    assert sorted(_bucket_of(key, prefix) for key in keys) == [
        _DAY_START,
        _DAY_START + 600,
    ]
    for key in keys:
        assert 120 < provide_metrics_redis.ttl(key) <= 660


def test_record_duration_stays_hourly(
    app: Flask,
    writer_with_metrics_enabled: MetricsWriter,
    provide_metrics_redis: Redis,
) -> None:
    """
    GIVEN the daily policy for counters
    WHEN a duration sample is recorded mid-day
    THEN its latency key is bucketed to the hour, not the day.
    """
    instant = _DAY_START + 5 * 3600 + 1234
    with app.app_context():
        with patch("backend.extensions.metrics.writer.time.time", return_value=instant):
            record_duration(
                metric=LatencyMetricName.API_REQUEST_DURATION,
                duration_ms=5.0,
                endpoint="utubs.get_utub",
                method="GET",
                dimensions={DEVICE_TYPE_DIM_KEY: DeviceType.DESKTOP},
            )

    keys = find_latency_keys(
        provide_metrics_redis, LatencyMetricName.API_REQUEST_DURATION.value
    )
    assert len(keys) == 1
    assert (
        _bucket_of(keys[0], METRICS_REDIS.LATENCY_KEY_PREFIX) == _DAY_START + 5 * 3600
    )
