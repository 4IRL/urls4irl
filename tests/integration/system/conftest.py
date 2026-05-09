from __future__ import annotations

from typing import Generator

import pytest
from flask import Flask
from redis import Redis

from backend import metrics_writer as app_metrics_writer
from backend.utils.strings.config_strs import CONFIG_ENVS


@pytest.fixture
def metrics_enabled_app(
    app: Flask, provide_metrics_redis: Redis
) -> Generator[Flask, None, None]:
    """Re-init the module-level `metrics_writer` with `METRICS_ENABLED=True`
    so the after_request middleware writes counters into the per-worker
    metrics Redis DB and the ingest route's CSRF + nonce + dispatch path
    actually exercises Redis.

    Mutates the module-level singleton (the same instance the
    `app.extensions["metrics_writer"]` slot points at) rather than swapping
    in a fresh one — keeps the writer that `record_event(...)` resolves
    through `current_app.extensions` and the writer that the route's
    `from backend import metrics_writer` import binds to identical, so
    `mock.patch.object(app_metrics_writer, ...)` in tests is honored by
    both the route code and the proxy.

    Restores the original config flag and writer state on teardown so the
    fixture is safe under parallel xdist workers.
    """
    original_metrics_enabled = app.config.get(CONFIG_ENVS.METRICS_ENABLED, False)
    original_redis = app_metrics_writer._redis
    original_enabled = app_metrics_writer._enabled

    app.config[CONFIG_ENVS.METRICS_ENABLED] = True
    app_metrics_writer.init_app(app)

    yield app

    app.config[CONFIG_ENVS.METRICS_ENABLED] = original_metrics_enabled
    app_metrics_writer._redis = original_redis
    app_metrics_writer._enabled = original_enabled
