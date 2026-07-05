"""
Integration tests for the bearer-token URL-tag endpoints:
  POST   /api/v1/utubs/<utub_id>/urls/<utub_url_id>/tags
  POST   /api/v1/utubs/<utub_id>/urls/<utub_url_id>/tags/batch
  DELETE /api/v1/utubs/<utub_id>/urls/<utub_url_id>/tags/<utub_tag_id>

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
_TAG_STRINGS_FIELD = "tagStrings"  # AddTagsRequest body key
_NEW_TAG_STRING = "MobileTestTag"
_BATCH_TAG_ALPHA = "batchmobilealpha"
_BATCH_TAG_BETA = "batchmobilebeta"


# ---------------------------------------------------------------------------
# URL helpers — resolved inside test_request_context so url_for works
# ---------------------------------------------------------------------------


def _create_url_tag_url(app: Flask, utub_id: int, utub_url_id: int) -> str:
    with app.test_request_context():
        return url_for(
            ROUTES.API_V1.CREATE_URL_TAG,
            utub_id=utub_id,
            utub_url_id=utub_url_id,
        )


def _batch_create_url_tags_url(app: Flask, utub_id: int, utub_url_id: int) -> str:
    with app.test_request_context():
        return url_for(
            ROUTES.API_V1.CREATE_URL_TAGS_BATCH,
            utub_id=utub_id,
            utub_url_id=utub_url_id,
        )


def _delete_url_tag_url(
    app: Flask, utub_id: int, utub_url_id: int, utub_tag_id: int
) -> str:
    with app.test_request_context():
        return url_for(
            ROUTES.API_V1.DELETE_URL_TAG,
            utub_id=utub_id,
            utub_url_id=utub_url_id,
            utub_tag_id=utub_tag_id,
        )


def _bearer(token: str) -> dict[str, str]:
    return {API_AUTH.AUTHORIZATION_HEADER: f"{API_AUTH.BEARER_PREFIX}{token}"}


def _token_for_user(app: Flask, user_id: int) -> str:
    with app.app_context():
        user: Users = Users.query.get(user_id)
        return create_access_token(user=user)


# ===========================================================================
# POST /api/v1/utubs/<utub_id>/urls/<utub_url_id>/tags — add single tag
# ===========================================================================


def test_add_url_tag_happy_path(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    add_one_url_to_each_utub_no_tags,
):
    """
    GIVEN a validated member of UTub 1 with URL utub_url_id=1 and no tags
    WHEN POST /api/v1/utubs/1/urls/1/tags with a fresh tagString
    THEN 200 with utubTag, utubUrlTagIDs, tagCountsInUtub; one Utub_Url_Tags row created
    """
    utub_id = 1
    utub_url_id = 1
    user_1_token = _token_for_user(app, user_id=1)

    with app.app_context():
        initial_url_tag_count = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == utub_url_id,
        ).count()

    assert initial_url_tag_count == 0

    response = api_client.post(
        _create_url_tag_url(app, utub_id=utub_id, utub_url_id=utub_url_id),
        json={_TAG_STRING_FIELD: _NEW_TAG_STRING},
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_ADDED_TO_URL
    assert TAGS_SUCCESS.UTUB_TAG in response_json
    assert response_json[TAGS_SUCCESS.UTUB_TAG][MODELS.TAG_STRING] == _NEW_TAG_STRING
    new_utub_tag_id = response_json[TAGS_SUCCESS.UTUB_TAG][MODELS.UTUB_TAG_ID]
    assert new_utub_tag_id in response_json[TAGS_SUCCESS.UTUB_URL_TAG_IDS]

    with app.app_context():
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id,
                Utub_Url_Tags.utub_url_id == utub_url_id,
            ).count()
            == initial_url_tag_count + 1
        )
        assert (
            Utub_Tags.query.filter(
                Utub_Tags.utub_id == utub_id,
                Utub_Tags.tag_string == _NEW_TAG_STRING,
            ).count()
            == 1
        )


def test_add_url_tag_no_token_is_401(
    app: Flask,
    api_client: FlaskClient,
):
    """
    GIVEN no Authorization header
    WHEN POST /api/v1/utubs/1/urls/1/tags
    THEN 401 with AUTHENTICATION_REQUIRED
    """
    response = api_client.post(
        _create_url_tag_url(app, utub_id=1, utub_url_id=1),
        json={_TAG_STRING_FIELD: _NEW_TAG_STRING},
    )

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.AUTHENTICATION_REQUIRED


def test_add_url_tag_unvalidated_email_is_403(
    app: Flask,
    api_client: FlaskClient,
    access_token_unvalidated_user: str,
):
    """
    GIVEN a bearer token for a user whose email is NOT validated
    WHEN POST /api/v1/utubs/1/urls/1/tags
    THEN 403 with EMAIL_VALIDATION_REQUIRED
    """
    response = api_client.post(
        _create_url_tag_url(app, utub_id=1, utub_url_id=1),
        json={_TAG_STRING_FIELD: _NEW_TAG_STRING},
        headers=_bearer(access_token_unvalidated_user),
    )

    assert response.status_code == 403
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.EMAIL_VALIDATION_REQUIRED


def test_add_url_tag_non_member_is_404(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    add_one_url_to_each_utub_no_tags,
):
    """
    GIVEN user 1 who is NOT a member of UTub 2 (owned by user 2)
    WHEN user 1 POSTs to /api/v1/utubs/2/urls/2/tags
    THEN 404
    """
    user_1_token = _token_for_user(app, user_id=1)

    response = api_client.post(
        _create_url_tag_url(app, utub_id=2, utub_url_id=2),
        json={_TAG_STRING_FIELD: _NEW_TAG_STRING},
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 404
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_add_url_tag_missing_body_is_400(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    add_one_url_to_each_utub_no_tags,
):
    """
    GIVEN a validated member of UTub 1
    WHEN POST /api/v1/utubs/1/urls/1/tags with no JSON body
    THEN 400 (schema validation failure)
    """
    user_1_token = _token_for_user(app, user_id=1)

    response = api_client.post(
        _create_url_tag_url(app, utub_id=1, utub_url_id=1),
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_add_url_tag_duplicate_is_400(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    add_two_users_and_all_urls_to_each_utub_with_one_tag,
):
    """
    GIVEN UTub 1 where utub_url_id=1 already has tag 'Exciting!' applied
    WHEN user 1 POSTs the same tagString again
    THEN 400 with TAG_ALREADY_ON_URL message
    """
    utub_id = 1
    utub_url_id = 1
    duplicate_tag_string = all_tag_strings[0]  # "Exciting!" — already on utub_url_id=1
    user_1_token = _token_for_user(app, user_id=1)

    response = api_client.post(
        _create_url_tag_url(app, utub_id=utub_id, utub_url_id=utub_url_id),
        json={_TAG_STRING_FIELD: duplicate_tag_string},
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == TAGS_FAILURE.TAG_ALREADY_ON_URL


# ===========================================================================
# POST /api/v1/utubs/<utub_id>/urls/<utub_url_id>/tags/batch — batch add
# ===========================================================================


def test_batch_add_url_tags_happy_path(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    add_one_url_to_each_utub_no_tags,
):
    """
    GIVEN a validated member of UTub 1 with URL utub_url_id=1 and no tags
    WHEN POST /api/v1/utubs/1/urls/1/tags/batch with two fresh tagStrings
    THEN 200 with appliedTags list length 2; two new Utub_Url_Tags rows created
    """
    utub_id = 1
    utub_url_id = 1
    user_1_token = _token_for_user(app, user_id=1)

    with app.app_context():
        initial_assoc_count = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == utub_url_id,
        ).count()
        initial_vocab_count = Utub_Tags.query.count()

    assert initial_assoc_count == 0

    response = api_client.post(
        _batch_create_url_tags_url(app, utub_id=utub_id, utub_url_id=utub_url_id),
        json={_TAG_STRINGS_FIELD: [_BATCH_TAG_ALPHA, _BATCH_TAG_BETA]},
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAGS_ADDED_TO_URL
    assert len(response_json[MODELS.APPLIED_TAGS]) == 2
    assert len(response_json[MODELS.URL_TAG_IDS]) == 2

    with app.app_context():
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id,
                Utub_Url_Tags.utub_url_id == utub_url_id,
            ).count()
            == initial_assoc_count + 2
        )
        assert Utub_Tags.query.count() == initial_vocab_count + 2


def test_batch_add_url_tags_empty_body_is_400(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    add_one_url_to_each_utub_no_tags,
):
    """
    GIVEN a validated member of UTub 1
    WHEN POST /api/v1/utubs/1/urls/1/tags/batch with no body
    THEN 400 (schema validation failure)
    """
    user_1_token = _token_for_user(app, user_id=1)

    response = api_client.post(
        _batch_create_url_tags_url(app, utub_id=1, utub_url_id=1),
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_batch_add_url_tags_no_token_is_401(
    app: Flask,
    api_client: FlaskClient,
):
    """
    GIVEN no Authorization header
    WHEN POST /api/v1/utubs/1/urls/1/tags/batch
    THEN 401
    """
    response = api_client.post(
        _batch_create_url_tags_url(app, utub_id=1, utub_url_id=1),
        json={_TAG_STRINGS_FIELD: [_BATCH_TAG_ALPHA]},
    )

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


# ===========================================================================
# DELETE /api/v1/utubs/<utub_id>/urls/<utub_url_id>/tags/<utub_tag_id>
# ===========================================================================


def test_delete_url_tag_happy_path(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    add_two_users_and_all_urls_to_each_utub_with_one_tag,
):
    """
    GIVEN UTub 1 where utub_url_id=1 has tag_id=1 ('Exciting!') applied
    WHEN user 1 DELETEs tag 1 from URL 1 in UTub 1
    THEN 200 with utubTag, utubUrlTagIDs; the Utub_Url_Tags row is removed;
         the Utub_Tags vocabulary row still exists
    """
    utub_id = 1
    utub_url_id = 1
    utub_tag_id = 1
    user_1_token = _token_for_user(app, user_id=1)

    with app.app_context():
        initial_assoc_exists = (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id,
                Utub_Url_Tags.utub_url_id == utub_url_id,
                Utub_Url_Tags.utub_tag_id == utub_tag_id,
            ).count()
            == 1
        )
        initial_total_url_tag_count = Utub_Url_Tags.query.count()

    assert initial_assoc_exists

    response = api_client.delete(
        _delete_url_tag_url(
            app,
            utub_id=utub_id,
            utub_url_id=utub_url_id,
            utub_tag_id=utub_tag_id,
        ),
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_REMOVED_FROM_URL
    assert TAGS_SUCCESS.UTUB_TAG in response_json
    assert response_json[TAGS_SUCCESS.UTUB_TAG][MODELS.TAG_STRING] == all_tag_strings[0]

    with app.app_context():
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id,
                Utub_Url_Tags.utub_url_id == utub_url_id,
                Utub_Url_Tags.utub_tag_id == utub_tag_id,
            ).count()
            == 0
        )
        assert Utub_Url_Tags.query.count() == initial_total_url_tag_count - 1
        assert Utub_Tags.query.get(utub_tag_id) is not None


def test_delete_url_tag_not_on_url_is_404(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    add_one_url_to_each_utub_no_tags,
    add_tags_to_utubs,
):
    """
    GIVEN UTub 1 where tag_id=1 exists in the UTub vocabulary but is NOT applied to any URL
    WHEN user 1 DELETEs tag 1 from URL 1 in UTub 1
    THEN 404 (Utub_Url_Tags association not found)
    """
    utub_id = 1
    utub_url_id = 1
    utub_tag_id = 1
    user_1_token = _token_for_user(app, user_id=1)

    with app.app_context():
        tag_in_utub_vocab = Utub_Tags.query.get(utub_tag_id)
        tag_on_url_count = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == utub_url_id,
            Utub_Url_Tags.utub_tag_id == utub_tag_id,
        ).count()

    assert tag_in_utub_vocab is not None
    assert tag_on_url_count == 0

    response = api_client.delete(
        _delete_url_tag_url(
            app,
            utub_id=utub_id,
            utub_url_id=utub_url_id,
            utub_tag_id=utub_tag_id,
        ),
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 404
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_delete_url_tag_no_token_is_401(
    app: Flask,
    api_client: FlaskClient,
):
    """
    GIVEN no Authorization header
    WHEN DELETE /api/v1/utubs/1/urls/1/tags/1
    THEN 401
    """
    response = api_client.delete(
        _delete_url_tag_url(app, utub_id=1, utub_url_id=1, utub_tag_id=1),
    )

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
