from __future__ import annotations

import pytest
from flask import Flask
from redis import Redis

from backend.extensions.metrics.writer import MetricsWriter
from backend.metrics.events import EventName
from backend.utils.strings.config_strs import CONFIG_ENVS

pytestmark = pytest.mark.cli


_BEHAVIORAL_TEST_KEY_COUNT = 15000
_BEHAVIORAL_MEMORY_CAP = "1mb"


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


_BEHAVIORAL_TEST_LOCK_KEY = "metrics:test:behavioral-isolation-lock"
_BEHAVIORAL_TEST_LOCK_TTL_SECONDS = 120


def test_metrics_redis_eviction_does_not_affect_shared_redis(
    provide_metrics_redis: Redis,
    writer_with_metrics_enabled: MetricsWriter,
    app: Flask,
    worker_id: str,
) -> None:
    """
    GIVEN the dedicated `redis-metrics` container, with eviction-under-load
        exercised through a worker-scoped key namespace
    WHEN the writer drives ~15000 distinct counter keys past a 1mb cap on the
        metrics Redis
    THEN at least one key is evicted on the metrics Redis, while the shared
        `redis` container's key set and `maxmemory` configuration remain
        unchanged.

    Parallelism model: `maxmemory` is a redis-server-level setting (not
    per-DB), so any concurrent test writing to redis-metrics while the cap
    is in effect would hit OOM. This test therefore runs only when pytest is
    operating in single-worker mode (no `-n` flag, or `-n 1`). Under
    multi-worker pytest-xdist runs (`-n 2+`), the test skips — the
    accompanying `test_metrics_redis_isolated_from_shared_redis` config-only
    test continues to guard the isolation contract in that mode.

    Single-worker safety: even though only one worker actually performs the
    load, a SETNX-based mutex on the shared `redis` container is held for
    the duration of the load so any re-entrant call (e.g., a serial run
    repeated back-to-back across pytest sessions sharing the same redis)
    sees consistent state. Per-iteration endpoints embed `worker_id` so
    key collisions are impossible if the lock ever expires mid-run.
    """
    if provide_metrics_redis is None:
        pytest.skip("metrics redis backend not configured (memory://)")

    # Detect multi-worker pytest-xdist mode via the `worker_id` fixture.
    # `worker_id` is the literal string "master" when pytest is run without
    # `-n` (or with `-n0`); under `-n N` with N > 1 each worker reports as
    # `gw0`, `gw1`, etc. Skipping here keeps the behavioral load from
    # triggering OOM in concurrent metrics tests on other workers (the
    # accompanying config-only isolation test still runs and guards the
    # static contract).
    if worker_id != "master":
        pytest.skip(
            "behavioral isolation test cannot run in multi-worker"
            " pytest-xdist mode without OOMing concurrent metrics writers;"
            " redis-metrics maxmemory is server-level"
        )

    shared_client = Redis.from_url(app.config[CONFIG_ENVS.REDIS_URI])
    # Re-entrancy guard: keeps a stray second invocation (e.g., a second
    # pytest session sharing the same redis) from racing into the load.
    lock_acquired = shared_client.set(
        _BEHAVIORAL_TEST_LOCK_KEY,
        worker_id,
        nx=True,
        ex=_BEHAVIORAL_TEST_LOCK_TTL_SECONDS,
    )
    if not lock_acquired:
        shared_client.close()
        pytest.skip(
            "another concurrent pytest session is already running the"
            " behavioral isolation test; the redis-metrics maxmemory cap"
            " is shared across the whole instance"
        )

    # Capture the redis-metrics default cap (set by the container's
    # `--maxmemory` flag) before mutating it so the `finally` block can
    # restore the production-style configuration — not zero it out, which
    # would silently disable eviction for every subsequent test in the run.
    metrics_maxmemory_before = provide_metrics_redis.config_get("maxmemory")[
        "maxmemory"
    ]

    try:
        # Drain any counters left over from concurrent workers' writes so
        # the 1mb cap can be exercised by this test's writes alone. Other
        # workers were blocked from writing during this run by the mutex
        # above, but their pre-mutex writes can still occupy the cap.
        provide_metrics_redis.flushdb()

        shared_keys_before = set(shared_client.keys())
        # Exclude the mutex key from the pre/post comparison — it lives on
        # the shared redis only for the duration of this test and must not
        # show up as a "shared redis was modified by metrics" false positive.
        shared_keys_before.discard(_BEHAVIORAL_TEST_LOCK_KEY.encode("utf-8"))

        shared_maxmemory_before = int(
            shared_client.config_get("maxmemory")["maxmemory"]
        )
        assert shared_maxmemory_before == 0, (
            "shared redis is expected to be uncapped; the metrics cap lives"
            " only on the dedicated redis-metrics container"
        )

        provide_metrics_redis.config_set("maxmemory", _BEHAVIORAL_MEMORY_CAP)
        assert (
            provide_metrics_redis.config_get("maxmemory-policy")["maxmemory-policy"]
            == "allkeys-lru"
        )

        provide_metrics_redis.config_resetstat()
        assert provide_metrics_redis.info("stats")["evicted_keys"] == 0

        with app.app_context():
            for iteration in range(_BEHAVIORAL_TEST_KEY_COUNT):
                writer_with_metrics_enabled.record(
                    EventName.API_HIT,
                    endpoint=f"/isolation/{worker_id}/{iteration}",
                    method="GET",
                    status_code=200,
                )

        evicted = provide_metrics_redis.info("stats")["evicted_keys"]
        assert evicted > 0, (
            f"expected eviction under {_BEHAVIORAL_MEMORY_CAP} cap after"
            f" {_BEHAVIORAL_TEST_KEY_COUNT} distinct keys;"
            f" evicted_keys={evicted}"
        )

        shared_keys_after = set(shared_client.keys())
        shared_keys_after.discard(_BEHAVIORAL_TEST_LOCK_KEY.encode("utf-8"))
        assert shared_keys_after == shared_keys_before, (
            "shared redis keys must remain unchanged when only the dedicated"
            " metrics container drives writes"
        )
        assert int(shared_client.config_get("maxmemory")["maxmemory"]) == 0, (
            "dedicated maxmemory cap must not bleed onto the shared redis" " instance"
        )
    finally:
        # Restore the container-default cap so the sibling config-only
        # isolation test (and any subsequent metrics tests) see the same
        # `maxmemory` they would in production.
        provide_metrics_redis.config_set("maxmemory", metrics_maxmemory_before)
        provide_metrics_redis.config_resetstat()
        shared_client.delete(_BEHAVIORAL_TEST_LOCK_KEY)
        shared_client.close()
