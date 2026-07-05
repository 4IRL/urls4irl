"""
Negative-surface integration tests for the /api/v1 mobile bearer-token surface.

Verifies the CSRF/XHR posture differs correctly between the bearer (/api/v1)
and session-cookie (web) surfaces:

  - Bearer requests with no CSRF token and no X-Requested-With header reach
    /api/v1 mutating endpoints normally (200).
  - The same web mutating routes reject requests that carry no X-Requested-With
    sentinel (302 AJAX redirect).
  - Web mutating routes reject requests that carry no CSRF token (403).
  - A logged-in session client that carries no Authorization: Bearer header
    cannot authenticate via the session fallback on /api/v1 (401).
  - An ambiguous request carrying BOTH a session cookie and a valid bearer
    token is refused on /api/v1 (401) — the session resolves first, so the
    bearer-authenticated stamp is never set.

Conventions:
  - Uses api_client (plain FlaskClient) for bearer tests.
  - Uses login_first_user_with_register (AjaxFlaskLoginClient) for web tests.
  - All JSON key constants imported from backend string modules.
  - pytestmark = pytest.mark.mobile_api
"""

from typing import Tuple

from flask import Flask, url_for
from flask.testing import FlaskClient
import pytest

from backend.api_v1.services.tokens import create_access_token
from backend.models.users import Users
from backend.utils.all_routes import ROUTES
from backend.utils.strings.api_auth_strs import (
    API_AUTH,
    API_AUTH_FAILURE,
)
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from tests.models_for_test import valid_url_strings

pytestmark = pytest.mark.mobile_api

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_UTUB_NAME_FIELD = "utubName"
_UTUB_DESC_FIELD = "utubDescription"
_TAG_STRING_FIELD = MODELS.TAG_STRING

_BEARER_TEST_UTUB_NAME = "BearerNoCsrfUTub"
_BEARER_TEST_URL_STRING = valid_url_strings[0]  # "https://www.abc.com/"
_BEARER_TEST_URL_TITLE = "Bearer No-CSRF URL"
_BEARER_TEST_TAG_STRING = "bearer-no-csrf-tag"

_WEB_TEST_UTUB_NAME = "WebSurfaceTestUTub"

# Status codes referenced by assertions
_AJAX_REDIRECT_STATUS = 302
_CSRF_MISSING_STATUS = 403

# X-CSRFToken header name (from URL_VALIDATION constants)
_CSRF_HEADER_KEY = URL_VALIDATION.X_CSRF_TOKEN

# Non-AJAX value for the X-Requested-With header — triggers AJAX enforcement
_NON_AJAX_VALUE = "not-ajax"


# ---------------------------------------------------------------------------
# URL helpers — resolved inside test_request_context so url_for works
# ---------------------------------------------------------------------------


def _api_create_utub_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.CREATE_UTUB)


def _api_create_url_url(app: Flask, utub_id: int) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.CREATE_URL, utub_id=utub_id)


def _api_create_utub_tag_url(app: Flask, utub_id: int) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.CREATE_UTUB_TAG, utub_id=utub_id)


def _web_create_utub_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.UTUBS.CREATE_UTUB)


def _bearer(token: str) -> dict[str, str]:
    return {API_AUTH.AUTHORIZATION_HEADER: f"{API_AUTH.BEARER_PREFIX}{token}"}


def _token_for_user(app: Flask, user_id: int) -> str:
    with app.app_context():
        user: Users = Users.query.get(user_id)
        return create_access_token(user=user)


# ===========================================================================
# /api/v1 bearer surface: no CSRF + no X-Requested-With → succeeds
# ===========================================================================


def test_bearer_without_csrf_or_ajax_header_can_create_utub(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
    register_first_user,
):
    """
    GIVEN a validated user with a bearer token
    WHEN POST /api/v1/utubs is sent with no X-CSRFToken and no
         X-Requested-With header (as a native mobile client would)
    THEN the request is accepted (200) — the /api/v1 blueprint is CSRF-exempt
         and never requires an AJAX sentinel.
    """
    response = api_client.post(
        _api_create_utub_url(app),
        json={_UTUB_NAME_FIELD: _BEARER_TEST_UTUB_NAME},
        headers=bearer_headers_first_user,
    )

    assert response.status_code == 200
    response_data = response.get_json()
    assert response_data[STD_JSON.STATUS] == STD_JSON.SUCCESS


def test_bearer_without_csrf_or_ajax_header_can_create_url(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
    add_single_utub_as_user_without_logging_in,
):
    """
    GIVEN a validated user who is a member of UTub 1 (no URLs)
    WHEN POST /api/v1/utubs/1/urls is sent with no X-CSRFToken and no
         X-Requested-With header
    THEN the request is accepted (200).
    """
    response = api_client.post(
        _api_create_url_url(app, utub_id=1),
        json={
            MODELS.URL_STRING: _BEARER_TEST_URL_STRING,
            MODELS.URL_TITLE: _BEARER_TEST_URL_TITLE,
        },
        headers=bearer_headers_first_user,
    )

    assert response.status_code == 200
    response_data = response.get_json()
    assert response_data[STD_JSON.STATUS] == STD_JSON.SUCCESS


