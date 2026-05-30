from __future__ import annotations

import time
from typing import Any

from redis import Redis
from selenium.webdriver.remote.webdriver import WebDriver

from backend.metrics.events import EventName
from scripts.flush_metrics import FLUSH_LOCK_KEY, run_flush

# Postgres poll cadence inside `wait_for_metrics_row`. The metrics-client's
# `flushBeacon()` request goes out asynchronously, so we poll Postgres with
# periodic server-side `run_flush` calls until the row materializes.
_POLL_INTERVAL_SECONDS: float = 0.2
_DEFAULT_TIMEOUT_SECONDS: float = 10.0

# Short settling delay after we dispatch the `pagehide` event. Gives the
# browser time to enqueue the `navigator.sendBeacon` request (or its
# `fetch keepalive` fallback) before we begin polling Postgres.
_BEACON_SETTLE_SECONDS: float = 0.3

# JS dispatched by `_trigger_metrics_flush_via_pagehide`. Synthesizes a real
# `PageTransitionEvent("pagehide")` on `window` — the metrics-client's
# `_onPageHide` listener (registered by `initMetricsClient` in
# `frontend/lib/metrics-client.ts`) runs synchronously, calls `flushBeacon`,
# which dispatches `navigator.sendBeacon` (or a `fetch keepalive` fallback)
# to `/api/metrics`. Unlike `visibilitychange`, the `pagehide` listener is
# NOT gated against the browser's internal page-hidden state, so a
# synthesized event with the correct constructor fires the listener reliably
# even under headless Chrome via Selenium. The page stays alive after the
# dispatch (no real navigation), so the beacon flight has the full network
# stack available and is guaranteed to land.
_DISPATCH_PAGEHIDE_JS: str = """
const done = arguments[arguments.length - 1];
try {
    const pageHideEvent = new PageTransitionEvent("pagehide", {
        persisted: false,
        bubbles: false,
        cancelable: false,
    });
    window.dispatchEvent(pageHideEvent);
    done("dispatched");
} catch (err) {
    done("error: " + String(err));
}
"""


def _trigger_metrics_flush_via_pagehide(browser: WebDriver) -> None:
    """Force the metrics-client's `pagehide` -> `flushBeacon()` path.

    Synthesizes a real `PageTransitionEvent("pagehide")` on the page's
    `window` via `dispatchEvent`. The metrics-client's `_onPageHide`
    listener (registered in `initMetricsClient`) calls `flushBeacon`,
    which dispatches `navigator.sendBeacon` (or a `fetch keepalive`
    fallback) to `/api/metrics` — the same module instance the production
    code uses.

    Why this works where `visibilitychange` does not: Chromium gates the
    page-visibility listener against the browser's internal hidden state,
    so a synthesized `visibilitychange` event fires the listener but
    `document.visibilityState` is still "visible" and the listener short-
    circuits. The `pagehide` listener has no such gate — it runs on the
    raw event regardless of the browser's internal navigation state.

    Why this is preferred over real navigation: a real `browser.get(...)`
    tears down the page context, which under headless Chrome has been
    observed to abort the in-flight `sendBeacon` before it leaves the
    process. Keeping the page alive after dispatch lets the beacon
    complete normally.

    After dispatching, sleeps briefly so the async sendBeacon request can
    be flushed onto the wire before the test starts polling Postgres.
    """
    dispatch_result = browser.execute_async_script(_DISPATCH_PAGEHIDE_JS)
    if dispatch_result != "dispatched":
        raise RuntimeError(
            f"_trigger_metrics_flush_via_pagehide: dispatch failed: "
            f"{dispatch_result!r}"
        )
    time.sleep(_BEACON_SETTLE_SECONDS)


def query_anonymous_metrics_rows(
    pg_conn: Any, event_name: str | None = None
) -> list[dict[str, Any]]:
    """Return `AnonymousMetrics` rows (filtered by `event_name` if provided).

    Returns a list of dicts (`event_name`, `dimensions`, `count`,
    `bucket_start`) so call sites can assert on individual fields without
    unpacking opaque tuples. Uses a fresh cursor so the conn's transaction
    state is unchanged after the read.
    """
    query = (
        'SELECT "eventName", "dimensions", "count", "bucketStart"'
        ' FROM "AnonymousMetrics"'
    )
    params: tuple[Any, ...] = ()
    if event_name is not None:
        query += ' WHERE "eventName" = %s'
        params = (event_name,)
    query += " ORDER BY id"

    with pg_conn.cursor() as cursor:
        cursor.execute(query, params)
        raw_rows = cursor.fetchall()

    return [
        {
            "event_name": row[0],
            "dimensions": row[1],
            "count": row[2],
            "bucket_start": row[3],
        }
        for row in raw_rows
    ]


