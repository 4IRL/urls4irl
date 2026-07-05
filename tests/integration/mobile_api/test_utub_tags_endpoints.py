"""
Integration tests for the bearer-token UTub-tag endpoints:
  POST   /api/v1/utubs/<utub_id>/tags
  DELETE /api/v1/utubs/<utub_id>/tags/<utub_tag_id>

Conventions:
  - Uses api_client (plain FlaskClient, no session/CSRF/AjaxFlaskLoginClient).
  - URLs built with url_for() inside app.test_request_context().
  - All JSON key constants imported from backend string modules.
  - pytestmark = pytest.mark.mobile_api
"""

from flask import Flask, url_for
from flask.testing import FlaskClient
import pytest

from backend.api_v1.services.tokens import create_access_token
from backend.models.users import Users
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.utils.all_routes import ROUTES
from backend.utils.strings.api_auth_strs import API_AUTH, API_AUTH_FAILURE
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.tag_strs import TAGS_FAILURE, TAGS_SUCCESS
from tests.models_for_test import all_tag_strings

pytestmark = pytest.mark.mobile_api

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_TAG_STRING_FIELD = MODELS.TAG_STRING  # "tagString" — AddTagRequest body key
_NEW_UTUB_TAG_STRING = "BrandNewUTubTag"


# ---------------------------------------------------------------------------
# URL helpers — resolved inside test_request_context so url_for works
# ---------------------------------------------------------------------------


def _create_utub_tag_url(app: Flask, utub_id: int) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.CREATE_UTUB_TAG, utub_id=utub_id)


def _delete_utub_tag_url(app: Flask, utub_id: int, utub_tag_id: int) -> str:
    with app.test_request_context():
        return url_for(
            ROUTES.API_V1.DELETE_UTUB_TAG,
            utub_id=utub_id,
            utub_tag_id=utub_tag_id,
        )


def _bearer(token: str) -> dict[str, str]:
    return {API_AUTH.AUTHORIZATION_HEADER: f"{API_AUTH.BEARER_PREFIX}{token}"}


def _token_for_user(app: Flask, user_id: int) -> str:
    with app.app_context():
        user: Users = Users.query.get(user_id)
        return create_access_token(user=user)


# ===========================================================================
# POST /api/v1/utubs/<utub_id>/tags — create UTub tag
# ===========================================================================


