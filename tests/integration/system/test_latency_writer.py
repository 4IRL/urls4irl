from __future__ import annotations

import logging
import time

import pytest
import redis as redis_module
from flask import Flask
from redis import Redis

from backend.extensions.metrics.buckets import compute_bucket_start_epoch
from backend.extensions.metrics.writer import MetricsWriter, record_duration
from backend.metrics.events import DEVICE_TYPE_DIM_KEY, DeviceType
from backend.metrics.latency import LATENCY_SAMPLE_CAP_PER_BUCKET, LatencyMetricName
from tests.integration.system.metrics_helpers import (
    build_latency_key,
    find_latency_keys,
)

pytestmark = pytest.mark.cli

_METRIC_VALUE = LatencyMetricName.API_REQUEST_DURATION.value
_ENDPOINT = "utubs.get_utub"
_METHOD = "GET"


def _expected_key(writer: MetricsWriter, device_type: DeviceType) -> str:
    bucket_start = compute_bucket_start_epoch(int(time.time()), writer._bucket_seconds)
    return build_latency_key(
        bucket_start, _METRIC_VALUE, _ENDPOINT, _METHOD, device_type
    )


def test_record_duration_buffers_samples_in_capped_redis_list(
    app: Flask,
    writer_with_metrics_enabled: MetricsWriter,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a MetricsWriter wired to the metrics Redis DB
    WHEN record_duration is called N times for the same endpoint/method/device
    THEN one matching latency list key exists, its length is min(N, cap),
        and LRANGE returns the pushed fixed-precision duration strings.
    """
    assert find_latency_keys(provide_metrics_redis, _METRIC_VALUE) == []

    durations = [12.5, 30.0, 7.125]
    with app.app_context():
        for duration in durations:
            record_duration(
                metric=LatencyMetricName.API_REQUEST_DURATION,
                duration_ms=duration,
                endpoint=_ENDPOINT,
                method=_METHOD,
                dimensions={DEVICE_TYPE_DIM_KEY: DeviceType.DESKTOP},
            )

    keys = find_latency_keys(provide_metrics_redis, _METRIC_VALUE)
    assert len(keys) == 1
    expected_key = _expected_key(writer_with_metrics_enabled, DeviceType.DESKTOP)
    assert keys[0].decode() == expected_key

    stored = provide_metrics_redis.lrange(expected_key, 0, -1)
    assert len(stored) == len(durations)
    decoded = [value.decode() for value in stored]
    # LPUSH prepends, so the most recent push is at index 0.
    assert decoded == [f"{duration:.3f}" for duration in reversed(durations)]


def test_record_duration_ltrims_to_cap(
    app: Flask,
    writer_with_metrics_enabled: MetricsWriter,
    provide_metrics_redis: Redis,
):
    """
    GIVEN more than LATENCY_SAMPLE_CAP_PER_BUCKET samples for one bucket/dims
    WHEN record_duration is called for each
    THEN the list is LTRIM'd to exactly the cap (oldest discarded).
    """
    assert find_latency_keys(provide_metrics_redis, _METRIC_VALUE) == []

    over_cap = LATENCY_SAMPLE_CAP_PER_BUCKET + 25
    with app.app_context():
        for index in range(over_cap):
            record_duration(
                metric=LatencyMetricName.API_REQUEST_DURATION,
                duration_ms=float(index),
                endpoint=_ENDPOINT,
                method=_METHOD,
                dimensions={DEVICE_TYPE_DIM_KEY: DeviceType.MOBILE},
            )

    expected_key = _expected_key(writer_with_metrics_enabled, DeviceType.MOBILE)
    assert provide_metrics_redis.llen(expected_key) == LATENCY_SAMPLE_CAP_PER_BUCKET


def test_record_duration_separate_keys_for_distinct_device_types(
    app: Flask,
    writer_with_metrics_enabled: MetricsWriter,
    provide_metrics_redis: Redis,
):
    """
    GIVEN two record_duration calls with distinct device types
    WHEN both are recorded
    THEN two distinct latency list keys exist, one per device type.
    """
    with app.app_context():
        record_duration(
            metric=LatencyMetricName.API_REQUEST_DURATION,
            duration_ms=10.0,
            endpoint=_ENDPOINT,
            method=_METHOD,
            dimensions={DEVICE_TYPE_DIM_KEY: DeviceType.MOBILE},
        )
        record_duration(
            metric=LatencyMetricName.API_REQUEST_DURATION,
            duration_ms=20.0,
            endpoint=_ENDPOINT,
            method=_METHOD,
            dimensions={DEVICE_TYPE_DIM_KEY: DeviceType.DESKTOP},
        )

    keys = find_latency_keys(provide_metrics_redis, _METRIC_VALUE)
    assert len(keys) == 2


def test_record_duration_early_returns_when_endpoint_is_none(
    app: Flask,
    writer_with_metrics_enabled: MetricsWriter,
    provide_metrics_redis: Redis,
):
    """
    GIVEN endpoint=None (an unmatched route)
    WHEN record_duration is called
    THEN no latency key is written (early-return guard).
    """
    assert find_latency_keys(provide_metrics_redis, _METRIC_VALUE) == []

    with app.app_context():
        record_duration(
            metric=LatencyMetricName.API_REQUEST_DURATION,
            duration_ms=42.0,
            endpoint=None,
            method=_METHOD,
            dimensions={DEVICE_TYPE_DIM_KEY: DeviceType.DESKTOP},
        )

    assert find_latency_keys(provide_metrics_redis, _METRIC_VALUE) == []


def test_record_duration_disabled_when_metrics_enabled_false(
    app: Flask,
    provide_metrics_redis: Redis,
):
    """
    GIVEN METRICS_ENABLED is False (the ConfigTest default)
    WHEN record_duration is called
    THEN the writer is a no-op: no Redis client built, no key written.
    """
    metrics_writer = MetricsWriter()
    metrics_writer.init_app(app)
    assert metrics_writer._redis is None

    with app.app_context():
        record_duration(
            metric=LatencyMetricName.API_REQUEST_DURATION,
            duration_ms=15.0,
            endpoint=_ENDPOINT,
            method=_METHOD,
            dimensions={DEVICE_TYPE_DIM_KEY: DeviceType.DESKTOP},
        )

    assert provide_metrics_redis.dbsize() == 0


def test_record_duration_log_and_drop_on_redis_failure(
    app: Flask,
    writer_with_metrics_enabled: MetricsWriter,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    GIVEN the writer's Redis client raises ConnectionError on pipeline
    WHEN record_duration is called
    THEN the call returns None without raising and the failure is logged.
    """

    class _BrokenRedis:
        def pipeline(self):
            raise redis_module.exceptions.ConnectionError("simulated redis failure")

    monkeypatch.setattr(writer_with_metrics_enabled, "_redis", _BrokenRedis())

    caplog.set_level(logging.ERROR)
    with app.app_context():
        result = record_duration(
            metric=LatencyMetricName.API_REQUEST_DURATION,
            duration_ms=15.0,
            endpoint=_ENDPOINT,
            method=_METHOD,
            dimensions={DEVICE_TYPE_DIM_KEY: DeviceType.DESKTOP},
        )

    assert result is None
    assert any(
        record.message == "metrics: record_duration failed"
        and record.levelno == logging.ERROR
        for record in caplog.records
    ), "Expected an ERROR log 'metrics: record_duration failed' on Redis failure"


def test_record_duration_outside_app_context_is_silent_noop():
    """
    GIVEN no Flask application context (CLI/script caller)
    WHEN the module-level record_duration proxy is invoked
    THEN the RuntimeError from current_app is swallowed and None returned.
    """
    result = record_duration(
        metric=LatencyMetricName.API_REQUEST_DURATION,
        duration_ms=15.0,
        endpoint=_ENDPOINT,
        method=_METHOD,
        dimensions={DEVICE_TYPE_DIM_KEY: DeviceType.DESKTOP},
    )
    assert result is None
