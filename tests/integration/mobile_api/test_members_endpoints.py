"""
Integration tests for the bearer-token Member endpoints:
  POST   /api/v1/utubs/<utub_id>/members
  DELETE /api/v1/utubs/<utub_id>/members/<user_id>

Conventions:
  - Uses api_client (plain FlaskClient, no session/CSRF).
  - URL built with url_for() inside app.test_request_context().
  - All JSON key constants imported from backend string modules.
  - pytestmark = pytest.mark.mobile_api
"""

from flask import Flask, url_for
from flask.testing import FlaskClient
import pytest

from backend import limiter
from backend.api_v1.services.tokens import create_access_token
from backend.members.constants import MEMBER_ADD_RATE_LIMIT
from backend.models.utub_members import Utub_Members
from backend.models.users import Users
from backend.utils.all_routes import ROUTES
from backend.utils.strings.api_auth_strs import API_AUTH, API_AUTH_FAILURE
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.user_strs import MEMBER_FAILURE, MEMBER_SUCCESS
from tests.models_for_test import valid_users

pytestmark = pytest.mark.mobile_api

# ---------------------------------------------------------------------------
# Constants for request body field names
# ---------------------------------------------------------------------------

_USERNAME_FIELD = "username"
_MEMBER_KEY = MEMBER_SUCCESS.MEMBER


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def _create_member_url(app: Flask, utub_id: int) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.CREATE_MEMBER, utub_id=utub_id)


def _remove_member_url(app: Flask, utub_id: int, user_id: int) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.REMOVE_MEMBER, utub_id=utub_id, user_id=user_id)


def _bearer(token: str) -> dict[str, str]:
    return {API_AUTH.AUTHORIZATION_HEADER: f"{API_AUTH.BEARER_PREFIX}{token}"}


def _token_for_user(app: Flask, user_id: int) -> str:
    with app.app_context():
        user: Users = Users.query.get(user_id)
        return create_access_token(user=user)


# ===========================================================================
# POST /api/v1/utubs/<utub_id>/members — add member
# ===========================================================================


