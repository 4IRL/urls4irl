from flask import Flask, request
import pytest

from backend.users.routes import load_user_from_request
from backend.utils.strings.api_auth_strs import API_AUTH

pytestmark = pytest.mark.mobile_api

_API_V1_PROBE_PATH = f"{API_AUTH.API_V1_URL_PREFIX}/probe"
_WEB_PATH = "/utubs"


def test_bearer_on_api_v1_path_authenticates(
    app: Flask, access_token_first_user: str, make_bearer_headers
):
    """
    GIVEN a valid access token in an Authorization: Bearer header
    WHEN a request targets an /api/v1 path
    THEN the request_loader resolves the token to its user
    """
    with app.test_request_context(
        _API_V1_PROBE_PATH, headers=make_bearer_headers(access_token_first_user)
    ):
        loaded_user = load_user_from_request(request)
        assert loaded_user is not None
        assert loaded_user.id == 1


def test_bearer_on_web_path_is_ignored(
    app: Flask, access_token_first_user: str, make_bearer_headers
):
    """Bearer tokens must never authenticate web (non-/api/v1) routes."""
    with app.test_request_context(
        _WEB_PATH, headers=make_bearer_headers(access_token_first_user)
    ):
        assert load_user_from_request(request) is None


def test_missing_authorization_header_returns_none(app: Flask, register_first_user):
    with app.test_request_context(_API_V1_PROBE_PATH):
        assert load_user_from_request(request) is None


def test_non_bearer_authorization_scheme_returns_none(
    app: Flask, access_token_first_user: str
):
    with app.test_request_context(
        _API_V1_PROBE_PATH,
        headers={API_AUTH.AUTHORIZATION_HEADER: f"Token {access_token_first_user}"},
    ):
        assert load_user_from_request(request) is None


def test_invalid_bearer_token_returns_none(app: Flask, register_first_user):
    with app.test_request_context(
        _API_V1_PROBE_PATH,
        headers={API_AUTH.AUTHORIZATION_HEADER: f"{API_AUTH.BEARER_PREFIX}garbage"},
    ):
        assert load_user_from_request(request) is None


def test_web_route_with_bearer_still_redirects_unauthenticated(
    app: Flask, client, access_token_first_user: str, make_bearer_headers
):
    """
    GIVEN a request to a session-protected web route carrying only a bearer token
    WHEN the request is made without a session cookie
    THEN the web auth path is unchanged: Flask-Login treats it as
        unauthenticated and issues its 302 redirect to the splash page
    """
    response = client.get(
        _WEB_PATH, headers=make_bearer_headers(access_token_first_user)
    )
    assert response.status_code == 302
