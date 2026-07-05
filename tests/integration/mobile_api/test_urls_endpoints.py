"""
Integration tests for the bearer-token URL endpoints:
  POST   /api/v1/utubs/<utub_id>/urls
  GET    /api/v1/utubs/<utub_id>/urls/<utub_url_id>
  PATCH  /api/v1/utubs/<utub_id>/urls/<utub_url_id>
  PATCH  /api/v1/utubs/<utub_id>/urls/<utub_url_id>/title
  DELETE /api/v1/utubs/<utub_id>/urls/<utub_url_id>

Conventions:
  - Uses api_client (plain FlaskClient, no session/CSRF/AjaxFlaskLoginClient).
  - URL built with url_for() inside app.test_request_context().
  - All JSON key constants are imported from backend string modules.
  - pytestmark = pytest.mark.mobile_api
"""

from typing import Callable

from flask import Flask, url_for
from flask.testing import FlaskClient
import pytest

from backend.api_v1.services.tokens import create_access_token
from backend.models.users import Users
from backend.models.utub_urls import Utub_Urls
from backend.utils.all_routes import ROUTES
from backend.utils.strings.api_auth_strs import API_AUTH, API_AUTH_FAILURE
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.url_strs import URL_SUCCESS
from backend.utils.strings.utub_strs import UTUB_NAME
from tests.models_for_test import valid_url_strings

pytestmark = pytest.mark.mobile_api

# ---------------------------------------------------------------------------
# Module-level test-data constants
# ---------------------------------------------------------------------------

_TEST_URL_TITLE = "My Test URL Title"
_UPDATED_URL_STRING = valid_url_strings[2]  # "https://www.efg.com/" — not in UTub 1
_UPDATED_URL_TITLE = "My Updated URL Title"

# URL prefix set by add_one_url_to_each_utub_no_tags for UTub 1 (user 1's URL)
_UTUB_1_URL_STRING = valid_url_strings[0]  # "https://www.abc.com/"
_UTUB_1_URL_TITLE = f"This is {_UTUB_1_URL_STRING}"

# ---------------------------------------------------------------------------
# URL helpers — resolved inside test_request_context so url_for works
# ---------------------------------------------------------------------------


def _create_url_url(app: Flask, utub_id: int) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.CREATE_URL, utub_id=utub_id)


def _get_url_url(app: Flask, utub_id: int, utub_url_id: int) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.GET_URL, utub_id=utub_id, utub_url_id=utub_url_id)


def _update_url_url(app: Flask, utub_id: int, utub_url_id: int) -> str:
    with app.test_request_context():
        return url_for(
            ROUTES.API_V1.UPDATE_URL, utub_id=utub_id, utub_url_id=utub_url_id
        )


def _update_url_title_url(app: Flask, utub_id: int, utub_url_id: int) -> str:
    with app.test_request_context():
        return url_for(
            ROUTES.API_V1.UPDATE_URL_TITLE, utub_id=utub_id, utub_url_id=utub_url_id
        )


def _delete_url_url(app: Flask, utub_id: int, utub_url_id: int) -> str:
    with app.test_request_context():
        return url_for(
            ROUTES.API_V1.DELETE_URL, utub_id=utub_id, utub_url_id=utub_url_id
        )


def _bearer(token: str) -> dict[str, str]:
    return {API_AUTH.AUTHORIZATION_HEADER: f"{API_AUTH.BEARER_PREFIX}{token}"}


def _token_for_user(app: Flask, user_id: int) -> str:
    with app.app_context():
        user: Users = Users.query.get(user_id)
        return create_access_token(user=user)


# ===========================================================================
# POST /api/v1/utubs/<utub_id>/urls — create URL
# ===========================================================================


