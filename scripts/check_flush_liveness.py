"""Liveness healthcheck for the metrics workflow container.

Reads the ``metrics:flush:last_success_epoch`` sentinel written by
``scripts/flush_metrics.py`` after every successful flush and exits non-zero
when the sentinel is missing or older than
``METRICS_FLUSH_LIVENESS_THRESHOLD_SECONDS`` (default 180s). Wired into the
workflow service's Docker healthcheck so the container is reported unhealthy
when flushes silently break — the prior ``pgrep cron`` healthcheck only
confirmed the cron daemon was alive, not that flushes were progressing.

Standalone (stdlib + ``redis`` only) so the workflow venv does not need
Flask/SQLAlchemy installed. Matches the Redis client construction used by
``flush_metrics.py`` exactly so password handling and decode behavior stay
consistent.
"""

from __future__ import annotations

import os
import sys
import time

import redis

LIVENESS_KEY: str = "metrics:flush:last_success_epoch"
DEFAULT_THRESHOLD_SECONDS: int = 180


def _build_redis_client_from_env() -> redis.Redis:
    """Construct a metrics-DB Redis client from env vars.

    Mirrors ``scripts.flush_metrics._build_redis_client_from_env`` so password
    handling and decode behavior match exactly.
    """
    redis_uri = os.environ.get("REDIS_URI")
    metrics_db = os.environ.get("METRICS_REDIS_DB")
    if not redis_uri:
        raise RuntimeError("REDIS_URI environment variable is required")
    if metrics_db is None:
        raise RuntimeError("METRICS_REDIS_DB environment variable is required")
    base, _trailing_db = redis_uri.rsplit("/", 1)
    metrics_uri = f"{base}/{metrics_db}"
    return redis.Redis.from_url(metrics_uri)


def _resolve_threshold_seconds() -> int:
    raw_threshold = os.environ.get("METRICS_FLUSH_LIVENESS_THRESHOLD_SECONDS")
    if raw_threshold is None or raw_threshold == "":
        return DEFAULT_THRESHOLD_SECONDS
    return int(raw_threshold)


def check_liveness(
    redis_client: redis.Redis,
    threshold_seconds: int,
    now_epoch: int,
) -> tuple[int, str]:
    """Return ``(exit_code, stderr_message)`` for the healthcheck decision.

    Pure function (no side effects) so it is unit-testable with a mock Redis
    client and an injected ``now_epoch``. Callers handle the actual ``print``
    + ``sys.exit``.
    """
    raw_value = redis_client.get(LIVENESS_KEY)
    if raw_value is None:
        return (1, "missing: no successful flush recorded")

    if isinstance(raw_value, bytes):
        decoded_value = raw_value.decode("utf-8", errors="replace")
    else:
        decoded_value = str(raw_value)

    try:
        last_success_epoch = int(decoded_value)
    except ValueError:
        return (
            1,
            f"missing: liveness sentinel value is not an integer: {decoded_value!r}",
        )

    age_seconds = now_epoch - last_success_epoch
    if age_seconds > threshold_seconds:
        return (
            1,
            f"stale: {age_seconds}s old, threshold {threshold_seconds}s",
        )
    return (0, "")


def main() -> int:
    threshold_seconds = _resolve_threshold_seconds()
    redis_client = _build_redis_client_from_env()
    try:
        exit_code, stderr_message = check_liveness(
            redis_client=redis_client,
            threshold_seconds=threshold_seconds,
            now_epoch=int(time.time()),
        )
    finally:
        try:
            redis_client.close()
        except Exception:
            pass

    if stderr_message:
        print(stderr_message, file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
