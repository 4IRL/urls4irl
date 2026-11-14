from __future__ import annotations

import logging
import re
import time
from unittest import mock

import pytest
from flask import Flask, session
from flask_session.redis import RedisSessionInterface
from redis import Redis

from backend.schemas.system import DeepHealthResponseSchema
from backend.system import health_checks
from backend.system.health_checks import (
    STATUS_DOWN,
    STATUS_NOT_CONFIGURED,
    STATUS_UP,
    Budget,
)
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.health_strs import HEALTH_STRS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON

pytestmark = pytest.mark.cli

HEALTH_DEEP_URL = "/health/deep"
TOKEN = "test-token-4f9a1c7e2b"
AUTH_HEADERS = {CONFIG_ENVS.X_HEALTH_TOKEN: TOKEN}
UNREACHABLE_REDIS_URI = "redis://127.0.0.1:1/0"

ROUTE_PROBES = (
    "backend.system.routes.probe_postgres",
    "backend.system.routes.probe_session_redis",
    "backend.system.routes.probe_metrics_redis",
)


def _real_redis_configured(app: Flask) -> bool:
    session_uri = app.config.get(CONFIG_ENVS.REDIS_URI)
    metrics_uri = app.config.get(CONFIG_ENVS.METRICS_REDIS_URI)
    return all(
        uri and uri != health_checks.MEMORY_URI for uri in (session_uri, metrics_uri)
    )


def _patch_probes(
    postgres: str = STATUS_UP,
    session_redis: str = STATUS_UP,
    metrics_redis: str = STATUS_UP,
):
    return (
        mock.patch(ROUTE_PROBES[0], return_value=postgres),
        mock.patch(ROUTE_PROBES[1], return_value=session_redis),
        mock.patch(ROUTE_PROBES[2], return_value=metrics_redis),
    )


def _get_deep(app: Flask, headers: dict[str, str] | None = None):
    with app.test_client() as deep_client:
        return deep_client.get(HEALTH_DEEP_URL, headers=headers or {})


def test_valid_token_all_up_returns_200(app: Flask):
    """
    GIVEN a configured token and reachable Postgres and both Redis servers
    WHEN /health/deep is requested with the valid token
    THEN 200 with every component up and a body matching the schema
    """
    if not _real_redis_configured(app):
        pytest.skip("session or metrics Redis URI is memory://")

    with mock.patch.dict(app.config, {CONFIG_ENVS.HEALTH_CHECK_TOKEN: TOKEN}):
        response = _get_deep(app, AUTH_HEADERS)

    assert response.status_code == 200
    body = response.get_json()
    assert set(body) == {STD_JSON.STATUS, HEALTH_STRS.COMPONENTS}
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[HEALTH_STRS.COMPONENTS] == {
        key: STATUS_UP for key in HEALTH_STRS.COMPONENT_ORDER
    }
    DeepHealthResponseSchema.model_validate(body)


def test_all_up_body_has_exact_keys_and_status(app: Flask):
    """
    GIVEN all three probes report up (patched, so never skipped)
    WHEN /health/deep is requested with the valid token
    THEN 200 with exactly the keys status and components and status Success
    """
    postgres, session_redis, metrics_redis = _patch_probes()
    with mock.patch.dict(app.config, {CONFIG_ENVS.HEALTH_CHECK_TOKEN: TOKEN}):
        with postgres, session_redis, metrics_redis:
            response = _get_deep(app, AUTH_HEADERS)

    assert response.status_code == 200
    body = response.get_json()
    assert set(body) == {STD_JSON.STATUS, HEALTH_STRS.COMPONENTS}
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS


@pytest.mark.parametrize(
    "headers",
    [
        {CONFIG_ENVS.X_HEALTH_TOKEN: "wrong-token"},
        {},
        {CONFIG_ENVS.X_HEALTH_TOKEN: ""},
    ],
    ids=["wrong", "missing", "empty"],
)
def test_bad_header_returns_401_and_runs_no_probe(app: Flask, headers: dict[str, str]):
    """
    GIVEN a configured token
    WHEN the header is wrong, missing or empty
    THEN 401 Unauthorized with no components, and no probe runs
    """
    postgres, session_redis, metrics_redis = _patch_probes()
    with mock.patch.dict(app.config, {CONFIG_ENVS.HEALTH_CHECK_TOKEN: TOKEN}):
        with postgres as pg_mock, session_redis as s_mock, metrics_redis as m_mock:
            response = _get_deep(app, headers)

    assert response.status_code == 401
    assert response.get_json() == {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: HEALTH_STRS.UNAUTHORIZED,
    }
    for probe_mock in (pg_mock, s_mock, m_mock):
        probe_mock.assert_not_called()