def test_add_member_happy_path(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    every_user_makes_a_unique_utub,
):
    """
    GIVEN three users each with their own UTub (ids 1, 2, 3)
    WHEN creator of UTub 1 (user 1) POSTs to add user 2 by username
    THEN 200 with member object and utubID; DB association created

    Note: bearer headers are minted after every_user_makes_a_unique_utub runs
    (which registers all 3 users) to avoid fixture conflict with register_first_user.
    """
    user_1_headers = make_bearer_headers(_token_for_user(app, user_id=1))
    user_2_username = valid_users[1]["username"]

    with app.app_context():
        initial_member_count = Utub_Members.query.filter_by(utub_id=1).count()

    assert initial_member_count == 1

    response = api_client.post(
        _create_member_url(app, utub_id=1),
        json={_USERNAME_FIELD: user_2_username},
        headers=user_1_headers,
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == MEMBER_SUCCESS.MEMBER_ADDED
    assert response_json[_MEMBER_KEY][MODELS.USERNAME] == user_2_username

    with app.app_context():
        assert (
            Utub_Members.query.filter_by(utub_id=1).count() == initial_member_count + 1
        )


def test_add_member_no_token_is_401(app: Flask, api_client: FlaskClient):
    """No Authorization header → 401 JSON failure."""
    response = api_client.post(
        _create_member_url(app, utub_id=1),
        json={_USERNAME_FIELD: "someuser"},
    )

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.AUTHENTICATION_REQUIRED


def test_add_member_not_creator_is_403(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """
    GIVEN user 2 is a member (not creator) of UTub id=1
    WHEN user 2 tries to add another member
    THEN 403
    """
    user_2_token = _token_for_user(app, user_id=2)
    user_3_username = valid_users[2]["username"]

    response = api_client.post(
        _create_member_url(app, utub_id=1),
        json={_USERNAME_FIELD: user_3_username},
        headers=make_bearer_headers(user_2_token),
    )

    assert response.status_code == 403
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_add_member_missing_body_is_400(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
    add_single_utub_as_user_without_logging_in,
):
    """Missing required username field → 400 (schema validation failure)."""
    response = api_client.post(
        _create_member_url(app, utub_id=1),
        headers=bearer_headers_first_user,
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_add_member_nonexistent_user_is_400(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
    add_single_utub_as_user_without_logging_in,
):
    """
    GIVEN a valid creator token for UTub id=1
    WHEN POST /api/v1/utubs/1/members with a username that does not exist
    THEN 400 (service rejects unknown username)
    """
    response = api_client.post(
        _create_member_url(app, utub_id=1),
        json={_USERNAME_FIELD: "NonExistentUser9999"},
        headers=bearer_headers_first_user,
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


# ===========================================================================
# DELETE /api/v1/utubs/<utub_id>/members/<user_id> — remove member
# ===========================================================================


def test_remove_member_creator_removes_member_happy_path(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    add_multiple_users_to_utub_without_logging_in,
):
    """
    GIVEN UTub id=1 with creator (user 1) and members (users 2, 3)
    WHEN creator sends DELETE /api/v1/utubs/1/members/2
    THEN 200 with member object; DB association removed

    Note: bearer headers are minted after the multi-user fixture runs
    to avoid fixture conflict with register_first_user.
    """
    user_1_headers = make_bearer_headers(_token_for_user(app, user_id=1))

    with app.app_context():
        initial_member_count = Utub_Members.query.filter_by(utub_id=1).count()

    assert initial_member_count == 3

    response = api_client.delete(
        _remove_member_url(app, utub_id=1, user_id=2),
        headers=user_1_headers,
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == MEMBER_SUCCESS.MEMBER_REMOVED
    assert response_json[_MEMBER_KEY][MODELS.ID] == 2

    with app.app_context():
        assert (
            Utub_Members.query.filter_by(utub_id=1).count() == initial_member_count - 1
        )


def test_remove_member_self_removal_happy_path(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """
    GIVEN UTub id=1 with creator (user 1) and members (users 2, 3)
    WHEN user 2 (non-creator member) removes themselves
    THEN 200
    """
    user_2_token = _token_for_user(app, user_id=2)

    with app.app_context():
        initial_member_count = Utub_Members.query.filter_by(utub_id=1).count()

    assert initial_member_count == 3

    response = api_client.delete(
        _remove_member_url(app, utub_id=1, user_id=2),
        headers=make_bearer_headers(user_2_token),
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS

    with app.app_context():
        assert (
            Utub_Members.query.filter_by(utub_id=1).count() == initial_member_count - 1
        )


def test_remove_member_no_token_is_401(app: Flask, api_client: FlaskClient):
    """No Authorization header → 401."""
    response = api_client.delete(_remove_member_url(app, utub_id=1, user_id=2))

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.AUTHENTICATION_REQUIRED


def test_remove_member_non_member_cannot_remove_other(
    app: Flask,
    api_client: FlaskClient,
    every_user_makes_a_unique_utub,
    make_bearer_headers,
):
    """
    GIVEN user 1 is not a member of UTub id=2 (owned by user 2)
    WHEN user 1 tries DELETE /api/v1/utubs/2/members/3
    THEN 404 (not a member of that UTub → utub_membership_required returns 404)
    """
    user_1_token = _token_for_user(app, user_id=1)

    response = api_client.delete(
        _remove_member_url(app, utub_id=2, user_id=3),
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 404
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_remove_member_member_cannot_remove_other_member(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """
    GIVEN UTub id=1 with creator (user 1) and members (users 2, 3)
    WHEN user 2 tries to remove user 3
    THEN 403 (only creator may remove others)
    """
    user_2_token = _token_for_user(app, user_id=2)

    response = api_client.delete(
        _remove_member_url(app, utub_id=1, user_id=3),
        headers=make_bearer_headers(user_2_token),
    )

    assert response.status_code == 403
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        response_json[STD_JSON.MESSAGE] == MEMBER_FAILURE.INVALID_PERMISSION_TO_REMOVE
    )


def test_remove_member_creator_cannot_remove_self(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    add_multiple_users_to_utub_without_logging_in,
):
    """
    GIVEN user 1 is the creator of UTub id=1
    WHEN user 1 tries to remove themselves (user_id=1)
    THEN 400 (creator cannot remove themselves)

    Note: bearer headers minted after multi-user fixture to avoid fixture conflict.
    """
    user_1_headers = make_bearer_headers(_token_for_user(app, user_id=1))

    response = api_client.delete(
        _remove_member_url(app, utub_id=1, user_id=1),
        headers=user_1_headers,
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        response_json[STD_JSON.MESSAGE] == MEMBER_FAILURE.CREATOR_CANNOT_REMOVE_THEMSELF
    )


def test_remove_member_nonexistent_member_is_404(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
    add_single_utub_as_user_without_logging_in,
):
    """
    GIVEN UTub id=1 with only creator (user 1); user 2 is not a member
    WHEN creator tries to remove user 2
    THEN 404 (member does not exist in UTub)
    """
    response = api_client.delete(
        _remove_member_url(app, utub_id=1, user_id=2),
        headers=bearer_headers_first_user,
    )

    assert response.status_code == 404
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


# ===========================================================================
# Per-IP Flask-Limiter 429 on the /api/v1 add-member twin (JSON envelope)
# ===========================================================================


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


def test_add_member_rate_limit_returns_json_429(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    every_user_makes_a_unique_utub,
):
    """
    GIVEN the per-IP MEMBER_ADD_RATE_LIMIT (30/minute) on POST
        /api/v1/utubs/<id>/members
    WHEN a 31st add-member request arrives within the window
    THEN a 429 is returned as the JSON ErrorResponse envelope (never HTML).
    """
    user_1_headers = make_bearer_headers(_token_for_user(app, user_id=1))
    user_2_username = valid_users[1]["username"]
    add_url = _create_member_url(app, utub_id=1)
    add_body = {_USERNAME_FIELD: user_2_username}
    allowed_per_window = int(MEMBER_ADD_RATE_LIMIT.split("/")[0])

    _enable_limiter(app)
    try:
        for _attempt_number in range(allowed_per_window):
            response = api_client.post(add_url, json=add_body, headers=user_1_headers)
            assert response.status_code != 429

        rate_limited_response = api_client.post(
            add_url, json=add_body, headers=user_1_headers
        )
        assert rate_limited_response.status_code == 429
        assert rate_limited_response.is_json
        rate_limited_json = rate_limited_response.get_json()
        assert rate_limited_json[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert rate_limited_json[STD_JSON.MESSAGE] == STD_JSON.TOO_MANY_REQUESTS
    finally:
        _disable_limiter()
