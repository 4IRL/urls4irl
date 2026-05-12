from __future__ import annotations

from typing import Any, Generator

import pytest
from flask import Flask
from redis import Redis

from backend.extensions.metrics.writer import MetricsWriter
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