@pytest.mark.parametrize("secret", [None, "", "   "], ids=["none", "empty", "blank"])
@pytest.mark.parametrize(
    "header", [TOKEN, "", "   ", None], ids=["tok", "empty", "blank", "none"]
)
def test_unset_secret_returns_401(app: Flask, secret: str | None, header: str | None):
    """
    GIVEN the server secret is None, empty or whitespace
    WHEN /health/deep is requested with any header
    THEN 401 and no probe runs
    """
    headers = {} if header is None else {CONFIG_ENVS.X_HEALTH_TOKEN: header}
    postgres, session_redis, metrics_redis = _patch_probes()
    with mock.patch.dict(app.config, {CONFIG_ENVS.HEALTH_CHECK_TOKEN: secret}):
        with postgres as pg_mock, session_redis as s_mock, metrics_redis as m_mock:
            response = _get_deep(app, headers)

    assert response.status_code == 401
    assert HEALTH_STRS.COMPONENTS not in response.get_json()
    for probe_mock in (pg_mock, s_mock, m_mock):
        probe_mock.assert_not_called()


@pytest.mark.parametrize("down_key", HEALTH_STRS.COMPONENT_ORDER)
def test_single_component_down_returns_503(app: Flask, down_key: str):
    """
    GIVEN one probe reports down
    WHEN /health/deep is requested with the valid token
    THEN 503 with that key down, the others up, and the message naming it
    """
    statuses = {key: STATUS_UP for key in HEALTH_STRS.COMPONENT_ORDER}
    statuses[down_key] = STATUS_DOWN
    postgres, session_redis, metrics_redis = _patch_probes(**statuses)
    with mock.patch.dict(app.config, {CONFIG_ENVS.HEALTH_CHECK_TOKEN: TOKEN}):
        with postgres, session_redis, metrics_redis:
            response = _get_deep(app, AUTH_HEADERS)

    assert response.status_code == 503
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == HEALTH_STRS.UNHEALTHY_PREFIX + down_key
    assert body[HEALTH_STRS.COMPONENTS] == statuses


def test_all_components_down_message_uses_fixed_order(app: Flask):
    """
    GIVEN every probe reports down
    WHEN /health/deep is requested
    THEN the message names all keys in postgres, session_redis, metrics_redis order
    """
    postgres, session_redis, metrics_redis = _patch_probes(
        STATUS_DOWN, STATUS_DOWN, STATUS_DOWN
    )
    with mock.patch.dict(app.config, {CONFIG_ENVS.HEALTH_CHECK_TOKEN: TOKEN}):
        with postgres, session_redis, metrics_redis:
            response = _get_deep(app, AUTH_HEADERS)

    assert response.status_code == 503
    assert response.get_json()[STD_JSON.MESSAGE] == (
        HEALTH_STRS.UNHEALTHY_PREFIX + "postgres, session_redis, metrics_redis"
    )


@pytest.mark.parametrize("key", HEALTH_STRS.COMPONENT_ORDER)
def test_not_configured_component_returns_503(app: Flask, key: str):
    """
    GIVEN one component reports not configured
    WHEN /health/deep is requested with the valid token
    THEN 503 (fail closed) with that component's value not configured
    """
    statuses = {name: STATUS_UP for name in HEALTH_STRS.COMPONENT_ORDER}
    statuses[key] = STATUS_NOT_CONFIGURED
    postgres, session_redis, metrics_redis = _patch_probes(**statuses)
    with mock.patch.dict(app.config, {CONFIG_ENVS.HEALTH_CHECK_TOKEN: TOKEN}):
        with postgres, session_redis, metrics_redis:
            response = _get_deep(app, AUTH_HEADERS)

    assert response.status_code == 503
    body = response.get_json()
    assert body[HEALTH_STRS.COMPONENTS][key] == STATUS_NOT_CONFIGURED
    assert body[STD_JSON.MESSAGE] == HEALTH_STRS.UNHEALTHY_PREFIX + key


