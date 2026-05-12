from __future__ import annotations

import pytest
from flask import Flask
from redis import Redis

from backend.extensions.metrics.writer import MetricsWriter
from backend.metrics.events import EventName
from backend.utils.strings.config_strs import CONFIG_ENVS

pytestmark = pytest.mark.cli


def test_metrics_redis_isolation_under_memory_pressure(
    provide_metrics_redis: Redis,
    writer_with_metrics_enabled: MetricsWriter,
    app: Flask,
    worker_id: str,
) -> None:
    """
    GIVEN the dedicated `redis-metrics` container with `maxmemory` capped tiny
        and `allkeys-lru` eviction policy
    WHEN the writer drives a large number of distinct counter keys past the cap
    THEN telemetry counters are silently evicted (LRU semantics) without
        OOM errors, while the shared `redis` container is completely
        unaffected — neither its keys nor its `maxmemory` config change.
    """
    if worker_id != "master":
        pytest.skip(
            "eviction is container-wide; serialise to avoid evicting parallel"
            " workers' counter keys"
        )
    if provide_metrics_redis is None:
        pytest.skip("metrics redis backend not configured (memory://)")

    shared_client = Redis.from_url(app.config[CONFIG_ENVS.REDIS_URI])
    try:
        shared_keys_before = set(shared_client.keys())
        shared_maxmemory_before = int(
            shared_client.config_get("maxmemory")["maxmemory"]
        )
        assert shared_maxmemory_before == 0, (
            "shared redis is expected to be uncapped; the metrics cap lives only"
            " on the dedicated redis-metrics container"
        )

        provide_metrics_redis.config_set("maxmemory", "1mb")
        assert (
            provide_metrics_redis.config_get("maxmemory-policy")["maxmemory-policy"]
            == "allkeys-lru"
        )

        assert provide_metrics_redis.info("stats")["evicted_keys"] == 0
        provide_metrics_redis.config_resetstat()

        with app.app_context():
            for iteration in range(0, 100):
                writer_with_metrics_enabled.record(
                    EventName.API_HIT,
                    endpoint=f"/isolation/phase1/{iteration}",
                    method="GET",
                    status_code=200,
                )

            early_keys = list(
                provide_metrics_redis.scan_iter(match="metrics:counter:*", count=100)
            )[:50]

            for iteration in range(100, 15000):
                writer_with_metrics_enabled.record(
                    EventName.API_HIT,
                    endpoint=f"/isolation/phase2/{iteration}",
                    method="GET",
                    status_code=200,
                )

        evicted = provide_metrics_redis.info("stats")["evicted_keys"]
        assert evicted > 0, (
            f"expected eviction under 1mb cap after 15000 distinct keys; "
            f"evicted_keys={evicted}"
        )

        evicted_early = [
            early_key
            for early_key in early_keys
            if not provide_metrics_redis.exists(early_key)
        ]
        assert len(evicted_early) > 0, (
            "expected at least one early-written key to be evicted under LRU,"
            " but all early keys were still present"
        )

        shared_keys_after = set(shared_client.keys())
        assert shared_keys_after == shared_keys_before, (
            "shared redis keys must remain unchanged when only the dedicated"
            " metrics container drives writes"
        )
        assert (
            int(shared_client.config_get("maxmemory")["maxmemory"]) == 0
        ), "dedicated maxmemory cap must not bleed onto the shared redis instance"
    finally:
        provide_metrics_redis.config_set("maxmemory", "0")
        provide_metrics_redis.config_resetstat()
        shared_client.close()
