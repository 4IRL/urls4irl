"""Integration tests for the five admin ops-action POST endpoints.

POST /admin/ops/metrics-flush
POST /admin/ops/gauge-sample
POST /admin/ops/audit-purge
POST /admin/ops/verify-tables
POST /admin/ops/short-urls-sync

Happy paths mock the heavy-lifting functions (run_flush, run_sample, run_purge,
and the short-URL requests.get) to avoid external side effects. Auth, audit
recording, and the JSON response envelope are exercised against the live Flask/DB
stack in every test.
"""

from __future__ import annotations

from typing import Tuple
from unittest.mock import MagicMock

import pytest
from flask import Flask
from flask.testing import FlaskClient
from redis import Redis

import backend.admin.ops_service as ops_service
from backend.models.audit_log import AuditLog
from backend.models.users import Users
from backend.utils.strings.admin_portal_strs import (
    ADMIN_ACTION_STRINGS,
    ADMIN_AUDIT_ACTIONS,
)
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.metrics_strs import METRICS_REDIS
from backend.utils.strings.url_validation_strs import SHORT_URLS
from tests.utils_for_test import get_csrf_token

pytestmark = pytest.mark.admin

_OPS_METRICS_FLUSH_URL: str = "/admin/ops/metrics-flush"
_OPS_GAUGE_SAMPLE_URL: str = "/admin/ops/gauge-sample"
_OPS_AUDIT_PURGE_URL: str = "/admin/ops/audit-purge"
_OPS_VERIFY_TABLES_URL: str = "/admin/ops/verify-tables"
_OPS_SHORT_URLS_SYNC_URL: str = "/admin/ops/short-urls-sync"
_OPS_BACKUP_TRIGGER_URL: str = "/admin/ops/backup-trigger"

_ALL_OPS_URLS: list[str] = [
    _OPS_METRICS_FLUSH_URL,
    _OPS_GAUGE_SAMPLE_URL,
    _OPS_AUDIT_PURGE_URL,
    _OPS_VERIFY_TABLES_URL,
    _OPS_SHORT_URLS_SYNC_URL,
    _OPS_BACKUP_TRIGGER_URL,
]

_MOCK_FLUSH_ROWS: int = 5
_MOCK_GAUGE_COUNT: int = 3
_MOCK_PURGE_COUNT: int = 2
_MOCK_SYNC_COUNT: int = 7
_MOCK_REASON: str = "integration test run"
_OVERLONG_REASON: str = "x" * 501

# Clearly fake domains that will not appear in any real short-URL list.
_FAKE_SHORT_DOMAIN_A: str = "fake-test-shorturl-domain-zzz-a.example"
_FAKE_SHORT_DOMAIN_B: str = "fake-test-shorturl-domain-zzz-b.example"

# Domain-list content mimicking the real GitHub file format.
# The real file has 11 header/comment lines; domain lines start at index 11.
# splitlines() on "\n" * 11 produces 11 empty strings; domain lines follow.
_FAKE_DOMAIN_LIST_BYTES: bytes = (
    "\n" * 11 + _FAKE_SHORT_DOMAIN_A + "\n" + _FAKE_SHORT_DOMAIN_B + "\n"
).encode()