def test_bodies_never_leak_internals(app: Flask):
    """
    GIVEN real probes against unreachable Redis servers (exceptions are raised internally)
    WHEN /health/deep is requested (authorized and not)
    THEN no body contains a URI, traceback, exception text or the token
    """
    config = {
        CONFIG_ENVS.HEALTH_CHECK_TOKEN: TOKEN,
        CONFIG_ENVS.REDIS_URI: UNREACHABLE_REDIS_URI,
        CONFIG_ENVS.METRICS_REDIS_URI: UNREACHABLE_REDIS_URI,
    }
    with mock.patch.dict(app.config, config):
        authorized = _get_deep(app, AUTH_HEADERS)
        unauthorized = _get_deep(app, {CONFIG_ENVS.X_HEALTH_TOKEN: "other"})

    assert authorized.status_code == 503
    for response in (authorized, unauthorized):
        text = response.get_data(as_text=True)
        for forbidden in ("redis://", "Traceback", "Error", "127.0.0.1", TOKEN):
            assert forbidden not in text


def test_session_redis_outage_cookieless(app: Flask):
    """
    GIVEN the session Redis is unreachable (cookieless requests)
    WHEN /health/deep (valid token) and /health are requested
    THEN deep returns 503 with session_redis down (not 500) and /health returns 200
    """
    if not isinstance(app.session_interface, RedisSessionInterface):
        pytest.skip("session interface is not Redis (memory:// fallback)")

    original_client = app.session_interface.client
    outage_client = Redis.from_url(UNREACHABLE_REDIS_URI)
    config = {
        CONFIG_ENVS.HEALTH_CHECK_TOKEN: TOKEN,
        CONFIG_ENVS.REDIS_URI: UNREACHABLE_REDIS_URI,
    }
    try:
        app.session_interface.client = outage_client
        with mock.patch.dict(app.config, config):
            deep_response = _get_deep(app, AUTH_HEADERS)
            with app.test_client() as plain_client:
                health_response = plain_client.get("/health")
    finally:
        app.session_interface.client = original_client
        outage_client.close()

    assert deep_response.status_code == 503
    deep_body = deep_response.get_json()
    assert deep_body[HEALTH_STRS.COMPONENTS][HEALTH_STRS.SESSION_REDIS] == STATUS_DOWN
    assert health_response.status_code == 200
    assert health_response.get_json() == {STD_JSON.STATUS: STD_JSON.SUCCESS}


def test_unauthorized_log_levels(app: Flask, caplog: pytest.LogCaptureFixture):
    """
    GIVEN the 401 paths
    WHEN each is hit
    THEN missing header logs INFO, token mismatch and unset secret log WARNING, and
    the provided value is never logged
    """
    provided = "attacker-supplied-value"

    def records_with(text: str) -> list[logging.LogRecord]:
        return [rec for rec in caplog.records if text in rec.getMessage()]

    with mock.patch.dict(app.config, {CONFIG_ENVS.HEALTH_CHECK_TOKEN: TOKEN}):
        _get_deep(app)
        missing = records_with("header missing")
        _get_deep(app, {CONFIG_ENVS.X_HEALTH_TOKEN: provided})
        mismatch = records_with("token mismatch")
    with mock.patch.dict(app.config, {CONFIG_ENVS.HEALTH_CHECK_TOKEN: None}):
        _get_deep(app, AUTH_HEADERS)
        unset = records_with("secret unset")

    assert [rec.levelno for rec in missing] == [logging.INFO]
    assert [rec.levelno for rec in mismatch] == [logging.WARNING]
    assert [rec.levelno for rec in unset] == [logging.WARNING]
    assert not records_with(provided)
    assert not records_with(TOKEN)


def test_success_logs_one_info_record_with_statuses(
    app: Flask, caplog: pytest.LogCaptureFixture
):
    """
    GIVEN an authorized call with known component statuses
    WHEN /health/deep is requested
    THEN exactly one INFO record carries the three statuses
    """
    postgres, session_redis, metrics_redis = _patch_probes(
        STATUS_UP, STATUS_DOWN, STATUS_NOT_CONFIGURED
    )
    with mock.patch.dict(app.config, {CONFIG_ENVS.HEALTH_CHECK_TOKEN: TOKEN}):
        with postgres, session_redis, metrics_redis:
            _get_deep(app, AUTH_HEADERS)

    records = [
        rec for rec in caplog.records if "Deep health check:" in rec.getMessage()
    ]
    assert len(records) == 1
    assert records[0].levelno == logging.INFO
    message = records[0].getMessage()
    assert "postgres=up" in message
    assert "session_redis=down" in message
    assert "metrics_redis=not configured" in message
    assert re.search(r"in \d+ms$", message)


