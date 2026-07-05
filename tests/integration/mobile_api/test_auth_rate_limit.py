from flask import Flask, url_for
from flask.testing import FlaskClient
import pytest

from backend import limiter
from backend.utils.all_routes import ROUTES
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON

pytestmark = pytest.mark.mobile_api

_AUTH_RATE_LIMIT_PER_MINUTE = 10
_LOGIN_BODY = {"username": "someUnknownUser", "password": "somePassword123"}


def _login_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.AUTH_LOGIN)


def _enable_limiter(app: Flask) -> None:
    """Re-arm flask-limiter for this test (globally disabled in tests).

    Mirrors the established pattern in
    tests/integration/account_and_settings/test_contact_us.py.
    """
    original_first_request = app._got_first_request
    app._got_first_request = False
    app.config["RATELIMIT_ENABLED"] = True
    limiter.enabled = True
    limiter.init_app(app)
    app._got_first_request = original_first_request


def _disable_limiter() -> None:
    if limiter._storage is not None:
        limiter._storage.reset()
    limiter._storage = None
    limiter._limiter = None
    limiter.enabled = False
    limiter.initialized = False


def test_auth_endpoint_rate_limit_returns_json_429(
    app: Flask, api_client: FlaskClient, register_first_user
):
    """
    GIVEN the 10/minute per-IP limit on /api/v1/auth/*
    WHEN an 11th login attempt arrives within the window
    THEN a 429 is returned as the JSON ErrorResponse envelope (never HTML)
    """
    _enable_limiter(app)
    try:
        login_url = _login_url(app)
        for _attempt_number in range(_AUTH_RATE_LIMIT_PER_MINUTE):
            response = api_client.post(login_url, json=_LOGIN_BODY)
            assert response.status_code == 400

        rate_limited_response = api_client.post(login_url, json=_LOGIN_BODY)

        assert rate_limited_response.status_code == 429
        assert rate_limited_response.is_json
        rate_limited_json = rate_limited_response.get_json()
        assert rate_limited_json[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert rate_limited_json[STD_JSON.MESSAGE] == STD_JSON.TOO_MANY_REQUESTS
    finally:
        _disable_limiter()
