"""Integration tests for the account-state gates on the /api/v1 surface.

Covers the Phase 5 suspension gate for bearer clients: a suspended user is
refused a token pair at login, and an already-issued access token stops
authenticating the moment the account is suspended (request_loader gate).
"""

from __future__ import annotations

from flask import Flask, g, url_for
from flask.testing import FlaskClient
import pytest

from backend import db
from backend.api_v1.constants import ApiAuthErrorCodes
from backend.models.users import Users
from backend.utils.all_routes import ROUTES
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.splash_form_strs import REGISTER_FORM
from backend.utils.strings.user_strs import USER_FAILURE
from tests.models_for_test import valid_user_1

pytestmark = pytest.mark.mobile_api

_FIRST_USER_ID: int = 1


def _login_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.AUTH_LOGIN)


def _me_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.GET_ME)


def _valid_login_body() -> dict[str, str]:
    return {
        MODELS.USERNAME: valid_user_1[REGISTER_FORM.USERNAME],
        "password": valid_user_1[REGISTER_FORM.PASSWORD],
    }


def _suspend_first_user(app: Flask) -> None:
    with app.app_context():
        target_user: Users = Users.query.get(_FIRST_USER_ID)
        target_user.is_suspended = True
        db.session.commit()


def _clear_flask_login_request_cache() -> None:
    """Drop Flask-Login's per-request user cache (``g._login_user``).

    The test harness keeps one app context alive for the whole test, so the
    per-request ``g`` cache persists across sequential test-client requests —
    never the case in production. Clearing it forces the next request through
    the request_loader again, matching production per-request behavior.
    """
    if hasattr(g, "_login_user"):
        delattr(g, "_login_user")


def test_suspended_user_api_login_returns_403(
    app: Flask, api_client: FlaskClient, register_first_user
):
    """
    GIVEN a registered, validated, SUSPENDED user with correct credentials
    WHEN POST /api/v1/auth/login
    THEN 403 with the account-suspended message and error code — no token
         pair is issued.
    """
    _suspend_first_user(app)

    response = api_client.post(_login_url(app), json=_valid_login_body())

    assert response.status_code == 403
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == USER_FAILURE.ACCOUNT_SUSPENDED
    assert response_json[STD_JSON.ERROR_CODE] == int(
        ApiAuthErrorCodes.ACCOUNT_SUSPENDED
    )


def test_suspended_user_bearer_token_stops_authenticating(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
):
    """
    GIVEN a valid, unexpired access token for a user
    WHEN the user is suspended after the token was issued
    THEN the token no longer authenticates — /api/v1/me returns 401 — even
         though the JWT itself is still cryptographically valid.
    """
    pre_suspension_response = api_client.get(
        _me_url(app), headers=bearer_headers_first_user
    )
    assert pre_suspension_response.status_code == 200

    _suspend_first_user(app)
    _clear_flask_login_request_cache()

    post_suspension_response = api_client.get(
        _me_url(app), headers=bearer_headers_first_user
    )
    assert post_suspension_response.status_code == 401
