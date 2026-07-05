from __future__ import annotations

from typing import Any, Generator, Tuple

import psycopg2
import pytest
from flask import Flask
from flask.testing import FlaskCliRunner
from redis import Redis

from backend import metrics_writer as app_metrics_writer
from backend.config import ConfigTest
from backend.extensions.metrics.registry_sync import sync_event_registry
from backend.utils.strings.metrics_strs import METRICS_REDIS
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.ui_test_setup import ping_server


def _build_pg_conn(app: Flask) -> Any:
    """Open a fresh psycopg2 connection to the same DB the test Flask uses.

    Functional tests do not wrap test bodies in a SAVEPOINT (unlike the
    integration `app` fixture), so an inline psycopg2 connection can safely
    coexist with the SQLAlchemy session that the Flask thread uses to serve
    requests. Mirrors the pattern in `tests/integration/system/
    test_metrics_pipeline_e2e.py`.
    """
    return psycopg2.connect(app.config["SQLALCHEMY_DATABASE_URI"])


@pytest.fixture(scope="session")
def metrics_redis_client(
    worker_metrics_redis_uri: str,
) -> Generator[Redis, None, None]:
    """Per-worker `redis-metrics` client.

    Per-worker isolation is inherited from the existing session-scoped
    `worker_metrics_redis_uri` fixture in `tests/conftest.py`, which assigns
    each xdist worker a dedicated DB index in the range
    `_METRICS_REDIS_DB_BASE..(_METRICS_REDIS_DB_BASE + n_workers - 1)`. With the
    documented UI parallelism cap of `n=8`, the highest assigned index is 15 —
    inside the dedicated container's default 16-database limit (indices 0..15).

    Skips the test session when the metrics Redis is unavailable
    (`memory://`), matching how `provide_metrics_redis` short-circuits in the
    integration suite.
    """
    if not worker_metrics_redis_uri or worker_metrics_redis_uri == "memory://":
        pytest.skip("metrics Redis is unavailable; skipping metrics UI test")
    client = Redis.from_url(worker_metrics_redis_uri)
    yield client
    try:
        client.close()
    except Exception:
        pass


@pytest.fixture(scope="session")
def metrics_enabled_for_ui(
    metrics_redis_client: Redis,
    parallelize_app: None,
    provide_app: Flask,
    provide_port: int,
    build_app: Tuple[Flask, Any],
) -> Generator[None, None, None]:
    """Activate the module-level `metrics_writer` singleton for the lifetime
    of the test session.

    The functional stack runs Flask in a background thread spawned by
    `parallelize_app`; the route handler imports `from backend import
    metrics_writer`, which resolves to the same module-level singleton this
    fixture mutates. Mutating `_enabled` and `_redis` in place (rather than
    swapping a fresh instance) ensures both the route's direct reference and
    the `current_app.extensions["metrics_writer"]` lookup see the activated
    writer pointed at this worker's dedicated metrics-Redis DB.

    The explicit `parallelize_app` + `provide_app` + `build_app` dependencies
    guarantee every `create_app(...) -> metrics_writer.init_app(app)` call in
    the functional stack has already run by the time we flip the singleton.
    `ping_server(...)` then blocks until the background Flask thread's
    `create_app` (which mutates the same singleton) has finished serving its
    first 200 — without it, `parallelize_app`'s fixed `sleep(5)` can race the
    thread's import-heavy startup and the `init_app` call inside the thread
    silently reverts `_enabled` back to `False` from the app config moments
    after we set it to `True`.

    Session-scoped so the per-test cost is zero — clearing happens via the
    `clear_metrics_state` fixture below (requested explicitly by each
    metrics-validation test, not autouse — so non-metrics UI tests in the
    same domain do not pay the setup cost).
    """
    docker_or_localhost_base_url = (
        UI_TEST_STRINGS.DOCKER_BASE_URL
        if ConfigTest.DOCKER
        else UI_TEST_STRINGS.BASE_URL
    )
    flask_thread_ready = ping_server(docker_or_localhost_base_url + str(provide_port))
    assert flask_thread_ready, (
        "metrics_enabled_for_ui: background Flask thread did not respond to "
        "ping before timeout; metrics_writer.init_app would race the flip."
    )
    original_redis = app_metrics_writer._redis
    original_enabled = app_metrics_writer._enabled

    app_metrics_writer._redis = metrics_redis_client
    app_metrics_writer._enabled = True

    yield

    app_metrics_writer._redis = original_redis
    app_metrics_writer._enabled = original_enabled


@pytest.fixture(scope="session")
def metrics_registry_synced(
    provide_app: Flask,
    parallelize_app: None,
    metrics_enabled_for_ui: None,
) -> Flask:
    """Hand the session-scoped Flask app to the per-test sync.

    `AnonymousMetrics."eventName"` has a FK to `EventRegistry."name"`, so a
    flush UPSERT fails unless every `EventName` value has a row. The
    functional page fixtures invoke `clear_db(runner, ...)` between
    tests, which `flask managedb clear test` resolves to `meta.drop_all() +
    meta.create_all()` — wiping EventRegistry along with everything else.
    The actual sync must therefore happen **after** `clear_db` runs, inside
    the per-test `clear_metrics_state` fixture below. This session-scoped
    fixture only exposes `provide_app` to it.
    """
    return provide_app


