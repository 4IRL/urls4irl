from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Tuple
from unittest.mock import patch
from urllib.parse import quote, urlsplit

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient

import backend.admin.health_service as health_service
from backend import db
from backend.admin.health_service import (
    STATUS_DOWN,
    STATUS_UP,
    SystemResources,
    _probe_system_resources,
    collect_health_snapshot,
)
from backend.metrics.events import EventCategory, EventName
from backend.metrics.latency import LatencyMetricName
from backend.models.anonymous_latency_samples import Anonymous_Latency_Samples
from backend.models.anonymous_metrics import Anonymous_Metrics
from backend.models.audit_log import AuditLog
from backend.models.event_registry import Event_Registry
from backend.models.users import Users
from backend.utils.all_routes import ADMIN_ROUTES
from backend.utils.strings.admin_portal_strs import (
    ADMIN_AUDIT_ACTIONS,
    ADMIN_PORTAL_STRINGS,
)

pytestmark = pytest.mark.admin

_ADMIN_HEALTH_URL: str = "/admin/health"
_ADMIN_HEALTH_SNAPSHOT_URL: str = "/admin/health/snapshot"
_HEALTH_TITLE_BYTES: bytes = ADMIN_PORTAL_STRINGS.HEALTH_TITLE.encode()
_SNAPSHOT_REGION_ID_BYTES: bytes = b'id="AdminHealthSnapshot"'
_HEALTH_GRID_ID_BYTES: bytes = b'id="AdminHealthGrid"'
_STATUS_UP_BYTES: bytes = STATUS_UP.encode()

_API_HIT_EVENT_DESCRIPTION: str = "Seeded api_hit event for health snapshot tests."
_SLOW_ENDPOINT: str = "utubs.slow_endpoint"
_FAST_ENDPOINT: str = "utubs.fast_endpoint"
_BUSY_ENDPOINT: str = "utubs.busy_endpoint"
_QUIET_ENDPOINT: str = "utubs.quiet_endpoint"
_GET_METHOD: str = "GET"
_POST_METHOD: str = "POST"
_MISSING_MEMINFO_PATH: str = "/proc/definitely-not-a-real-meminfo-file"


def _ensure_api_hit_event_registered() -> None:
    """Insert the api_hit EventRegistry row if absent (FK target for metrics)."""
    already_registered = (
        Event_Registry.query.filter_by(name=EventName.API_HIT.value).one_or_none()
        is not None
    )
    if already_registered:
        return
    db.session.add(
        Event_Registry(
            name=EventName.API_HIT.value,
            category=EventCategory.API,
            description=_API_HIT_EVENT_DESCRIPTION,
        )
    )
    db.session.flush()


def _seed_api_hit(
    *,
    bucket_start: datetime,
    count: int,
    endpoint: str,
    method: str,
    status_code: int,
) -> None:
    """Seed one api_hit AnonymousMetrics row through SQLAlchemy.

    Each row uses a distinct ``bucket_start`` because the table's unique
    constraint is (bucketStart, eventName, dimensions) — the promoted
    endpoint/method/status_code columns are not part of it, so two same-bucket
    rows with empty dimensions would collide.
    """
    _ensure_api_hit_event_registered()
    db.session.add(
        Anonymous_Metrics(
            event_name=EventName.API_HIT.value,
            bucket_start=bucket_start,
            dimensions={},
            count=count,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
        )
    )
    db.session.commit()


def _seed_latency_sample(
    *,
    observed_at: datetime,
    duration_ms: float,
    endpoint: str,
    method: str,
) -> None:
    """Seed one AnonymousLatencySamples row through SQLAlchemy."""
    db.session.add(
        Anonymous_Latency_Samples(
            metric_name=LatencyMetricName.API_REQUEST_DURATION.value,
            endpoint=endpoint,
            method=method,
            observed_at=observed_at,
            duration_ms=duration_ms,
            dimensions={},
        )
    )
    db.session.commit()