def test_create_url_happy_path(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
    add_single_utub_as_user_without_logging_in,
):
    """
    GIVEN a validated user (ID=1) who is a member of UTub 1 with no URLs
    WHEN POST /api/v1/utubs/1/urls with a valid urlString and urlTitle
    THEN 200 with utubID, addedByUserID, and URL object; Utub_Urls row created with user_id=1
    """
    with app.app_context():
        initial_count = Utub_Urls.query.count()

    assert initial_count == 0

    response = api_client.post(
        _create_url_url(app, utub_id=1),
        json={
            MODELS.URL_STRING: _UTUB_1_URL_STRING,
            MODELS.URL_TITLE: _TEST_URL_TITLE,
        },
        headers=bearer_headers_first_user,
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[URL_SUCCESS.UTUB_ID] == 1
    assert response_json[URL_SUCCESS.ADDED_BY] == 1
    assert MODELS.URL in response_json

    with app.app_context():
        assert Utub_Urls.query.count() == initial_count + 1
        created_utub_url: Utub_Urls = Utub_Urls.query.first()
        assert created_utub_url is not None
        assert created_utub_url.user_id == 1
        assert created_utub_url.utub_id == 1


def test_create_url_no_token_is_401(
    app: Flask,
    api_client: FlaskClient,
    add_single_utub_as_user_without_logging_in,
):
    """
    GIVEN no Authorization header
    WHEN POST /api/v1/utubs/1/urls
    THEN 401 JSON failure envelope
    """
    response = api_client.post(
        _create_url_url(app, utub_id=1),
        json={MODELS.URL_STRING: _UTUB_1_URL_STRING, MODELS.URL_TITLE: _TEST_URL_TITLE},
    )

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.AUTHENTICATION_REQUIRED


def test_create_url_unvalidated_email_is_403(
    app: Flask,
    api_client: FlaskClient,
    access_token_unvalidated_user: str,
):
    """
    GIVEN a bearer token for a user whose email is NOT validated
    WHEN POST /api/v1/utubs/9999/urls
    THEN 403 EMAIL_VALIDATION_REQUIRED (auth layer rejects before UTub lookup)
    """
    response = api_client.post(
        _create_url_url(app, utub_id=9999),
        json={MODELS.URL_STRING: _UTUB_1_URL_STRING, MODELS.URL_TITLE: _TEST_URL_TITLE},
        headers=_bearer(access_token_unvalidated_user),
    )

    assert response.status_code == 403
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.EMAIL_VALIDATION_REQUIRED


def test_create_url_non_member_utub_is_404(
    app: Flask,
    api_client: FlaskClient,
    every_user_makes_a_unique_utub,
    make_bearer_headers: Callable[[str], dict[str, str]],
):
    """
    GIVEN users 1-3 each owning a unique UTub (IDs 1-3), user 1 is only member of UTub 1
    WHEN user 1 POSTs to /api/v1/utubs/2/urls (UTub owned by user 2)
    THEN 404 (user 1 is not a member of UTub 2)
    """
    user_1_token = _token_for_user(app, user_id=1)

    response = api_client.post(
        _create_url_url(app, utub_id=2),
        json={MODELS.URL_STRING: _UTUB_1_URL_STRING, MODELS.URL_TITLE: _TEST_URL_TITLE},
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 404
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_create_url_missing_body_is_400(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
    add_single_utub_as_user_without_logging_in,
):
    """
    GIVEN a validated bearer token and UTub 1 existing
    WHEN POST /api/v1/utubs/1/urls with no JSON body
    THEN 400 schema validation failure
    """
    response = api_client.post(
        _create_url_url(app, utub_id=1),
        headers=bearer_headers_first_user,
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_create_url_duplicate_is_409(
    app: Flask,
    api_client: FlaskClient,
    add_one_url_to_each_utub_no_tags,
    make_bearer_headers: Callable[[str], dict[str, str]],
):
    """
    GIVEN UTub 1 already contains URL with string "https://www.abc.com/"
    WHEN user 1 (creator/member of UTub 1) POSTs the same URL string again
    THEN 409 with URL_IN_UTUB message
    """
    user_1_token = _token_for_user(app, user_id=1)

    with app.app_context():
        initial_count = Utub_Urls.query.count()

    response = api_client.post(
        _create_url_url(app, utub_id=1),
        json={MODELS.URL_STRING: _UTUB_1_URL_STRING, MODELS.URL_TITLE: _TEST_URL_TITLE},
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 409
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE

    with app.app_context():
        assert Utub_Urls.query.count() == initial_count


# ===========================================================================
# GET /api/v1/utubs/<utub_id>/urls/<utub_url_id> — retrieve URL
# ===========================================================================


def test_get_url_happy_path(
    app: Flask,
    api_client: FlaskClient,
    add_one_url_to_each_utub_no_tags,
    make_bearer_headers: Callable[[str], dict[str, str]],
):
    """
    GIVEN UTub 1 contains utub_url_id=1 added by user 1 (who is the creator)
    WHEN user 1 GETs /api/v1/utubs/1/urls/1
    THEN 200 with URL object containing utubUrlID, urlString, urlTitle, urlTags
    """
    user_1_token = _token_for_user(app, user_id=1)

    response = api_client.get(
        _get_url_url(app, utub_id=1, utub_url_id=1),
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == URL_SUCCESS.URL_FOUND_IN_UTUB

    url_object = response_json[MODELS.URL]
    assert url_object[MODELS.UTUB_URL_ID] == 1
    assert url_object[MODELS.URL_STRING] == _UTUB_1_URL_STRING
    assert url_object[MODELS.URL_TITLE] == _UTUB_1_URL_TITLE
    assert MODELS.URL_TAGS in url_object


def test_get_url_no_token_is_401(
    app: Flask,
    api_client: FlaskClient,
    add_one_url_to_each_utub_no_tags,
):
    """
    GIVEN no Authorization header
    WHEN GET /api/v1/utubs/1/urls/1
    THEN 401 JSON failure envelope
    """
    response = api_client.get(_get_url_url(app, utub_id=1, utub_url_id=1))

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.AUTHENTICATION_REQUIRED


def test_get_url_wrong_utub_is_404(
    app: Flask,
    api_client: FlaskClient,
    add_one_url_and_all_users_to_each_utub_no_tags,
    make_bearer_headers: Callable[[str], dict[str, str]],
):
    """
    GIVEN user 1 is a member of both UTub 1 and UTub 2; utub_url_id=2 belongs to UTub 2
    WHEN user 1 GETs /api/v1/utubs/1/urls/2 (utub_url_id=2 is in UTub 2, not UTub 1)
    THEN 404 (URL not in the requested UTub)
    """
    user_1_token = _token_for_user(app, user_id=1)

    response = api_client.get(
        _get_url_url(app, utub_id=1, utub_url_id=2),
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 404
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_get_url_non_member_is_404(
    app: Flask,
    api_client: FlaskClient,
    add_one_url_to_each_utub_no_tags,
    make_bearer_headers: Callable[[str], dict[str, str]],
):
    """
    GIVEN user 1 is not a member of UTub 2; UTub 2 has utub_url_id=2
    WHEN user 1 GETs /api/v1/utubs/2/urls/2
    THEN 404 (not a member of UTub 2)
    """
    user_1_token = _token_for_user(app, user_id=1)

    response = api_client.get(
        _get_url_url(app, utub_id=2, utub_url_id=2),
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 404
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


# ===========================================================================
# PATCH /api/v1/utubs/<utub_id>/urls/<utub_url_id> — update URL string
# ===========================================================================


def test_update_url_happy_path(
    app: Flask,
    api_client: FlaskClient,
    add_one_url_and_all_users_to_each_utub_no_tags,
    make_bearer_headers: Callable[[str], dict[str, str]],
):
    """
    GIVEN user 1 is the creator of UTub 1 and added utub_url_id=1 (URL string = "https://www.abc.com/")
    WHEN user 1 PATCHes /api/v1/utubs/1/urls/1 with a new urlString
    THEN 200 with utubID, utubName, and updated URL object; DB row reflects new URL
    """
    user_1_token = _token_for_user(app, user_id=1)

    with app.app_context():
        utub_url: Utub_Urls = Utub_Urls.query.get(1)
        assert utub_url.standalone_url.url_string == _UTUB_1_URL_STRING

    response = api_client.patch(
        _update_url_url(app, utub_id=1, utub_url_id=1),
        json={MODELS.URL_STRING: _UPDATED_URL_STRING},
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[URL_SUCCESS.UTUB_ID] == 1
    assert UTUB_NAME in response_json
    url_object = response_json[MODELS.URL]
    assert url_object[MODELS.URL_STRING] == _UPDATED_URL_STRING

    with app.app_context():
        updated_utub_url: Utub_Urls = Utub_Urls.query.get(1)
        assert updated_utub_url.standalone_url.url_string == _UPDATED_URL_STRING


def test_update_url_non_adder_member_is_403(
    app: Flask,
    api_client: FlaskClient,
    add_one_url_and_all_users_to_each_utub_no_tags,
    make_bearer_headers: Callable[[str], dict[str, str]],
):
    """
    GIVEN user 1 is a member of UTub 2 but did NOT add utub_url_id=2 and is NOT the creator of UTub 2
    WHEN user 1 PATCHes /api/v1/utubs/2/urls/2 with a new urlString
    THEN 403 (neither URL adder nor UTub creator)
    """
    user_1_token = _token_for_user(app, user_id=1)

    response = api_client.patch(
        _update_url_url(app, utub_id=2, utub_url_id=2),
        json={MODELS.URL_STRING: _UPDATED_URL_STRING},
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 403
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_update_url_no_token_is_401(
    app: Flask,
    api_client: FlaskClient,
    add_one_url_to_each_utub_no_tags,
):
    """
    GIVEN no Authorization header
    WHEN PATCH /api/v1/utubs/1/urls/1
    THEN 401 JSON failure envelope
    """
    response = api_client.patch(
        _update_url_url(app, utub_id=1, utub_url_id=1),
        json={MODELS.URL_STRING: _UPDATED_URL_STRING},
    )

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.AUTHENTICATION_REQUIRED


def test_update_url_missing_body_is_400(
    app: Flask,
    api_client: FlaskClient,
    add_one_url_and_all_users_to_each_utub_no_tags,
    make_bearer_headers: Callable[[str], dict[str, str]],
):
    """
    GIVEN user 1 is the creator of UTub 1 and added utub_url_id=1
    WHEN PATCH /api/v1/utubs/1/urls/1 with no JSON body
    THEN 400 schema validation failure
    """
    user_1_token = _token_for_user(app, user_id=1)

    response = api_client.patch(
        _update_url_url(app, utub_id=1, utub_url_id=1),
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


# ===========================================================================
# PATCH /api/v1/utubs/<utub_id>/urls/<utub_url_id>/title — update URL title
# ===========================================================================


def test_update_url_title_happy_path(
    app: Flask,
    api_client: FlaskClient,
    add_one_url_and_all_users_to_each_utub_no_tags,
    make_bearer_headers: Callable[[str], dict[str, str]],
):
    """
    GIVEN user 1 is the creator of UTub 1 and added utub_url_id=1 (title = "This is https://www.abc.com/")
    WHEN user 1 PATCHes /api/v1/utubs/1/urls/1/title with a new urlTitle
    THEN 200 with URL object reflecting the new title; DB row updated
    """
    user_1_token = _token_for_user(app, user_id=1)

    with app.app_context():
        utub_url: Utub_Urls = Utub_Urls.query.get(1)
        assert utub_url.url_title == _UTUB_1_URL_TITLE

    response = api_client.patch(
        _update_url_title_url(app, utub_id=1, utub_url_id=1),
        json={MODELS.URL_TITLE: _UPDATED_URL_TITLE},
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    url_object = response_json[MODELS.URL]
    assert url_object[MODELS.URL_TITLE] == _UPDATED_URL_TITLE

    with app.app_context():
        updated_utub_url: Utub_Urls = Utub_Urls.query.get(1)
        assert updated_utub_url.url_title == _UPDATED_URL_TITLE


def test_update_url_title_non_adder_member_is_403(
    app: Flask,
    api_client: FlaskClient,
    add_one_url_and_all_users_to_each_utub_no_tags,
    make_bearer_headers: Callable[[str], dict[str, str]],
):
    """
    GIVEN user 1 is a member of UTub 2 but did NOT add utub_url_id=2 and is NOT the creator of UTub 2
    WHEN user 1 PATCHes /api/v1/utubs/2/urls/2/title with a new urlTitle
    THEN 403 (neither URL adder nor UTub creator)
    """
    user_1_token = _token_for_user(app, user_id=1)

    response = api_client.patch(
        _update_url_title_url(app, utub_id=2, utub_url_id=2),
        json={MODELS.URL_TITLE: _UPDATED_URL_TITLE},
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 403
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_update_url_title_no_token_is_401(
    app: Flask,
    api_client: FlaskClient,
    add_one_url_to_each_utub_no_tags,
):
    """
    GIVEN no Authorization header
    WHEN PATCH /api/v1/utubs/1/urls/1/title
    THEN 401 JSON failure envelope
    """
    response = api_client.patch(
        _update_url_title_url(app, utub_id=1, utub_url_id=1),
        json={MODELS.URL_TITLE: _UPDATED_URL_TITLE},
    )

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.AUTHENTICATION_REQUIRED


def test_update_url_title_missing_body_is_400(
    app: Flask,
    api_client: FlaskClient,
    add_one_url_and_all_users_to_each_utub_no_tags,
    make_bearer_headers: Callable[[str], dict[str, str]],
):
    """
    GIVEN user 1 is the creator of UTub 1 and added utub_url_id=1
    WHEN PATCH /api/v1/utubs/1/urls/1/title with no JSON body
    THEN 400 schema validation failure
    """
    user_1_token = _token_for_user(app, user_id=1)

    response = api_client.patch(
        _update_url_title_url(app, utub_id=1, utub_url_id=1),
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


# ===========================================================================
# DELETE /api/v1/utubs/<utub_id>/urls/<utub_url_id> — delete URL
# ===========================================================================


def test_delete_url_happy_path(
    app: Flask,
    api_client: FlaskClient,
    add_one_url_to_each_utub_no_tags,
    make_bearer_headers: Callable[[str], dict[str, str]],
):
    """
    GIVEN user 1 is the creator of UTub 1 and added utub_url_id=1; 3 Utub_Urls rows total
    WHEN user 1 DELETEs /api/v1/utubs/1/urls/1
    THEN 200 with utubID, URL object, and tagCountsInUtub; Utub_Urls count decreases by 1
    """
    user_1_token = _token_for_user(app, user_id=1)

    with app.app_context():
        initial_utub_urls_count = Utub_Urls.query.count()

    assert initial_utub_urls_count == 3

    response = api_client.delete(
        _delete_url_url(app, utub_id=1, utub_url_id=1),
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == URL_SUCCESS.URL_REMOVED
    assert response_json[URL_SUCCESS.UTUB_ID] == 1
    assert MODELS.URL in response_json
    assert URL_SUCCESS.TAG_COUNTS_MODIFIED in response_json

    url_object = response_json[MODELS.URL]
    assert url_object[MODELS.UTUB_URL_ID] == 1
    assert url_object[MODELS.URL_STRING] == _UTUB_1_URL_STRING

    with app.app_context():
        assert Utub_Urls.query.count() == initial_utub_urls_count - 1
        assert Utub_Urls.query.get(1) is None


def test_delete_url_non_adder_member_is_403(
    app: Flask,
    api_client: FlaskClient,
    add_one_url_and_all_users_to_each_utub_no_tags,
    make_bearer_headers: Callable[[str], dict[str, str]],
):
    """
    GIVEN user 1 is a member of UTub 2 but did NOT add utub_url_id=2 and is NOT the creator of UTub 2
    WHEN user 1 DELETEs /api/v1/utubs/2/urls/2
    THEN 403 (neither URL adder nor UTub creator)
    """
    user_1_token = _token_for_user(app, user_id=1)

    with app.app_context():
        initial_utub_urls_count = Utub_Urls.query.count()

    response = api_client.delete(
        _delete_url_url(app, utub_id=2, utub_url_id=2),
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 403
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE

    with app.app_context():
        assert Utub_Urls.query.count() == initial_utub_urls_count


def test_delete_url_no_token_is_401(
    app: Flask,
    api_client: FlaskClient,
    add_one_url_to_each_utub_no_tags,
):
    """
    GIVEN no Authorization header
    WHEN DELETE /api/v1/utubs/1/urls/1
    THEN 401 JSON failure envelope
    """
    response = api_client.delete(_delete_url_url(app, utub_id=1, utub_url_id=1))

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.AUTHENTICATION_REQUIRED


def test_delete_url_nonexistent_utub_url_is_404(
    app: Flask,
    api_client: FlaskClient,
    add_one_url_to_each_utub_no_tags,
    make_bearer_headers: Callable[[str], dict[str, str]],
):
    """
    GIVEN user 1 is the creator of UTub 1; utub_url_id=9999 does not exist
    WHEN user 1 DELETEs /api/v1/utubs/1/urls/9999
    THEN 404 (no such URL in any UTub)
    """
    user_1_token = _token_for_user(app, user_id=1)

    response = api_client.delete(
        _delete_url_url(app, utub_id=1, utub_url_id=9999),
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 404
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