def _reset_metrics_state_for_test(
    provide_app: Flask,
    metrics_redis_client: Redis,
) -> None:
    """Shared reset implementation invoked by both desktop + mobile fixtures.

    Pulled out as a helper so the same logic can run in two fixture
    variants — one ordered after the desktop page chain, one ordered
    after the mobile `page_mobile_portrait` chain — without forcing both
    page chains to spin up.

    - UNLINK every `metrics:counter:*` and `metrics:batch:*` key — the same
      keys touched by `make metrics-clear-counters`.
    - TRUNCATE `AnonymousMetrics` so post-flush rows from prior tests do not
      bleed into the current test's row count.
    - Re-sync `EventRegistry` to populate the parent table the FK on
      `AnonymousMetrics."eventName"` references. The `browser` fixture's
      `clear_db(runner, ...)` step calls `flask managedb clear test` which
      drops and recreates **every** table — wiping the EventRegistry rows
      a previous test populated. Without the re-sync, the first test
      passes and every subsequent test hits a FK violation when the route
      tries to UPSERT.

    The flush distributed lock (`metrics:flush:lock`) and liveness sentinel
    are intentionally left intact; tests that need to flush will overwrite
    or expire them naturally.
    """
    counter_keys = list(
        metrics_redis_client.scan_iter(match=f"{METRICS_REDIS.COUNTER_KEY_PREFIX}*")
    )
    if counter_keys:
        metrics_redis_client.unlink(*counter_keys)
    batch_keys = list(
        metrics_redis_client.scan_iter(match=f"{METRICS_REDIS.BATCH_KEY_PREFIX}*")
    )
    if batch_keys:
        metrics_redis_client.unlink(*batch_keys)

    cleanup_conn = _build_pg_conn(provide_app)
    try:
        with cleanup_conn.cursor() as cursor:
            cursor.execute('TRUNCATE TABLE "AnonymousMetrics" RESTART IDENTITY')
        cleanup_conn.commit()
    finally:
        cleanup_conn.close()

    # Populate EventRegistry — must run AFTER `clear_db` (parent browser
    # fixture chain) and BEFORE the test body's emit POST. See docstring
    # for the drop_all/create_all explanation.
    sync_event_registry(provide_app)

    # Sanity check: the route handler's `record_event` proxy resolves the
    # writer via `current_app.extensions["metrics_writer"]`. Confirm the same
    # singleton both apps registered now reports enabled with our worker's
    # Redis client. Failing here means the fixture order is wrong and tests
    # will silently produce empty counter namespaces.
    assert app_metrics_writer._enabled, (
        "metrics_writer singleton is disabled at test entry — fixture order"
        " regression: metrics_enabled_for_ui must run before any UI gesture."
    )
    assert (
        app_metrics_writer._redis is metrics_redis_client
    ), "metrics_writer._redis is not pointed at the worker's test Redis DB"


@pytest.fixture
def clear_metrics_state(
    provide_app: Flask,
    metrics_redis_client: Redis,
    metrics_registry_synced: Flask,
    runner: Tuple[Flask, FlaskCliRunner],
    page_without_cookie_banner_cookie: Any,
) -> Generator[None, None, None]:
    """Reset metrics state before every desktop metrics-validation test.

    Requested explicitly by desktop metrics tests (NOT autouse) so that
    non-metrics UI tests in the same domain marker do not pay the
    EventRegistry resync cost.

    `runner` and `page_without_cookie_banner_cookie` are requested
    explicitly so `clear_db` (executed inside the page fixture's setup)
    runs strictly **before** this fixture's body, not after — otherwise
    the in-fixture sync runs and then `clear_db` wipes EventRegistry, and
    the test body's UPSERT fails the FK check.

    Mobile tests use `clear_metrics_state_mobile` instead so the desktop
    page chain is never instantiated for a mobile-viewport test.
    """
    _reset_metrics_state_for_test(provide_app, metrics_redis_client)
    yield


@pytest.fixture
def clear_metrics_state_mobile(
    provide_app: Flask,
    metrics_redis_client: Redis,
    metrics_registry_synced: Flask,
    runner: Tuple[Flask, FlaskCliRunner],
    page_mobile_portrait_without_cookie_banner_cookie: Any,
) -> Generator[None, None, None]:
    """Mobile-viewport variant of `clear_metrics_state`.

    Identical behavior to `clear_metrics_state` (see its docstring) but
    orders itself after the mobile page fixture chain instead of the
    desktop one, so a mobile test never triggers a desktop context setup.
    """
    _reset_metrics_state_for_test(provide_app, metrics_redis_client)
    yield


@pytest.fixture
def pg_conn_for_metrics(
    provide_app: Flask,
    clear_metrics_state: None,
) -> Generator[Any, None, None]:
    """Per-test psycopg2 connection used for both `run_flush` and assertions.

    Desktop variant — ordered after `clear_metrics_state`. Reusing one
    connection per test keeps the flushed rows and the assertion `SELECT`
    inside the same transactional view, avoiding read-after-write races
    where the assertion runs before the UPSERT commit is visible.

    Explicit `clear_metrics_state` dependency guarantees the connection is
    opened **after** EventRegistry has been re-synced. Without this, the
    conn's first implicit transaction can snapshot EventRegistry as empty
    (clear_db dropped/recreated it but the sync hasn't run yet), and a later
    UPSERT in the same transaction fails the FK check even though
    sync_event_registry has committed.
    """
    pg_conn = _build_pg_conn(provide_app)
    try:
        yield pg_conn
    finally:
        pg_conn.close()


@pytest.fixture
def pg_conn_for_metrics_mobile(
    provide_app: Flask,
    clear_metrics_state_mobile: None,
) -> Generator[Any, None, None]:
    """Mobile-viewport variant of `pg_conn_for_metrics`."""
    pg_conn = _build_pg_conn(provide_app)
    try:
        yield pg_conn
    finally:
        pg_conn.close()
