"""
Integration tests for the bearer-token UTub endpoints:
  POST   /api/v1/utubs
  GET    /api/v1/utubs
  GET    /api/v1/utubs/<utub_id>
  PATCH  /api/v1/utubs/<utub_id>/name
  PATCH  /api/v1/utubs/<utub_id>/description
  DELETE /api/v1/utubs/<utub_id>

Conventions:
  - Uses api_client (plain FlaskClient, no session/CSRF/AjaxFlaskLoginClient).
  - URL built with url_for() inside app.test_request_context().
  - All JSON key constants are imported from backend string modules.
  - pytestmark = pytest.mark.mobile_api
"""

from flask import Flask, url_for
from flask.testing import FlaskClient
import pytest

from backend.api_v1.services.tokens import create_access_token
from backend.models.utubs import Utubs
from backend.models.users import Users
from backend.utils.all_routes import ROUTES
from backend.utils.strings.api_auth_strs import API_AUTH, API_AUTH_FAILURE
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.utub_strs import UTUB_NAME, UTUB_SUCCESS
from tests.models_for_test import valid_empty_utub_1

pytestmark = pytest.mark.mobile_api

# ---------------------------------------------------------------------------
# URL helpers — resolved inside test_request_context so url_for works
# ---------------------------------------------------------------------------

_UTUB_NAME_FIELD = "utubName"
_UTUB_DESC_FIELD = "utubDescription"
_UTUBS_KEY = MODELS.UTUBS


def _create_utub_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.CREATE_UTUB)


def _get_utubs_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.GET_UTUBS)


def _get_single_utub_url(app: Flask, utub_id: int) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.GET_SINGLE_UTUB, utub_id=utub_id)


def _update_name_url(app: Flask, utub_id: int) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.UPDATE_UTUB_NAME, utub_id=utub_id)


def _update_desc_url(app: Flask, utub_id: int) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.UPDATE_UTUB_DESC, utub_id=utub_id)


def _delete_utub_url(app: Flask, utub_id: int) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.DELETE_UTUB, utub_id=utub_id)


def _bearer(token: str) -> dict[str, str]:
    return {API_AUTH.AUTHORIZATION_HEADER: f"{API_AUTH.BEARER_PREFIX}{token}"}


def _token_for_user(app: Flask, user_id: int) -> str:
    with app.app_context():
        user: Users = Users.query.get(user_id)
        return create_access_token(user=user)


# ===========================================================================
# POST /api/v1/utubs — create UTub
# ===========================================================================