# Fake, syntactically valid Redis URI for tests that must bypass the 503 guard
# without needing an actual Redis instance (lazy connection, never actually sent).
_FAKE_REDIS_URI: str = "redis://fake-test-redis:6379/0"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _post_ops(
    client: FlaskClient,
    url: str,
    csrf: str,
    reason: str | None = _MOCK_REASON,
) -> object:
    """POST an ops-action endpoint with a reason payload.

    Every ops action now requires a non-empty reason (same contract as the
    account/moderation actions), so the default carries a valid mock reason.
    Pass ``reason=None`` to omit it and exercise the required-field rejection.
    """
    payload: dict = {}
    if reason is not None:
        payload["reason"] = reason
    return client.post(url, json=payload, headers={"X-CSRFToken": csrf})


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_admin_ops_metrics_flush_happy_path(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a logged-in admin user and run_flush mocked to return 5
    WHEN POST /admin/ops/metrics-flush
    THEN the response is 200 JSON with count=5 and one audit row is created
         for the acting admin.
    """
    client, csrf, admin_user, app = login_admin_user_with_register

    mock_metrics_redis = MagicMock(spec=Redis)
    monkeypatch.setattr(ops_service, "_build_metrics_redis", lambda: mock_metrics_redis)
    monkeypatch.setattr(ops_service, "run_flush", lambda **_kw: _MOCK_FLUSH_ROWS)

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = _post_ops(client, _OPS_METRICS_FLUSH_URL, csrf)

    assert response.status_code == 200
    assert response.content_type == "application/json"
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body["count"] == _MOCK_FLUSH_ROWS

    with app.app_context():
        rows_after: int = AuditLog.query.count()
        assert rows_after == 1
        audit_row: AuditLog | None = AuditLog.query.first()
    assert audit_row is not None
    assert audit_row.action == ADMIN_AUDIT_ACTIONS.OPS_METRICS_FLUSH
    assert audit_row.actor_id == admin_user.id


def test_admin_ops_gauge_sample_happy_path(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a logged-in admin user and run_sample mocked to return 3
    WHEN POST /admin/ops/gauge-sample
    THEN the response is 200 JSON with count=3 and one audit row is created.
    """
    client, csrf, admin_user, app = login_admin_user_with_register

    mock_metrics_redis = MagicMock(spec=Redis)
    monkeypatch.setattr(ops_service, "_build_metrics_redis", lambda: mock_metrics_redis)
    monkeypatch.setattr(ops_service, "run_sample", lambda **_kw: _MOCK_GAUGE_COUNT)

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = _post_ops(client, _OPS_GAUGE_SAMPLE_URL, csrf)

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body["count"] == _MOCK_GAUGE_COUNT

    with app.app_context():
        rows_after: int = AuditLog.query.count()
        assert rows_after == 1
        audit_row: AuditLog | None = AuditLog.query.first()
    assert audit_row is not None
    assert audit_row.action == ADMIN_AUDIT_ACTIONS.OPS_GAUGE_SAMPLE
    assert audit_row.actor_id == admin_user.id


def test_admin_ops_audit_purge_happy_path(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a logged-in admin user and run_purge mocked to return 2
    WHEN POST /admin/ops/audit-purge
    THEN the response is 200 JSON with count=2 and one audit row is created
         (the self-audit record written before run_purge runs).
    """
    client, csrf, admin_user, app = login_admin_user_with_register

    monkeypatch.setattr(ops_service, "run_purge", lambda **_kw: _MOCK_PURGE_COUNT)

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = _post_ops(client, _OPS_AUDIT_PURGE_URL, csrf)

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body["count"] == _MOCK_PURGE_COUNT

    with app.app_context():
        rows_after: int = AuditLog.query.count()
        assert rows_after == 1
        audit_row: AuditLog | None = AuditLog.query.first()
    assert audit_row is not None
    assert audit_row.action == ADMIN_AUDIT_ACTIONS.OPS_AUDIT_PURGE
    assert audit_row.actor_id == admin_user.id
    assert audit_row.log_metadata is not None
    # The single row is the self-audit written BEFORE the delete ran.
    assert "retention_days" in audit_row.log_metadata


def test_admin_ops_verify_tables_happy_path(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user and a fully-migrated test database
    WHEN POST /admin/ops/verify-tables
    THEN the response is 200 JSON with count=0, the "all tables present" message,
         and one audit row is created.
    """
    client, csrf, admin_user, app = login_admin_user_with_register

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = _post_ops(client, _OPS_VERIFY_TABLES_URL, csrf)

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body["count"] == 0
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.OPS_VERIFY_OK

    with app.app_context():
        rows_after: int = AuditLog.query.count()
        assert rows_after == 1
        audit_row: AuditLog | None = AuditLog.query.first()
    assert audit_row is not None
    assert audit_row.action == ADMIN_AUDIT_ACTIONS.OPS_VERIFY_TABLES
    assert audit_row.actor_id == admin_user.id


def test_admin_ops_short_urls_sync_happy_path(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a logged-in admin user with sync_short_url_domains_to_redis mocked
          to return 7 and a fake REDIS_URI bypassing the 503 guard
    WHEN POST /admin/ops/short-urls-sync
    THEN the response is 200 JSON with count=7 and one audit row is created.
    """
    client, csrf, admin_user, app = login_admin_user_with_register

    # Override REDIS_URI so the 503 guard is bypassed (not "memory://")
    monkeypatch.setitem(app.config, "REDIS_URI", _FAKE_REDIS_URI)

    # Mock sync so the fake Redis URI is never actually dialled
    monkeypatch.setattr(
        ops_service, "sync_short_url_domains_to_redis", lambda **_kw: _MOCK_SYNC_COUNT
    )

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = _post_ops(client, _OPS_SHORT_URLS_SYNC_URL, csrf)

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body["count"] == _MOCK_SYNC_COUNT

    with app.app_context():
        rows_after: int = AuditLog.query.count()
        assert rows_after == 1
        audit_row: AuditLog | None = AuditLog.query.first()
    assert audit_row is not None
    assert audit_row.action == ADMIN_AUDIT_ACTIONS.OPS_SHORT_URLS_SYNC
    assert audit_row.actor_id == admin_user.id


# ---------------------------------------------------------------------------
# Auth guard tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ops_url", _ALL_OPS_URLS)
def test_admin_ops_non_admin_returns_404(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    ops_url: str,
) -> None:
    """
    GIVEN a logged-in non-admin user
    WHEN that user POSTs any ops-action endpoint
    THEN the response is 404 JSON (admin_required returns 404 for non-admins
         to avoid leaking admin-surface existence).
    """
    client, csrf, _, _ = login_first_user_with_register

    response = _post_ops(client, ops_url, csrf)

    assert response.status_code == 404


@pytest.mark.parametrize("ops_url", _ALL_OPS_URLS)
def test_admin_ops_anonymous_returns_401(
    client: FlaskClient,
    ops_url: str,
) -> None:
    """
    GIVEN an unauthenticated (anonymous) session
    WHEN the client POSTs any ops-action endpoint with a valid CSRF token
    THEN the response is 401 JSON (admin_required returns 401 for anonymous).

    Note: a GET to "/" is required first to establish an anonymous session and
    obtain a valid CSRF token. Without it the CSRF middleware would return 403
    before the auth check runs.
    """
    splash_response = client.get("/")
    csrf_token = get_csrf_token(splash_response.get_data(), meta_tag=True)

    response = client.post(ops_url, json={}, headers={"X-CSRFToken": csrf_token})

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Request-schema validation tests
# ---------------------------------------------------------------------------


def test_admin_ops_missing_reason_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user sending no reason at all
    WHEN POST /admin/ops/verify-tables with an empty JSON body
    THEN the response is 400 JSON — ops actions now require a non-empty reason,
         so the request schema rejects the missing field before any work runs.
    """
    client, csrf, _, _ = login_admin_user_with_register

    response = _post_ops(client, _OPS_VERIFY_TABLES_URL, csrf, reason=None)

    assert response.status_code == 400


def test_admin_ops_whitespace_reason_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user sending a whitespace-only reason
    WHEN POST /admin/ops/verify-tables with reason="   "
    THEN the response is 400 JSON — the required-reason validator rejects
         whitespace-only values just as it does for account/moderation actions.
    """
    client, csrf, _, _ = login_admin_user_with_register

    response = _post_ops(client, _OPS_VERIFY_TABLES_URL, csrf, reason="   ")

    assert response.status_code == 400


def test_admin_ops_reason_too_long_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user sending a reason string longer than 500 chars
    WHEN POST /admin/ops/verify-tables (no mocks needed — schema validates first)
    THEN the response is 400 JSON (field_validator rejects the excess length).
    """
    client, csrf, _, _ = login_admin_user_with_register

    response = _post_ops(client, _OPS_VERIFY_TABLES_URL, csrf, reason=_OVERLONG_REASON)

    assert response.status_code == 400


def test_admin_ops_reason_lands_in_audit_metadata(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin user POSTing with a reason string
    WHEN POST /admin/ops/verify-tables with reason=_MOCK_REASON
    THEN the audit row's log_metadata contains the exact reason supplied.
    """
    client, csrf, _, app = login_admin_user_with_register

    response = _post_ops(client, _OPS_VERIFY_TABLES_URL, csrf, reason=_MOCK_REASON)

    assert response.status_code == 200
    with app.app_context():
        audit_row: AuditLog | None = AuditLog.query.first()
    assert audit_row is not None
    assert audit_row.log_metadata is not None
    assert audit_row.log_metadata.get("reason") == _MOCK_REASON


# ---------------------------------------------------------------------------
# Purge self-audit-before-delete guarantee
# ---------------------------------------------------------------------------


def test_admin_ops_purge_self_audit_precedes_delete(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a logged-in admin user and run_purge monkeypatched to raise
    WHEN POST /admin/ops/audit-purge
    THEN the response is 500 AND the self-audit row (containing retention_days
         in its metadata) was committed before run_purge was called, proving
         the purge trigger is always on record even when the delete fails.
    """
    client, csrf, admin_user, app = login_admin_user_with_register

    def _raise_on_purge(**_kw: object) -> int:
        raise RuntimeError("simulated purge failure")

    monkeypatch.setattr(ops_service, "run_purge", _raise_on_purge)

    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    response = _post_ops(client, _OPS_AUDIT_PURGE_URL, csrf)

    assert response.status_code == 500

    with app.app_context():
        # Both the self-audit (before purge) and the error-audit (in the except
        # block) are committed; at minimum the self-audit row must be present.
        rows_after: int = AuditLog.query.count()
        assert rows_after >= 1

        first_row: AuditLog | None = AuditLog.query.order_by(AuditLog.id).first()
    assert first_row is not None
    assert first_row.action == ADMIN_AUDIT_ACTIONS.OPS_AUDIT_PURGE
    assert first_row.actor_id == admin_user.id
    assert first_row.log_metadata is not None
    # Self-audit metadata has retention_days, not "error"
    assert "retention_days" in first_row.log_metadata


# ---------------------------------------------------------------------------
# Gauge sentinel stamping
# ---------------------------------------------------------------------------


def test_admin_ops_gauge_sample_stamps_sentinel_on_metrics_redis(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    provide_metrics_redis: Redis | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a logged-in admin user, a real metrics Redis, and run_sample mocked
          to avoid raw psycopg2 DB writes
    WHEN POST /admin/ops/gauge-sample
    THEN GAUGE_LAST_SUCCESS_KEY is set on metrics Redis, mirroring the
         behaviour of the background sample_gauges sidecar.

    Skipped when metrics Redis is not configured in the test environment.
    """
    metrics_redis = provide_metrics_redis
    if metrics_redis is None:
        pytest.skip("metrics Redis not configured in test environment")

    client, csrf, _, _ = login_admin_user_with_register

    # Mock run_sample to prevent raw psycopg2 commits bypassing the test transaction.
    # _build_metrics_redis is NOT mocked — the service creates its own client
    # pointing at the same metrics Redis, so the sentinel it writes is visible here.
    monkeypatch.setattr(ops_service, "run_sample", lambda **_kw: _MOCK_GAUGE_COUNT)

    sentinel_before = metrics_redis.get(METRICS_REDIS.GAUGE_LAST_SUCCESS_KEY)
    assert sentinel_before is None

    response = _post_ops(client, _OPS_GAUGE_SAMPLE_URL, csrf)

    assert response.status_code == 200
    sentinel_after = metrics_redis.get(METRICS_REDIS.GAUGE_LAST_SUCCESS_KEY)
    assert sentinel_after is not None


# ---------------------------------------------------------------------------
# Short-URL Redis set population
# ---------------------------------------------------------------------------


def test_admin_ops_short_urls_sync_adds_domains_to_redis(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    provide_redis: Redis | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a logged-in admin user, a real main Redis, and requests.get mocked to
          return a fake domain list containing two clearly test-specific domains
    WHEN POST /admin/ops/short-urls-sync
    THEN both fake domains appear in the SHORT_URLS Redis set after the call.

    Skipped when main Redis is not configured in the test environment.
    """
    main_redis = provide_redis
    if main_redis is None:
        pytest.skip("main Redis not configured in test environment")

    client, csrf, _, _ = login_admin_user_with_register

    mock_response = MagicMock()
    mock_response.content = _FAKE_DOMAIN_LIST_BYTES
    monkeypatch.setattr(
        "backend.utils.short_urls.requests.get",
        lambda *_args, **_kw: mock_response,
    )

    response = _post_ops(client, _OPS_SHORT_URLS_SYNC_URL, csrf)

    assert response.status_code == 200
    assert main_redis.sismember(SHORT_URLS, _FAKE_SHORT_DOMAIN_A)
    assert main_redis.sismember(SHORT_URLS, _FAKE_SHORT_DOMAIN_B)


# ---------------------------------------------------------------------------
# Backup trigger (cross-container flag)
# ---------------------------------------------------------------------------


def test_admin_ops_backup_trigger_sets_flag_and_audits(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    provide_metrics_redis: Redis | None,
) -> None:
    """
    GIVEN a logged-in admin user, a real metrics Redis, and no pending request
    WHEN POST /admin/ops/backup-trigger with a reason
    THEN the trigger flag key is set with a TTL, the success message is
         returned, and one audit row records the trigger with the reason.

    Skipped when metrics Redis is not configured in the test environment.
    """
    metrics_redis = provide_metrics_redis
    if metrics_redis is None:
        pytest.skip("metrics Redis not configured in test environment")

    client, csrf, admin_user, app = login_admin_user_with_register

    assert metrics_redis.get(METRICS_REDIS.BACKUP_TRIGGER_KEY) is None
    with app.app_context():
        rows_before: int = AuditLog.query.count()
    assert rows_before == 0

    try:
        response = _post_ops(client, _OPS_BACKUP_TRIGGER_URL, csrf, reason=_MOCK_REASON)

        assert response.status_code == 200
        body = response.get_json()
        assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
        assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.OPS_BACKUP_TRIGGER_SUCCESS

        flag_value = metrics_redis.get(METRICS_REDIS.BACKUP_TRIGGER_KEY)
        assert flag_value is not None
        flag_ttl = metrics_redis.ttl(METRICS_REDIS.BACKUP_TRIGGER_KEY)
        assert 0 < flag_ttl <= ops_service.BACKUP_TRIGGER_TTL_SECONDS

        with app.app_context():
            rows_after: int = AuditLog.query.count()
            assert rows_after == 1
            audit_row: AuditLog | None = AuditLog.query.first()
        assert audit_row is not None
        assert audit_row.action == ADMIN_AUDIT_ACTIONS.OPS_BACKUP_TRIGGER
        assert audit_row.actor_id == admin_user.id
        assert audit_row.log_metadata is not None
        assert audit_row.log_metadata.get("reason") == _MOCK_REASON
    finally:
        metrics_redis.delete(METRICS_REDIS.BACKUP_TRIGGER_KEY)


def test_admin_ops_backup_trigger_idempotent_while_pending(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    provide_metrics_redis: Redis | None,
) -> None:
    """
    GIVEN a logged-in admin user and a backup request already pending
    WHEN POST /admin/ops/backup-trigger a second time
    THEN the response is 200 with the already-pending message, the original
         flag value is untouched, and NO additional audit row is written
         (nothing was triggered).
    """
    metrics_redis = provide_metrics_redis
    if metrics_redis is None:
        pytest.skip("metrics Redis not configured in test environment")

    client, csrf, _, app = login_admin_user_with_register

    try:
        first_response = _post_ops(client, _OPS_BACKUP_TRIGGER_URL, csrf)
        assert first_response.status_code == 200
        original_flag_value = metrics_redis.get(METRICS_REDIS.BACKUP_TRIGGER_KEY)
        assert original_flag_value is not None
        with app.app_context():
            rows_after_first: int = AuditLog.query.count()
        assert rows_after_first == 1

        second_response = _post_ops(client, _OPS_BACKUP_TRIGGER_URL, csrf)

        assert second_response.status_code == 200
        second_body = second_response.get_json()
        assert (
            second_body[STD_JSON.MESSAGE]
            == ADMIN_ACTION_STRINGS.OPS_BACKUP_TRIGGER_ALREADY_PENDING
        )
        assert (
            metrics_redis.get(METRICS_REDIS.BACKUP_TRIGGER_KEY) == original_flag_value
        )
        with app.app_context():
            rows_after_second: int = AuditLog.query.count()
        assert rows_after_second == 1
    finally:
        metrics_redis.delete(METRICS_REDIS.BACKUP_TRIGGER_KEY)