def test_bearer_without_csrf_or_ajax_header_can_create_utub_tag(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
    add_single_utub_as_user_without_logging_in,
):
    """
    GIVEN a validated user who is a member of UTub 1 (no tags)
    WHEN POST /api/v1/utubs/1/tags is sent with no X-CSRFToken and no
         X-Requested-With header
    THEN the request is accepted (200).
    """
    response = api_client.post(
        _api_create_utub_tag_url(app, utub_id=1),
        json={_TAG_STRING_FIELD: _BEARER_TEST_TAG_STRING},
        headers=bearer_headers_first_user,
    )

    assert response.status_code == 200
    response_data = response.get_json()
    assert response_data[STD_JSON.STATUS] == STD_JSON.SUCCESS


# ===========================================================================
# Web surface: AJAX enforcement (X-Requested-With: not-ajax → 302)
# ===========================================================================


def test_web_create_utub_without_ajax_header_is_302(
    app: Flask,
    login_first_user_with_register: Tuple[FlaskClient, str, object, Flask],
):
    """
    GIVEN a logged-in session client with a valid CSRF token
    WHEN POST /utubs is sent with X-Requested-With: not-ajax (overriding the
         header that AjaxFlaskLoginClient would normally inject)
    THEN 302 — the api_route AJAX sentinel rejects the non-AJAX request and
         redirects, mirroring test_ajax_enforcement.py's NON_AJAX_HEADERS pattern.
    """
    session_client, csrf_token, _, _ = login_first_user_with_register

    response = session_client.post(
        _web_create_utub_url(app),
        json={_UTUB_NAME_FIELD: _WEB_TEST_UTUB_NAME},
        headers={
            URL_VALIDATION.X_REQUESTED_WITH: _NON_AJAX_VALUE,
            _CSRF_HEADER_KEY: csrf_token,
        },
    )

    assert response.status_code == _AJAX_REDIRECT_STATUS


# ===========================================================================
# Web surface: missing CSRF (no X-CSRFToken → 403)
# ===========================================================================


def test_web_create_utub_without_csrf_is_403(
    app: Flask,
    login_first_user_with_register: Tuple[FlaskClient, str, object, Flask],
):
    """
    GIVEN a logged-in session client (AjaxFlaskLoginClient auto-injects the
         X-Requested-With: XMLHttpRequest header, satisfying the AJAX check)
    WHEN POST /utubs is sent WITHOUT the X-CSRFToken header
    THEN 403 — CSRFProtect rejects the request before any route logic runs,
         mirroring test_add_utub_with_no_csrf_token from the web integration
         suite (expected status verified from that test: 403).
    """
    session_client, _, _, _ = login_first_user_with_register

    # Do NOT include the CSRF token — AjaxFlaskLoginClient still adds the
    # X-Requested-With sentinel automatically, so only the CSRF check fires.
    response = session_client.post(
        _web_create_utub_url(app),
        json={_UTUB_NAME_FIELD: _WEB_TEST_UTUB_NAME},
    )

    assert response.status_code == _CSRF_MISSING_STATUS


# ===========================================================================
# /api/v1 surface: session cookie without Bearer → 401
# ===========================================================================


def test_session_client_without_bearer_cannot_access_api_v1_create_utub(
    app: Flask,
    login_first_user_with_register: Tuple[FlaskClient, str, object, Flask],
):
    """
    GIVEN a logged-in session client (AjaxFlaskLoginClient with a valid
         session cookie for user 1)
    WHEN POST /api/v1/utubs is called WITHOUT an Authorization: Bearer header
    THEN 401 — api_authentication_required requires the bearer-authenticated
         stamp that only load_user_from_request sets; Flask-Login's session
         fallback resolves current_user but never carries the stamp, so the
         session cookie alone must not grant access to the bearer surface.
    """
    session_client, _, _, _ = login_first_user_with_register

    response = session_client.post(
        _api_create_utub_url(app),
        json={_UTUB_NAME_FIELD: "SessionOnlyUTub"},
        # Deliberately no Authorization: Bearer header
    )

    assert response.status_code == 401
    response_data = response.get_json()
    assert response_data[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_data[STD_JSON.MESSAGE] == API_AUTH_FAILURE.AUTHENTICATION_REQUIRED


def test_session_client_with_bearer_header_is_still_refused_on_api_v1(
    app: Flask,
    login_first_user_with_register: Tuple[FlaskClient, str, object, Flask],
):
    """
    GIVEN a logged-in session client for user 1 that ALSO sends a valid
         bearer access token for user 1
    WHEN POST /api/v1/utubs is called with both credentials
    THEN 401 — Flask-Login resolves the session cookie BEFORE consulting the
         request loader, so the bearer-authenticated stamp is never set and
         the ambiguous request is refused rather than silently picking an
         identity source.
    """
    session_client, _, _, _ = login_first_user_with_register
    access_token = _token_for_user(app, user_id=1)

    response = session_client.post(
        _api_create_utub_url(app),
        json={_UTUB_NAME_FIELD: "AmbiguousAuthUTub"},
        headers=_bearer(access_token),
    )

    assert response.status_code == 401
    response_data = response.get_json()
    assert response_data[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_data[STD_JSON.MESSAGE] == API_AUTH_FAILURE.AUTHENTICATION_REQUIRED