def test_admin_health_page_renders_for_admin(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user
    WHEN the admin sends GET /admin/health
    THEN the response is 200 HTML containing the health title text and the
         AdminHealthSnapshot element id.
    """
    client, _, _, app = login_admin_user_with_register

    with app.test_request_context():
        admin_health_url = url_for(ADMIN_ROUTES.HEALTH_PAGE)

    response = client.get(admin_health_url)

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert _HEALTH_TITLE_BYTES in response.data
    assert _SNAPSHOT_REGION_ID_BYTES in response.data


def test_admin_health_page_creates_audit_log_row(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an empty AuditLogs table and a logged-in admin user
    WHEN the admin sends GET /admin/health
    THEN exactly one AuditLog row is created with action == HEALTH_VIEW
         and actor_id == the admin's user id.
    """
    client, _, admin_user, app = login_admin_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    client.get(_ADMIN_HEALTH_URL)

    with app.app_context():
        rows_after: int = AuditLog.query.count()
        assert rows_after == 1
        audit_row: AuditLog | None = AuditLog.query.first()
        assert audit_row is not None
        assert audit_row.action == ADMIN_AUDIT_ACTIONS.HEALTH_VIEW
        assert audit_row.actor_id == admin_user.id


def test_admin_health_snapshot_renders_for_admin(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user
    WHEN the admin sends GET /admin/health/snapshot
    THEN the response is 200 HTML containing the AdminHealthGrid id and the
         "up" status string for the database card.
    """
    client, _, _, app = login_admin_user_with_register

    with app.test_request_context():
        snapshot_url = url_for(ADMIN_ROUTES.HEALTH_SNAPSHOT)

    response = client.get(snapshot_url)

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert _HEALTH_GRID_ID_BYTES in response.data
    assert _STATUS_UP_BYTES in response.data


def test_admin_health_snapshot_creates_no_audit_log_row(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an empty AuditLogs table and a logged-in admin user
    WHEN the admin sends GET /admin/health/snapshot
    THEN no AuditLog rows are created (the snapshot endpoint is deliberately
         not audited to avoid flooding the audit log on each 30s poll).
    """
    client, _, _, app = login_admin_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    client.get(_ADMIN_HEALTH_SNAPSHOT_URL)

    with app.app_context():
        rows_after: int = AuditLog.query.count()
    assert rows_after == 0


def test_collect_health_snapshot_returns_database_up(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a running test app with a reachable Postgres database
    WHEN collect_health_snapshot() is called directly inside the app context
    THEN database_status == STATUS_UP, database_connection_count is an int
         >= 1, and captured_at is a timezone-aware datetime.
    """
    _, _, _, app = login_admin_user_with_register

    with app.app_context():
        snapshot = collect_health_snapshot()

    assert snapshot.database_status == STATUS_UP
    assert isinstance(snapshot.database_connection_count, int)
    assert snapshot.database_connection_count >= 1
    assert snapshot.captured_at.tzinfo is not None


def test_collect_health_snapshot_degrades_on_database_error(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a running test app where the database probe raises an exception
    WHEN collect_health_snapshot() is called directly inside the app context
    THEN database_status == STATUS_DOWN, database_connection_count is None,
         and the function does NOT raise.
    """
    _, _, _, app = login_admin_user_with_register

    with app.app_context():
        with patch(
            "backend.admin.health_service.db.session.execute",
            side_effect=Exception("simulated database error"),
        ):
            snapshot = collect_health_snapshot()

    assert snapshot.database_status == STATUS_DOWN
    assert snapshot.database_connection_count is None


def test_admin_health_page_returns_403_for_non_admin(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in non-admin user
    WHEN the user sends GET /admin/health
    THEN the response is 403 Forbidden and no AuditLog row is created.
    """
    client, _, _, app = login_first_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = client.get(_ADMIN_HEALTH_URL)

    assert response.status_code == 403

    with app.app_context():
        rows_after: int = AuditLog.query.count()
    assert rows_after == 0


def test_admin_health_snapshot_returns_403_for_non_admin(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in non-admin user
    WHEN the user sends GET /admin/health/snapshot
    THEN the response is 403 Forbidden.
    """
    client, _, _, _ = login_first_user_with_register

    response = client.get(_ADMIN_HEALTH_SNAPSHOT_URL)

    assert response.status_code == 403


def test_admin_health_page_redirects_anonymous_to_splash(
    client: FlaskClient,
) -> None:
    """
    GIVEN an anonymous (unauthenticated) browser session
    WHEN the client sends GET /admin/health
    THEN the response is 302 and redirects away from /admin/health
         (to the login page) with the original path in the `next` parameter.
    """
    response = client.get(_ADMIN_HEALTH_URL)

    assert response.status_code == 302
    assert response.location is not None

    redirect_path = urlsplit(response.location).path
    assert not redirect_path.startswith("/admin")

    encoded_next = quote(_ADMIN_HEALTH_URL, safe="")
    raw_next = _ADMIN_HEALTH_URL
    assert (
        f"next={encoded_next}" in response.location
        or f"next={raw_next}" in response.location
    )


def test_admin_health_snapshot_redirects_anonymous_to_splash(
    client: FlaskClient,
) -> None:
    """
    GIVEN an anonymous (unauthenticated) browser session
    WHEN the client sends GET /admin/health/snapshot
    THEN the response is 302 and redirects away from /admin.
    """
    response = client.get(_ADMIN_HEALTH_SNAPSHOT_URL)

    assert response.status_code == 302
    assert response.location is not None

    redirect_path = urlsplit(response.location).path
    assert not redirect_path.startswith("/admin")


def test_collect_health_snapshot_slowest_endpoint(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN latency samples for two endpoints, one clearly slower, inside the
          7-day (raw-retention) window
    WHEN collect_health_snapshot() is called
    THEN slowest_endpoint identifies the slow endpoint/method, p95_ms > 0, and
         the result is exact (approximate is False) since samples are recent.
    """
    _, _, _, app = login_admin_user_with_register

    with app.app_context():
        snapshot_before = collect_health_snapshot()
        assert snapshot_before.slowest_endpoint is None

        observed_at = datetime.now(timezone.utc) - timedelta(days=1)
        for _ in range(5):
            _seed_latency_sample(
                observed_at=observed_at,
                duration_ms=25.0,
                endpoint=_FAST_ENDPOINT,
                method=_GET_METHOD,
            )
            _seed_latency_sample(
                observed_at=observed_at,
                duration_ms=900.0,
                endpoint=_SLOW_ENDPOINT,
                method=_POST_METHOD,
            )
        snapshot = collect_health_snapshot()

    assert snapshot.slowest_endpoint is not None
    assert snapshot.slowest_endpoint.endpoint == _SLOW_ENDPOINT
    assert snapshot.slowest_endpoint.method == _POST_METHOD
    assert snapshot.slowest_endpoint.p95_ms > 0
    assert not snapshot.slowest_endpoint.approximate


def test_collect_health_snapshot_error_rate_with_traffic(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN api_hit rows in the last 24h with mixed status codes, 3 of 10 being 5xx
    WHEN collect_health_snapshot() is called
    THEN error_rate reports error_count=3, total_count=10, rate=0.3.
    """
    _, _, _, app = login_admin_user_with_register

    with app.app_context():
        snapshot_before = collect_health_snapshot()
        assert snapshot_before.error_rate is not None
        assert snapshot_before.error_rate.total_count == 0

        now = datetime.now(timezone.utc)
        _seed_api_hit(
            bucket_start=now - timedelta(hours=1),
            count=7,
            endpoint=_BUSY_ENDPOINT,
            method=_GET_METHOD,
            status_code=200,
        )
        _seed_api_hit(
            bucket_start=now - timedelta(hours=2),
            count=3,
            endpoint=_BUSY_ENDPOINT,
            method=_GET_METHOD,
            status_code=500,
        )
        snapshot = collect_health_snapshot()

    assert snapshot.error_rate is not None
    assert snapshot.error_rate.total_count == 10
    assert snapshot.error_rate.error_count == 3
    assert snapshot.error_rate.rate == pytest.approx(0.3)


def test_collect_health_snapshot_error_rate_zero_traffic(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN no api_hit traffic in the window
    WHEN collect_health_snapshot() is called
    THEN error_rate is present with total_count=0 and rate=0.0 (no divide-by-zero).
    """
    _, _, _, app = login_admin_user_with_register

    with app.app_context():
        snapshot = collect_health_snapshot()

    assert snapshot.error_rate is not None
    assert snapshot.error_rate.total_count == 0
    assert snapshot.error_rate.error_count == 0
    assert snapshot.error_rate.rate == 0.0


def test_collect_health_snapshot_busiest_endpoint(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN api_hit counts split across two endpoints in the last 24h
    WHEN collect_health_snapshot() is called
    THEN busiest_endpoint identifies the higher-volume endpoint/method and count.
    """
    _, _, _, app = login_admin_user_with_register

    with app.app_context():
        snapshot_before = collect_health_snapshot()
        assert snapshot_before.busiest_endpoint is None

        now = datetime.now(timezone.utc)
        _seed_api_hit(
            bucket_start=now - timedelta(hours=1),
            count=100,
            endpoint=_BUSY_ENDPOINT,
            method=_GET_METHOD,
            status_code=200,
        )
        _seed_api_hit(
            bucket_start=now - timedelta(hours=2),
            count=5,
            endpoint=_QUIET_ENDPOINT,
            method=_POST_METHOD,
            status_code=200,
        )
        snapshot = collect_health_snapshot()

    assert snapshot.busiest_endpoint is not None
    assert snapshot.busiest_endpoint.endpoint == _BUSY_ENDPOINT
    assert snapshot.busiest_endpoint.method == _GET_METHOD
    assert snapshot.busiest_endpoint.hit_count == 100


def test_collect_health_snapshot_database_max_connections(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a reachable Postgres that answers SHOW max_connections
    WHEN collect_health_snapshot() is called
    THEN database_max_connections is a positive int.
    """
    _, _, _, app = login_admin_user_with_register

    with app.app_context():
        snapshot = collect_health_snapshot()

    assert isinstance(snapshot.database_max_connections, int)
    assert snapshot.database_max_connections > 0


def test_collect_health_snapshot_flush_lag_fresh(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a flush sentinel timestamp inside the stale threshold
    WHEN collect_health_snapshot() is called
    THEN flush_lag_seconds reflects the recent age and flush_is_stale is False.
    """
    _, _, _, app = login_admin_user_with_register
    fresh_flush_at = datetime.now(timezone.utc) - timedelta(seconds=60)

    with app.app_context():
        with patch.object(
            health_service,
            "_probe_metrics_redis",
            return_value=(STATUS_UP, fresh_flush_at, None, None),
        ):
            snapshot = collect_health_snapshot()

    assert snapshot.flush_lag_seconds is not None
    assert 50 <= snapshot.flush_lag_seconds <= 180
    assert not snapshot.flush_is_stale


def test_collect_health_snapshot_flush_lag_stale(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a flush sentinel timestamp older than the stale threshold
    WHEN collect_health_snapshot() is called
    THEN flush_lag_seconds exceeds the threshold and flush_is_stale is True.
    """
    _, _, _, app = login_admin_user_with_register
    stale_flush_at = datetime.now(timezone.utc) - timedelta(
        seconds=health_service._FLUSH_STALE_THRESHOLD_SECONDS + 300
    )

    with app.app_context():
        with patch.object(
            health_service,
            "_probe_metrics_redis",
            return_value=(STATUS_UP, stale_flush_at, None, None),
        ):
            snapshot = collect_health_snapshot()

    assert snapshot.flush_lag_seconds is not None
    assert snapshot.flush_lag_seconds > health_service._FLUSH_STALE_THRESHOLD_SECONDS
    assert snapshot.flush_is_stale


def test_collect_health_snapshot_flush_lag_none_when_no_sentinel(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN no flush sentinel timestamp (metrics Redis reports None)
    WHEN collect_health_snapshot() is called
    THEN flush_lag_seconds is None and flush_is_stale is False.
    """
    _, _, _, app = login_admin_user_with_register

    with app.app_context():
        with patch.object(
            health_service,
            "_probe_metrics_redis",
            return_value=(STATUS_DOWN, None, None, None),
        ):
            snapshot = collect_health_snapshot()

    assert snapshot.flush_lag_seconds is None
    assert not snapshot.flush_is_stale


def test_collect_health_snapshot_backup_lag_fresh(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a backup sentinel timestamp inside the 26-hour stale threshold
    WHEN collect_health_snapshot() is called
    THEN backup_lag_seconds reflects the recent age and backup_is_stale is False.
    """
    _, _, _, app = login_admin_user_with_register
    fresh_backup_at = datetime.now(timezone.utc) - timedelta(hours=3)

    with app.app_context():
        with patch.object(
            health_service,
            "_probe_metrics_redis",
            return_value=(STATUS_UP, None, None, fresh_backup_at),
        ):
            snapshot = collect_health_snapshot()

    assert snapshot.backup_last_success_at == fresh_backup_at
    assert snapshot.backup_lag_seconds is not None
    assert snapshot.backup_lag_seconds < health_service._BACKUP_STALE_THRESHOLD_SECONDS
    assert not snapshot.backup_is_stale


def test_collect_health_snapshot_backup_lag_stale(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a backup sentinel timestamp older than the 26-hour stale threshold
    WHEN collect_health_snapshot() is called
    THEN backup_lag_seconds exceeds the threshold and backup_is_stale is True.
    """
    _, _, _, app = login_admin_user_with_register
    stale_backup_at = datetime.now(timezone.utc) - timedelta(
        seconds=health_service._BACKUP_STALE_THRESHOLD_SECONDS + 3600
    )

    with app.app_context():
        with patch.object(
            health_service,
            "_probe_metrics_redis",
            return_value=(STATUS_UP, None, None, stale_backup_at),
        ):
            snapshot = collect_health_snapshot()

    assert snapshot.backup_lag_seconds is not None
    assert snapshot.backup_lag_seconds > health_service._BACKUP_STALE_THRESHOLD_SECONDS
    assert snapshot.backup_is_stale


def test_collect_health_snapshot_backup_none_when_no_sentinel(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN no backup sentinel timestamp (never stamped)
    WHEN collect_health_snapshot() is called
    THEN backup fields are None/False so the dashboard renders "never".
    """
    _, _, _, app = login_admin_user_with_register

    with app.app_context():
        with patch.object(
            health_service,
            "_probe_metrics_redis",
            return_value=(STATUS_UP, None, None, None),
        ):
            snapshot = collect_health_snapshot()

    assert snapshot.backup_last_success_at is None
    assert snapshot.backup_lag_seconds is None
    assert not snapshot.backup_is_stale


def test_probe_system_resources_returns_values_or_none(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN the Linux test container exposing /proc/meminfo and getloadavg
    WHEN _probe_system_resources() is called
    THEN it returns either a SystemResources within sane bounds, or None
         (never raising) if /proc is unavailable.
    """
    _, _, _, app = login_admin_user_with_register

    with app.app_context():
        resources = _probe_system_resources()

    if resources is None:
        return
    assert isinstance(resources, SystemResources)
    assert 0 <= resources.memory_used_percent <= 100
    assert resources.load_avg_1m >= 0


def test_probe_system_resources_none_on_missing_meminfo(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN the meminfo path points at a non-existent file
    WHEN _probe_system_resources() is called
    THEN it returns None without raising.
    """
    _, _, _, app = login_admin_user_with_register
    monkeypatch.setattr(health_service, "_MEMINFO_PATH", _MISSING_MEMINFO_PATH)

    with app.app_context():
        resources = _probe_system_resources()

    assert resources is None