def test_create_utub_tag_happy_path(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    every_user_makes_a_unique_utub,
):
    """
    GIVEN user 1 is a member (creator) of UTub 1, which has no tags
    WHEN POST /api/v1/utubs/1/tags with a fresh tagString
    THEN 200 with utubTag (utubTagID, tagString) and tagCountsInUtub == 0;
         one new Utub_Tags row created in UTub 1
    """
    utub_id = 1
    user_1_token = _token_for_user(app, user_id=1)

    with app.app_context():
        initial_utub_tag_count = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_id
        ).count()

    assert initial_utub_tag_count == 0

    response = api_client.post(
        _create_utub_tag_url(app, utub_id=utub_id),
        json={_TAG_STRING_FIELD: _NEW_UTUB_TAG_STRING},
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_ADDED_TO_UTUB
    assert TAGS_SUCCESS.UTUB_TAG in response_json
    assert (
        response_json[TAGS_SUCCESS.UTUB_TAG][MODELS.TAG_STRING] == _NEW_UTUB_TAG_STRING
    )
    assert response_json[TAGS_SUCCESS.TAG_COUNTS_MODIFIED] == 0

    new_utub_tag_id = response_json[TAGS_SUCCESS.UTUB_TAG][MODELS.UTUB_TAG_ID]

    with app.app_context():
        assert (
            Utub_Tags.query.filter(
                Utub_Tags.utub_id == utub_id,
                Utub_Tags.tag_string == _NEW_UTUB_TAG_STRING,
            ).count()
            == 1
        )
        assert Utub_Tags.query.get(new_utub_tag_id) is not None


def test_create_utub_tag_no_token_is_401(
    app: Flask,
    api_client: FlaskClient,
):
    """
    GIVEN no Authorization header
    WHEN POST /api/v1/utubs/1/tags
    THEN 401 with AUTHENTICATION_REQUIRED
    """
    response = api_client.post(
        _create_utub_tag_url(app, utub_id=1),
        json={_TAG_STRING_FIELD: _NEW_UTUB_TAG_STRING},
    )

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.AUTHENTICATION_REQUIRED


def test_create_utub_tag_unvalidated_email_is_403(
    app: Flask,
    api_client: FlaskClient,
    access_token_unvalidated_user: str,
):
    """
    GIVEN a bearer token for a user whose email is NOT validated
    WHEN POST /api/v1/utubs/1/tags
    THEN 403 with EMAIL_VALIDATION_REQUIRED
    """
    response = api_client.post(
        _create_utub_tag_url(app, utub_id=1),
        json={_TAG_STRING_FIELD: _NEW_UTUB_TAG_STRING},
        headers=_bearer(access_token_unvalidated_user),
    )

    assert response.status_code == 403
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.EMAIL_VALIDATION_REQUIRED


def test_create_utub_tag_non_member_is_404(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    every_user_makes_a_unique_utub,
):
    """
    GIVEN user 1 who is NOT a member of UTub 2 (owned by user 2)
    WHEN user 1 POSTs to /api/v1/utubs/2/tags
    THEN 404
    """
    user_1_token = _token_for_user(app, user_id=1)

    response = api_client.post(
        _create_utub_tag_url(app, utub_id=2),
        json={_TAG_STRING_FIELD: _NEW_UTUB_TAG_STRING},
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 404
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_create_utub_tag_missing_body_is_400(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    every_user_makes_a_unique_utub,
):
    """
    GIVEN a validated member of UTub 1
    WHEN POST /api/v1/utubs/1/tags with no JSON body
    THEN 400 (schema validation failure)
    """
    user_1_token = _token_for_user(app, user_id=1)

    response = api_client.post(
        _create_utub_tag_url(app, utub_id=1),
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_create_utub_tag_duplicate_is_400(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    add_tags_to_utubs,
):
    """
    GIVEN UTub 1 already has 'Exciting!' in its tag vocabulary (tag_id=1)
    WHEN user 1 POSTs the same tagString to UTub 1
    THEN 400 with TAG_ALREADY_IN_UTUB message
    """
    utub_id = 1
    duplicate_tag_string = all_tag_strings[0]  # "Exciting!" — already in UTub 1
    user_1_token = _token_for_user(app, user_id=1)

    with app.app_context():
        existing_tag_count = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_id,
            Utub_Tags.tag_string == duplicate_tag_string,
        ).count()

    assert existing_tag_count == 1

    response = api_client.post(
        _create_utub_tag_url(app, utub_id=utub_id),
        json={_TAG_STRING_FIELD: duplicate_tag_string},
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == TAGS_FAILURE.TAG_ALREADY_IN_UTUB


# ===========================================================================
# DELETE /api/v1/utubs/<utub_id>/tags/<utub_tag_id> — delete UTub tag
# ===========================================================================


def test_delete_utub_tag_happy_path(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    add_two_users_and_all_urls_to_each_utub_with_one_tag,
):
    """
    GIVEN UTub 1 with tag_id=1 ('Exciting!') applied to two URLs
         (utub_url_id=1 and utub_url_id=4)
    WHEN user 1 DELETEs tag 1 from UTub 1
    THEN 200 with utubTag, utubUrlIDs (affected URL IDs);
         Utub_Tags row for tag_id=1 removed;
         all Utub_Url_Tags rows for that tag in UTub 1 removed
    """
    utub_id = 1
    utub_tag_id = 1
    user_1_token = _token_for_user(app, user_id=1)

    with app.app_context():
        utub_tag_before: Utub_Tags = Utub_Tags.query.get(utub_tag_id)
        tag_string_before = utub_tag_before.tag_string
        url_tag_rows_before = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_tag_id == utub_tag_id,
        ).count()

    assert utub_tag_before is not None
    assert url_tag_rows_before > 0

    response = api_client.delete(
        _delete_utub_tag_url(app, utub_id=utub_id, utub_tag_id=utub_tag_id),
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_REMOVED_FROM_UTUB
    assert TAGS_SUCCESS.UTUB_TAG in response_json
    assert response_json[TAGS_SUCCESS.UTUB_TAG][MODELS.TAG_STRING] == tag_string_before
    assert response_json[TAGS_SUCCESS.UTUB_TAG][MODELS.UTUB_TAG_ID] == utub_tag_id
    assert isinstance(response_json[TAGS_SUCCESS.UTUB_URL_IDS], list)
    assert len(response_json[TAGS_SUCCESS.UTUB_URL_IDS]) == url_tag_rows_before

    with app.app_context():
        assert Utub_Tags.query.get(utub_tag_id) is None
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id,
                Utub_Url_Tags.utub_tag_id == utub_tag_id,
            ).count()
            == 0
        )


def test_delete_utub_tag_nonexistent_is_404(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    every_user_makes_a_unique_utub,
):
    """
    GIVEN UTub 1 which has no tags
    WHEN user 1 DELETEs a tag_id that does not exist in UTub 1
    THEN 404
    """
    utub_id = 1
    nonexistent_utub_tag_id = 9999
    user_1_token = _token_for_user(app, user_id=1)

    with app.app_context():
        assert Utub_Tags.query.get(nonexistent_utub_tag_id) is None

    response = api_client.delete(
        _delete_utub_tag_url(app, utub_id=utub_id, utub_tag_id=nonexistent_utub_tag_id),
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 404
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_delete_utub_tag_no_token_is_401(
    app: Flask,
    api_client: FlaskClient,
):
    """
    GIVEN no Authorization header
    WHEN DELETE /api/v1/utubs/1/tags/1
    THEN 401
    """
    response = api_client.delete(
        _delete_utub_tag_url(app, utub_id=1, utub_tag_id=1),
    )

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
