from __future__ import annotations

import pytest
from flask import Flask
from redis import Redis

from backend.utils.strings.config_strs import CONFIG_ENVS

pytestmark = pytest.mark.cli


def test_metrics_redis_isolated_from_shared_redis(
    provide_metrics_redis: Redis,
    app: Flask,
) -> None:
    """
    GIVEN the dedicated `redis-metrics` container and the shared `redis` container
    WHEN their runtime configs are inspected
    THEN `redis-metrics` is capped with an `allkeys-lru` eviction policy, while
        the shared `redis` remains uncapped, and the two are distinct instances.
    """
    if provide_metrics_redis is None:
        pytest.skip("metrics redis backend not configured (memory://)")

    shared_client = Redis.from_url(app.config[CONFIG_ENVS.REDIS_URI])
    try:
        assert (
            shared_client.connection_pool.connection_kwargs
            != provide_metrics_redis.connection_pool.connection_kwargs
        ), "metrics and shared redis must be distinct instances"

        assert int(shared_client.config_get("maxmemory")["maxmemory"]) == 0, (
            "shared redis must remain uncapped; eviction belongs only on"
            " redis-metrics"
        )

        metrics_policy = provide_metrics_redis.config_get("maxmemory-policy")[
            "maxmemory-policy"
        ]
        assert (
            metrics_policy == "allkeys-lru"
        ), f"redis-metrics must use allkeys-lru eviction; got {metrics_policy!r}"
        assert (
            int(provide_metrics_redis.config_get("maxmemory")["maxmemory"]) > 0
        ), "redis-metrics must have a maxmemory cap so counters age out under load"
    finally:
        shared_client.close()