def test_create_utub_happy_path(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
    register_first_user,
):
    """
    GIVEN a validated user with a bearer token
    WHEN POST /api/v1/utubs with a valid name and description
    THEN 200 with utubID, utubName, utubDescription, utubCreatorID; DB row created
    """
    with app.app_context():
        initial_count = Utubs.query.count()

    assert initial_count == 0

    response = api_client.post(
        _create_utub_url(app),
        json={
            _UTUB_NAME_FIELD: valid_empty_utub_1[MODELS.NAME],
            _UTUB_DESC_FIELD: valid_empty_utub_1[MODELS.UTUB_DESCRIPTION],
        },
        headers=bearer_headers_first_user,
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[UTUB_SUCCESS.UTUB_NAME] == valid_empty_utub_1[MODELS.NAME]
    assert (
        response_json[UTUB_SUCCESS.UTUB_DESCRIPTION]
        == valid_empty_utub_1[MODELS.UTUB_DESCRIPTION]
    )
    assert response_json[UTUB_SUCCESS.UTUB_CREATOR_ID] == 1

    utub_id = response_json[UTUB_SUCCESS.UTUB_ID]
    with app.app_context():
        assert Utubs.query.count() == initial_count + 1
        created_utub: Utubs = Utubs.query.get(utub_id)
        assert created_utub is not None
        assert created_utub.utub_creator == 1


def test_create_utub_no_token_is_401(app: Flask, api_client: FlaskClient):
    """
    GIVEN no Authorization header
    WHEN POST /api/v1/utubs
    THEN 401 JSON failure envelope
    """
    response = api_client.post(
        _create_utub_url(app),
        json={_UTUB_NAME_FIELD: "SomeName"},
    )

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.AUTHENTICATION_REQUIRED


def test_create_utub_unvalidated_email_is_403(
    app: Flask,
    api_client: FlaskClient,
    access_token_unvalidated_user: str,
):
    """
    GIVEN a bearer token for a user whose email is NOT validated
    WHEN POST /api/v1/utubs
    THEN 403 with EMAIL_VALIDATION_REQUIRED message (closes Phase 3 gap)
    """
    response = api_client.post(
        _create_utub_url(app),
        json={_UTUB_NAME_FIELD: "SomeName"},
        headers=_bearer(access_token_unvalidated_user),
    )

    assert response.status_code == 403
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.EMAIL_VALIDATION_REQUIRED


def test_create_utub_missing_body_is_400(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
    register_first_user,
):
    """
    GIVEN a validated bearer token
    WHEN POST /api/v1/utubs with no JSON body
    THEN 400 (schema validation failure)
    """
    response = api_client.post(
        _create_utub_url(app),
        headers=bearer_headers_first_user,
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


# ===========================================================================
# GET /api/v1/utubs — list UTubs
# ===========================================================================


def test_get_utubs_happy_path(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
    add_single_utub_as_user_without_logging_in,
):
    """
    GIVEN a validated user with one UTub
    WHEN GET /api/v1/utubs
    THEN 200 with a utubs list containing one item
    """
    response = api_client.get(
        _get_utubs_url(app),
        headers=bearer_headers_first_user,
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    utubs_list = response_json[_UTUBS_KEY]
    assert len(utubs_list) == 1
    assert utubs_list[0][MODELS.NAME] == valid_empty_utub_1[MODELS.NAME]


def test_get_utubs_empty_returns_empty_list(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
    register_first_user,
):
    """
    GIVEN a validated user who is not a member of any UTub
    WHEN GET /api/v1/utubs
    THEN 200 with an empty utubs list
    """
    response = api_client.get(
        _get_utubs_url(app),
        headers=bearer_headers_first_user,
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[_UTUBS_KEY] == []


def test_get_utubs_no_token_is_401(app: Flask, api_client: FlaskClient):
    """No Authorization header → 401 JSON failure."""
    response = api_client.get(_get_utubs_url(app))

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.AUTHENTICATION_REQUIRED


def test_get_utubs_unvalidated_email_is_403(
    app: Flask,
    api_client: FlaskClient,
    access_token_unvalidated_user: str,
):
    """
    GIVEN a bearer token for a user whose email is NOT validated
    WHEN GET /api/v1/utubs
    THEN 403 with EMAIL_VALIDATION_REQUIRED message (closes Phase 3 review gap)
    """
    response = api_client.get(
        _get_utubs_url(app),
        headers=_bearer(access_token_unvalidated_user),
    )

    assert response.status_code == 403
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.EMAIL_VALIDATION_REQUIRED


# ===========================================================================
# GET /api/v1/utubs/<utub_id> — single UTub detail
# ===========================================================================


def test_get_single_utub_happy_path(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
    add_single_utub_as_user_without_logging_in,
):
    """
    GIVEN a validated user who is a member of UTub with id=1
    WHEN GET /api/v1/utubs/1
    THEN 200 with members, urls, tags, isCreator fields
    """
    response = api_client.get(
        _get_single_utub_url(app, utub_id=1),
        headers=bearer_headers_first_user,
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert MODELS.MEMBERS in response_json
    assert MODELS.URLS in response_json
    assert MODELS.TAGS in response_json
    assert MODELS.IS_CREATOR in response_json
    assert response_json[MODELS.NAME] == valid_empty_utub_1[MODELS.NAME]


def test_get_single_utub_no_token_is_401(app: Flask, api_client: FlaskClient):
    """No Authorization header → 401."""
    response = api_client.get(_get_single_utub_url(app, utub_id=1))

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_get_single_utub_not_member_is_404(
    app: Flask,
    api_client: FlaskClient,
    every_user_makes_a_unique_utub,
    make_bearer_headers,
):
    """
    GIVEN three users each with their own UTub (ids 1, 2, 3)
    WHEN user 1 tries GET /api/v1/utubs/2 (user 2's UTub)
    THEN 404 (not a member)
    """
    user_1_token = _token_for_user(app, user_id=1)

    response = api_client.get(
        _get_single_utub_url(app, utub_id=2),
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 404
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


# ===========================================================================
# PATCH /api/v1/utubs/<utub_id>/name
# ===========================================================================

_UPDATED_NAME = "Updated UTub Name"


def test_update_utub_name_happy_path(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
    add_single_utub_as_user_without_logging_in,
):
    """
    GIVEN the creator of a UTub with id=1
    WHEN PATCH /api/v1/utubs/1/name with a new name
    THEN 200 with utubID and utubName; DB row updated
    """
    response = api_client.patch(
        _update_name_url(app, utub_id=1),
        json={_UTUB_NAME_FIELD: _UPDATED_NAME},
        headers=bearer_headers_first_user,
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[UTUB_NAME] == _UPDATED_NAME

    with app.app_context():
        utub: Utubs = Utubs.query.get(1)
        assert utub.name == _UPDATED_NAME


def test_update_utub_name_no_token_is_401(app: Flask, api_client: FlaskClient):
    """No Authorization header → 401."""
    response = api_client.patch(
        _update_name_url(app, utub_id=1),
        json={_UTUB_NAME_FIELD: _UPDATED_NAME},
    )

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_update_utub_name_not_creator_is_403(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """
    GIVEN user 2 is a member (not creator) of UTub id=1
    WHEN user 2 sends PATCH /api/v1/utubs/1/name
    THEN 403
    """
    user_2_token = _token_for_user(app, user_id=2)

    response = api_client.patch(
        _update_name_url(app, utub_id=1),
        json={_UTUB_NAME_FIELD: _UPDATED_NAME},
        headers=make_bearer_headers(user_2_token),
    )

    assert response.status_code == 403
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_update_utub_name_missing_body_is_400(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
    add_single_utub_as_user_without_logging_in,
):
    """Missing required utubName field → 400."""
    response = api_client.patch(
        _update_name_url(app, utub_id=1),
        headers=bearer_headers_first_user,
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


# ===========================================================================
# PATCH /api/v1/utubs/<utub_id>/description
# ===========================================================================

_UPDATED_DESC = "Updated description text."


def test_update_utub_desc_happy_path(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
    add_single_utub_as_user_without_logging_in,
):
    """
    GIVEN the creator of UTub id=1
    WHEN PATCH /api/v1/utubs/1/description with a new description
    THEN 200 with utubID and utubDescription
    """
    response = api_client.patch(
        _update_desc_url(app, utub_id=1),
        json={_UTUB_DESC_FIELD: _UPDATED_DESC},
        headers=bearer_headers_first_user,
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[UTUB_SUCCESS.UTUB_DESCRIPTION] == _UPDATED_DESC


def test_update_utub_desc_not_creator_is_403(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """Member (not creator) attempting desc update → 403."""
    user_2_token = _token_for_user(app, user_id=2)

    response = api_client.patch(
        _update_desc_url(app, utub_id=1),
        json={_UTUB_DESC_FIELD: _UPDATED_DESC},
        headers=make_bearer_headers(user_2_token),
    )

    assert response.status_code == 403
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


# ===========================================================================
# DELETE /api/v1/utubs/<utub_id>
# ===========================================================================


def test_delete_utub_happy_path(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
    add_single_utub_as_user_without_logging_in,
):
    """
    GIVEN the creator of UTub id=1
    WHEN DELETE /api/v1/utubs/1
    THEN 200 with utubID and utubName; DB row removed
    """
    with app.app_context():
        initial_count = Utubs.query.count()

    assert initial_count == 1

    response = api_client.delete(
        _delete_utub_url(app, utub_id=1),
        headers=bearer_headers_first_user,
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[UTUB_SUCCESS.UTUB_ID] == 1

    with app.app_context():
        assert Utubs.query.count() == 0


def test_delete_utub_no_token_is_401(app: Flask, api_client: FlaskClient):
    """No Authorization header → 401."""
    response = api_client.delete(_delete_utub_url(app, utub_id=1))

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_delete_utub_not_creator_is_403(
    app: Flask,
    api_client: FlaskClient,
    add_multiple_users_to_utub_without_logging_in,
    make_bearer_headers,
):
    """Member (not creator) attempting delete → 403."""
    user_2_token = _token_for_user(app, user_id=2)

    response = api_client.delete(
        _delete_utub_url(app, utub_id=1),
        headers=make_bearer_headers(user_2_token),
    )

    assert response.status_code == 403
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_delete_utub_nonexistent_is_404(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
    register_first_user,
):
    """Attempting to delete a UTub that does not exist → 404."""
    response = api_client.delete(
        _delete_utub_url(app, utub_id=9999),
        headers=bearer_headers_first_user,
    )

    assert response.status_code == 404
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