@pytest.mark.parametrize("url", ["/health", HEALTH_DEEP_URL])
def test_health_responses_have_no_cookie_and_fixed_csp(app: Flask, url: str):
    """
    GIVEN the health endpoints
    WHEN requested
    THEN no Set-Cookie, the static security headers and the fixed CSP (no nonce)
    """
    with mock.patch.dict(app.config, {CONFIG_ENVS.HEALTH_CHECK_TOKEN: TOKEN}):
        with app.test_client() as health_client:
            response = health_client.get(url, headers=AUTH_HEADERS)

    assert "Set-Cookie" not in response.headers
    assert response.headers[CONFIG_ENVS.X_CONTENT_TYPE_OPTIONS] == "nosniff"
    assert response.headers[CONFIG_ENVS.X_FRAME_OPTIONS] == "DENY"
    assert CONFIG_ENVS.REFERRER_POLICY in response.headers
    assert CONFIG_ENVS.CROSS_ORIGIN_RESOURCE_POLICY in response.headers
    csp = response.headers[CONFIG_ENVS.CONTENT_SECURITY_POLICY]
    assert response.headers["Cache-Control"] == "no-store"
    assert "nonce-" not in csp
    assert "default-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp


def test_non_health_route_still_sets_nonce(app: Flask):
    """
    GIVEN a non-health route
    WHEN requested
    THEN session['nonce'] is set and the CSP carries a nonce (the bypass did not leak)
    """
    with app.test_client() as page_client:
        response = page_client.get("/")
        assert session.get("nonce")
        nonce = session["nonce"]

    assert f"'nonce-{nonce}'" in response.headers[CONFIG_ENVS.CONTENT_SECURITY_POLICY]


def test_deadline_bounds_total_time_and_shares_budget(app: Flask):
    """
    GIVEN a tiny overall deadline and a first probe that outlasts it
    WHEN /health/deep is requested
    THEN the later real probes report down without connecting, the response is 503
    naming them, every probe got the same Budget, and the call stays well under 8 s
    """
    seen_budgets: list[Budget] = []

    def slow_postgres(budget: Budget) -> str:
        seen_budgets.append(budget)
        time.sleep(0.2)
        return STATUS_UP

    real_session_probe = health_checks.probe_session_redis
    real_metrics_probe = health_checks.probe_metrics_redis

    def session_probe(budget: Budget) -> str:
        seen_budgets.append(budget)
        return real_session_probe(budget)

    def metrics_probe(budget: Budget) -> str:
        seen_budgets.append(budget)
        return real_metrics_probe(budget)

    config = {
        CONFIG_ENVS.HEALTH_CHECK_TOKEN: TOKEN,
        CONFIG_ENVS.REDIS_URI: UNREACHABLE_REDIS_URI,
        CONFIG_ENVS.METRICS_REDIS_URI: UNREACHABLE_REDIS_URI,
    }
    started_at = time.monotonic()
    with (
        mock.patch.dict(app.config, config),
        mock.patch.object(health_checks, "DEEP_CHECK_DEADLINE_SECONDS", 0.05),
        mock.patch(ROUTE_PROBES[0], side_effect=slow_postgres),
        mock.patch(ROUTE_PROBES[1], side_effect=session_probe),
        mock.patch(ROUTE_PROBES[2], side_effect=metrics_probe),
        mock.patch.object(health_checks.Redis, "from_url") as from_url_spy,
    ):
        response = _get_deep(app, AUTH_HEADERS)
    elapsed = time.monotonic() - started_at

    assert response.status_code == 503
    body = response.get_json()
    assert body[HEALTH_STRS.COMPONENTS] == {
        HEALTH_STRS.POSTGRES: STATUS_UP,
        HEALTH_STRS.SESSION_REDIS: STATUS_DOWN,
        HEALTH_STRS.METRICS_REDIS: STATUS_DOWN,
    }
    assert body[STD_JSON.MESSAGE] == (
        HEALTH_STRS.UNHEALTHY_PREFIX + "session_redis, metrics_redis"
    )
    from_url_spy.assert_not_called()
    assert len(seen_budgets) == 3
    assert all(budget is seen_budgets[0] for budget in seen_budgets)
    assert elapsed < 4
