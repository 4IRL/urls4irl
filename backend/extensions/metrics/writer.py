from __future__ import annotations

import time

from flask import Flask, current_app
from redis import Redis

from backend.extensions.metrics.buckets import compute_bucket_start_epoch
from backend.extensions.metrics.dimensions import canonicalize_dimensions
from backend.metrics.dimension_models import validate_dimensions
from backend.metrics.events import EventName
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.metrics_strs import METRICS_REDIS

_DEFAULT_BUCKET_SECONDS = 3600
_DEFAULT_BATCH_NONCE_TTL = 120
_KEY_TTL_FLOOR_SECONDS = 120
_KEY_TTL_GRACE_SECONDS = 60


class MetricsWriter:
    """Redis-backed writer for anonymous metrics counters.

    Mirrors the `EmailSender.init_app` extension pattern: register the
    instance at module scope, call `init_app(app)` from `create_app()`, and
    interact via the module-level `record_event(...)` proxy so domain code
    never imports the writer instance directly.
    """

    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._enabled: bool = False
        self._bucket_seconds: int = _DEFAULT_BUCKET_SECONDS
        self._batch_nonce_ttl: int = _DEFAULT_BATCH_NONCE_TTL

    def init_app(self, app: Flask) -> None:
        self._enabled = bool(app.config.get(CONFIG_ENVS.METRICS_ENABLED, False))
        self._bucket_seconds = int(
            app.config.get(CONFIG_ENVS.METRICS_BUCKET_SECONDS, _DEFAULT_BUCKET_SECONDS)
        )
        self._batch_nonce_ttl = int(
            app.config.get(
                CONFIG_ENVS.METRICS_BATCH_NONCE_TTL_SECONDS, _DEFAULT_BATCH_NONCE_TTL
            )
        )
        if self._enabled:
            metrics_uri = app.config.get(CONFIG_ENVS.METRICS_REDIS_URI)
            if metrics_uri and metrics_uri != "memory://":
                self._redis = Redis.from_url(metrics_uri)
        else:
            self._redis = None

        app.extensions["metrics_writer"] = self

    def record(
        self,
        event: EventName,
        *,
        endpoint: str | None = None,
        method: str | None = None,
        status_code: int | None = None,
        dimensions: dict | None = None,
    ) -> None:
        if not self._enabled or self._redis is None:
            return None
        try:
            if event is EventName.API_HIT:
                effective_dims: dict = {
                    "endpoint": endpoint,
                    "method": method,
                    "status_code": status_code,
                }
                if dimensions:
                    effective_dims.update(dimensions)
            else:
                effective_dims = dict(dimensions) if dimensions else {}

            validate_dimensions(event, effective_dims if effective_dims else None)

            bucket_start = compute_bucket_start_epoch(
                int(time.time()), self._bucket_seconds
            )
            canonical_dims = canonicalize_dimensions(effective_dims)
            counter_key = (
                f"{METRICS_REDIS.COUNTER_KEY_PREFIX}{bucket_start}:"
                f"{event.value}:{canonical_dims}"
            )
            ttl_seconds = max(
                self._bucket_seconds + _KEY_TTL_GRACE_SECONDS, _KEY_TTL_FLOOR_SECONDS
            )

            pipe = self._redis.pipeline()
            pipe.incr(counter_key)
            pipe.expire(counter_key, ttl_seconds)
            pipe.execute()
        except Exception:
            current_app.logger.exception("metrics: record_event failed")
            return None

    def reserve_batch(self, batch_id: str) -> bool:
        """Atomically reserve a batch nonce; True if newly reserved, False otherwise.

        Log-and-drop on Redis failure: returns True so telemetry degrades to
        "always proceed" rather than blocking the ingest path on a Redis hiccup.
        """
        if not self._enabled or self._redis is None:
            return True
        try:
            key = f"{METRICS_REDIS.BATCH_KEY_PREFIX}{batch_id}"
            result = self._redis.set(key, "1", nx=True, ex=self._batch_nonce_ttl)
            return bool(result)
        except Exception:
            current_app.logger.exception("metrics: reserve_batch failed")
            return True


def record_event(
    event: EventName,
    *,
    endpoint: str | None = None,
    method: str | None = None,
    status_code: int | None = None,
    dimensions: dict | None = None,
) -> None:
    """Module-level entry point for recording an anonymous metric event.

    Looks up the registered `MetricsWriter` from `current_app.extensions` and
    delegates to its `record(...)` method. Wrapped in `try/except RuntimeError`
    so callers in script/CLI contexts (no Flask application context) silently
    no-op rather than raising.
    """
    try:
        writer = current_app.extensions.get("metrics_writer")
    except RuntimeError:
        return None
    if writer is None:
        return None
    writer.record(
        event,
        endpoint=endpoint,
        method=method,
        status_code=status_code,
        dimensions=dimensions,
    )