def wait_for_metrics_row(
    browser: WebDriver,
    redis_client: Redis,
    pg_conn: Any,
    event_name: EventName,
    expected_dimensions: dict[str, Any],
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Trigger a real metrics-client flush, then poll Postgres for the row.

    1. Synthesize a `PageTransitionEvent("pagehide")` on `window` via
       `dispatchEvent`. The metrics-client's `_onPageHide` listener
       (registered by `initMetricsClient` in
       `frontend/lib/metrics-client.ts`) calls `flushBeacon`, which
       dispatches a `navigator.sendBeacon` (or `fetch keepalive` fallback)
       to `/api/metrics` from the same module instance production code
       uses.
    2. Pre-warm the psycopg2 connection's view of `EventRegistry`. The
       connection is opened in the autouse fixture's body, immediately
       after `sync_event_registry(provide_app)` commits the enum rows —
       but the conn's first FK lookup against EventRegistry has been
       observed to use a stale snapshot (likely a Postgres txn-id ordering
       artifact where the conn's implicit txn started before the commit
       from the SQLAlchemy session became visible). An explicit SELECT
       here forces the conn to resolve the table, and subsequent FK checks
       during `run_flush` see all rows.
    3. Poll Postgres with periodic `run_flush` calls: in a loop with a
       short sleep, drop the distributed flush lock (safe per-worker
       isolation; see below), run `run_flush` once, query
       `AnonymousMetrics` for the expected event+dimensions, return on
       match, retry on miss, time out after `timeout_seconds`.

    The flush lock drop is safe in this scope: each xdist worker owns its
    own metrics-Redis DB (per `worker_metrics_redis_uri`), so the worker's
    lock namespace is never shared with the workflow cron (DB 0) or with
    peer workers.

    On timeout, raises `AssertionError` with a diagnostic dump of every
    row currently in `AnonymousMetrics` for this event. The most likely
    cause of a timeout is a regression in the metrics-client's flush
    plumbing: either the gesture's `emit()` call no longer buffers the
    event, or the `pagehide` listener registration in
    `initMetricsClient` was broken, or `flushBeacon` no longer dispatches
    the `sendBeacon`/`fetch keepalive` request.
    """
    _trigger_metrics_flush_via_pagehide(browser)

    with pg_conn.cursor() as cursor:
        cursor.execute(
            'SELECT 1 FROM "EventRegistry" WHERE name = %s LIMIT 1',
            (event_name.value,),
        )
        registry_row = cursor.fetchone()
    if registry_row is None:
        raise AssertionError(
            f"wait_for_metrics_row: EventRegistry has no row for "
            f"event_name={event_name.value!r}; sync_event_registry never "
            "ran or the test DB was cleared between fixture setup and "
            "assertion. Check the order of `clear_metrics_state` vs the "
            "parent `browser` fixture's `clear_db` call."
        )

    deadline = time.monotonic() + timeout_seconds
    last_rows: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        redis_client.delete(FLUSH_LOCK_KEY)
        run_flush(redis_client=redis_client, pg_conn=pg_conn)
        last_rows = query_anonymous_metrics_rows(pg_conn, event_name=event_name.value)
        for row in last_rows:
            if row["dimensions"] == expected_dimensions:
                return row
        time.sleep(_POLL_INTERVAL_SECONDS)

    raise AssertionError(
        f"wait_for_metrics_row: no AnonymousMetrics row for "
        f"event={event_name.value!r} matched dimensions="
        f"{expected_dimensions!r} after the flush trigger (synthesized "
        f"`pagehide` event) and {timeout_seconds:.1f}s of polling with "
        f"periodic run_flush. This typically means the metrics-client "
        f"never POSTed the event (regression in flush plumbing) or the "
        f"route rejected the payload. All rows currently present for this "
        f"event: {last_rows!r}"
    )
