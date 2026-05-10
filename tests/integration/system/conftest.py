from __future__ import annotations

from typing import Any, Generator

import pytest
from flask import Flask
from redis import Redis

from backend import metrics_writer as app_metrics_writer
from backend.utils.strings.config_strs import CONFIG_ENVS


def reset_postgres_enum_to_lowercase_values(pg_conn: Any) -> None:
    """Force the Postgres `event_category_enum` type to contain only the
    lowercase StrEnum VALUES — matching the production migration's
    `postgresql.ENUM("api", "domain", "ui", name="event_category_enum")`.

    `db.create_all()` (used in test setup) generates the enum from the
    SQLAlchemy column definition. Without `values_callable`, SQLAlchemy
    emits the enum using the member NAMES (uppercase), so the test DB's
    enum disagrees with production. We rebuild the enum here so callers
    reproduce the exact mismatch production hits.

    Accepts a raw psycopg2 connection. Tests driven by SQLAlchemy can
    obtain one via `db.engine.raw_connection()` and pass it through.
    """
    with pg_conn.cursor() as cur:
        cur.execute('DELETE FROM "EventRegistry"')
        cur.execute('ALTER TABLE "EventRegistry" ALTER COLUMN "category" TYPE TEXT')
        cur.execute("DROP TYPE IF EXISTS event_category_enum")
        cur.execute("CREATE TYPE event_category_enum AS ENUM ('api', 'domain', 'ui')")
        cur.execute(
            'ALTER TABLE "EventRegistry" ALTER COLUMN "category"'
            " TYPE event_category_enum USING category::event_category_enum"
        )
    pg_conn.commit()


@pytest.fixture
def metrics_enabled_app(
    app: Flask, provide_metrics_redis: Redis | None
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
    if provide_metrics_redis is None:
        pytest.skip("metrics Redis is unavailable in this environment")

    original_metrics_enabled = app.config.get(CONFIG_ENVS.METRICS_ENABLED, False)
    original_redis = app_metrics_writer._redis
    original_enabled = app_metrics_writer._enabled

    app.config[CONFIG_ENVS.METRICS_ENABLED] = True
    app_metrics_writer.init_app(app)

    yield app

    app.config[CONFIG_ENVS.METRICS_ENABLED] = original_metrics_enabled
    app_metrics_writer._redis = original_redis
    app_metrics_writer._enabled = original_enabled
