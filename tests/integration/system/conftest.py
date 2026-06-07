from __future__ import annotations

from typing import Any, Generator, Tuple

import pytest
from flask import Flask
from flask.testing import FlaskCliRunner
from redis import Redis

from backend import metrics_writer as app_metrics_writer
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


@pytest.fixture
def metrics_enabled_runner_app(
    runner: Tuple[Flask, FlaskCliRunner],
    provide_metrics_redis: Redis,
) -> Generator[Flask, None, None]:
    """Activate the metrics_writer extension on the `runner` fixture's app.

    The `runner` fixture is required (instead of the `app` fixture) because
    callers of this fixture typically call into `sync_event_registry(...)`,
    `run_flush(...)`, or seed `AnonymousMetrics` rows via raw psycopg2 — all
    of which open their own DB transactions. The `app` fixture wraps every
    test in a SAVEPOINT and rolls back at teardown, which deadlocks when an
    inline psycopg2 connection writes rows the SAVEPOINT-bound session
    cannot see (and vice versa). `runner` uses `clear_database` teardown
    instead, so inline psycopg2 + SQLAlchemy can coexist.

    Mutates the module-level `metrics_writer` singleton in place (rather
    than swapping a fresh instance) so the route's
    `from backend import metrics_writer` import and the proxy's
    `current_app.extensions["metrics_writer"]` lookup both resolve to the
    same writer that this fixture has just enabled.
    """
    app = runner[0]

    original_metrics_enabled = app.config.get(CONFIG_ENVS.METRICS_ENABLED, False)
    original_redis = app_metrics_writer._redis
    original_enabled = app_metrics_writer._enabled

    app.config[CONFIG_ENVS.METRICS_ENABLED] = True
    app_metrics_writer.init_app(app)

    yield app

    app.config[CONFIG_ENVS.METRICS_ENABLED] = original_metrics_enabled
    app_metrics_writer._redis = original_redis
    app_metrics_writer._enabled = original_enabled
