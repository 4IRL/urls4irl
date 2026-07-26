from typing import Tuple

from flask import Flask, url_for
from flask.testing import FlaskClient
import pytest
from werkzeug.test import TestResponse

from backend import limiter
from backend.models.users import Users
from backend.utils.all_routes import ROUTES
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.reset_password_strs import FORGOT_PASSWORD
from backend.utils.strings.splash_form_strs import REGISTER_FORM
from tests.models_for_test import valid_user_1

pytestmark = pytest.mark.splash

_AUTH_RATE_LIMIT_PER_MINUTE = 10
_UNKNOWN_EMAIL = "ratelimit-nobody@example.com"
_LOGIN_BODY = {"username": "someUnknownUser", "password": "somePassword123"}


def _enable_limiter(app: Flask) -> None:
    """Re-arm flask-limiter for this test (globally disabled in tests).

    Mirrors the established pattern in
    tests/integration/mobile_api/test_auth_rate_limit.py.
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


def _assert_rate_limited(rate_limited_response: TestResponse) -> None:
    """Web AJAX 429s render the HTML 429 page (never JSON).

    Only /api/v1 bearer-token clients receive a JSON 429 body. Web splash
    forms POST via jQuery `$.ajax`; the global `$.ajaxPrefilter` in
    `frontend/lib/csrf.ts` detects the text/html 429 and performs a full-page
    replacement (`showNewPageOnAJAXHTMLResponse`) — the same contract every
    `*_rate_limits` UI test relies on. See
    `handle_429_response_default_ratelimit` (`backend/api_common/error_handler.py`)
    and the sibling `test_rate_limited_web_request_still_returns_html_429`.
    """
    assert rate_limited_response.status_code == 429
    assert not rate_limited_response.is_json
    assert IDENTIFIERS.HTML_429 in rate_limited_response.get_data(as_text=True)


def _register_body(user_data: dict) -> dict:
    return {
        REGISTER_FORM.USERNAME: user_data[REGISTER_FORM.USERNAME],
        REGISTER_FORM.EMAIL: user_data[REGISTER_FORM.EMAIL],
        REGISTER_FORM.CONFIRM_EMAIL: user_data[REGISTER_FORM.CONFIRM_EMAIL],
        REGISTER_FORM.PASSWORD: user_data[REGISTER_FORM.PASSWORD],
        REGISTER_FORM.CONFIRM_PASSWORD: user_data[REGISTER_FORM.CONFIRM_PASSWORD],
    }


def test_login_rate_limit_returns_html_429(
    app: Flask, load_login_page: Tuple[FlaskClient, str]
):
    """
    GIVEN the 10/minute per-IP limit on POST /login
    WHEN an 11th login attempt arrives within the window
    THEN a 429 is returned as the HTML 429 page (web AJAX; only /api/v1 gets JSON).
    """
    client, csrf_token = load_login_page
    login_url = url_for(ROUTES.SPLASH.LOGIN)
    _enable_limiter(app)
    try:
        for _attempt_number in range(_AUTH_RATE_LIMIT_PER_MINUTE):
            response = client.post(
                login_url, json=_LOGIN_BODY, headers={"X-CSRFToken": csrf_token}
            )
            assert response.status_code == 400

        rate_limited_response = client.post(
            login_url, json=_LOGIN_BODY, headers={"X-CSRFToken": csrf_token}
        )
        _assert_rate_limited(rate_limited_response)
    finally:
        _disable_limiter()


def test_register_rate_limit_returns_html_429(
    app: Flask,
    register_first_user: Tuple[dict, Users],
    load_register_page: Tuple[FlaskClient, str],
):
    """
    GIVEN the 10/minute per-IP limit on POST /register
    WHEN an 11th register attempt arrives within the window
    THEN a 429 is returned as the HTML 429 page (web AJAX; only /api/v1 gets JSON).

    Uses the already-registered valid_user_1 so every attempt is a
    username-taken 400 (branch 1) — no email is sent and no user is created,
    keeping the rate-limit exercise side-effect free.
    """
    client, csrf_token = load_register_page
    register_url = url_for(ROUTES.SPLASH.REGISTER)
    register_body = _register_body(valid_user_1)
    _enable_limiter(app)
    try:
        for _attempt_number in range(_AUTH_RATE_LIMIT_PER_MINUTE):
            response = client.post(
                register_url, json=register_body, headers={"X-CSRFToken": csrf_token}
            )
            assert response.status_code == 400

        rate_limited_response = client.post(
            register_url, json=register_body, headers={"X-CSRFToken": csrf_token}
        )
        _assert_rate_limited(rate_limited_response)
    finally:
        _disable_limiter()


def test_forgot_password_rate_limit_returns_html_429(
    app: Flask, load_login_page: Tuple[FlaskClient, str]
):
    """
    GIVEN the 10/minute per-IP limit on POST /forgot-password
    WHEN an 11th forgot-password attempt arrives within the window
    THEN a 429 is returned as the HTML 429 page (web AJAX; only /api/v1 gets JSON).

    An unknown email yields the uniform opaque 200 on every prior attempt with
    no email sent.
    """
    client, csrf_token = load_login_page
    forgot_password_url = url_for(ROUTES.SPLASH.FORGOT_PASSWORD_PAGE)
    forgot_password_body = {FORGOT_PASSWORD.EMAIL: _UNKNOWN_EMAIL}
    _enable_limiter(app)
    try:
        for _attempt_number in range(_AUTH_RATE_LIMIT_PER_MINUTE):
            response = client.post(
                forgot_password_url,
                json=forgot_password_body,
                headers={"X-CSRFToken": csrf_token},
            )
            assert response.status_code == 200

        rate_limited_response = client.post(
            forgot_password_url,
            json=forgot_password_body,
            headers={"X-CSRFToken": csrf_token},
        )
        _assert_rate_limited(rate_limited_response)
    finally:
        _disable_limiter()


def test_resend_registration_email_rate_limit_returns_html_429(
    app: Flask, load_register_page: Tuple[FlaskClient, str]
):
    """
    GIVEN the 10/minute per-IP limit on POST /resend-registration-email
    WHEN an 11th resend attempt arrives within the window
    THEN a 429 is returned as the HTML 429 page (web AJAX; only /api/v1 gets JSON).

    An unknown email yields the uniform opaque 200 on every prior attempt with
    no email sent.
    """
    client, csrf_token = load_register_page
    resend_url = url_for(ROUTES.SPLASH.RESEND_REGISTRATION_EMAIL)
    resend_body = {REGISTER_FORM.EMAIL: _UNKNOWN_EMAIL}
    _enable_limiter(app)
    try:
        for _attempt_number in range(_AUTH_RATE_LIMIT_PER_MINUTE):
            response = client.post(
                resend_url, json=resend_body, headers={"X-CSRFToken": csrf_token}
            )
            assert response.status_code == 200

        rate_limited_response = client.post(
            resend_url, json=resend_body, headers={"X-CSRFToken": csrf_token}
        )
        _assert_rate_limited(rate_limited_response)
    finally:
        _disable_limiter()
