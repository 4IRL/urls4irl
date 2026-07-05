"""
Integration tests for the bearer-token search endpoint:
  GET /api/v1/search?q=...&fields=...

Conventions:
  - Uses api_client (plain FlaskClient, no session/CSRF/AjaxFlaskLoginClient).
  - URL built with url_for() inside app.test_request_context().
  - All JSON key constants imported from backend string modules.
  - pytestmark = pytest.mark.mobile_api
"""

from flask import Flask, url_for
from flask.testing import FlaskClient
import pytest

from backend.api_v1.services.tokens import create_access_token
from backend.models.users import Users
from backend.search.constants import SearchErrorCodes, SearchFailureMessages
from backend.utils.all_routes import ROUTES
from backend.utils.strings.api_auth_strs import API_AUTH, API_AUTH_FAILURE
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.utub_strs import UTUB_ID, UTUB_NAME

pytestmark = pytest.mark.mobile_api

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_HTTPS_QUERY = "https"  # matches all seeded URL strings and titles
_NO_MATCH_QUERY = "zzzznomatchquery"  # matches nothing in any seeded fixture


# ---------------------------------------------------------------------------
# URL helpers — resolved inside test_request_context so url_for works
# ---------------------------------------------------------------------------


def _search_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.SEARCH)


def _bearer(token: str) -> dict[str, str]:
    return {API_AUTH.AUTHORIZATION_HEADER: f"{API_AUTH.BEARER_PREFIX}{token}"}


def _token_for_user(app: Flask, user_id: int) -> str:
    with app.app_context():
        user: Users = Users.query.get(user_id)
        return create_access_token(user=user)


# ===========================================================================
# GET /api/v1/search — search across UTubs
# ===========================================================================


def test_search_happy_path(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    add_all_urls_and_users_to_each_utub_with_all_tags,
):
    """
    GIVEN user 1 is a member of all three UTubs, each containing URLs whose
         titles and URL strings contain 'https'
    WHEN GET /api/v1/search?q=https
    THEN 200 with status=success, results list is non-empty, each group has
         utubID, utubName, and urls; each URL hit has utubUrlID, urlString,
         urlTitle, urlTags, matchedFields
    """
    user_1_token = _token_for_user(app, user_id=1)

    response = api_client.get(
        _search_url(app),
        query_string={"q": _HTTPS_QUERY},
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS

    groups = response_json[MODELS.SEARCH_RESULTS]
    assert isinstance(groups, list)
    assert len(groups) > 0

    for group in groups:
        assert UTUB_ID in group
        assert UTUB_NAME in group
        assert isinstance(group[MODELS.URLS], list)
        for url_hit in group[MODELS.URLS]:
            assert MODELS.UTUB_URL_ID in url_hit
            assert MODELS.URL_STRING in url_hit
            assert MODELS.URL_TITLE in url_hit
            assert MODELS.URL_TAGS in url_hit
            assert MODELS.MATCHED_FIELDS in url_hit


def test_search_no_match_returns_empty_list(
    app: Flask,
    api_client: FlaskClient,
    make_bearer_headers,
    add_all_urls_and_users_to_each_utub_with_all_tags,
):
    """
    GIVEN user 1 with seeded UTubs and URLs
    WHEN GET /api/v1/search?q=<term that matches nothing>
    THEN 200 with status=success and an empty results list
    """
    user_1_token = _token_for_user(app, user_id=1)

    response = api_client.get(
        _search_url(app),
        query_string={"q": _NO_MATCH_QUERY},
        headers=make_bearer_headers(user_1_token),
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[MODELS.SEARCH_RESULTS] == []


def test_search_missing_q_is_400(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
    register_first_user,
):
    """
    GIVEN a validated user with a bearer token
    WHEN GET /api/v1/search with no q parameter
    THEN 400 with INVALID_QUERY message and INVALID_QUERY_PARAM error code
    """
    response = api_client.get(
        _search_url(app),
        headers=bearer_headers_first_user,
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == SearchFailureMessages.INVALID_QUERY
    assert response_json[STD_JSON.ERROR_CODE] == SearchErrorCodes.INVALID_QUERY_PARAM


def test_search_blank_q_is_400(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
    register_first_user,
):
    """
    GIVEN a validated user with a bearer token
    WHEN GET /api/v1/search?q=%20%20 (whitespace-only q, strips to empty)
    THEN 400 with INVALID_QUERY message (fails min_length after strip)
    """
    response = api_client.get(
        _search_url(app),
        query_string={"q": "   "},
        headers=bearer_headers_first_user,
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == SearchFailureMessages.INVALID_QUERY
    assert response_json[STD_JSON.ERROR_CODE] == SearchErrorCodes.INVALID_QUERY_PARAM


def test_search_no_token_is_401(
    app: Flask,
    api_client: FlaskClient,
):
    """
    GIVEN no Authorization header
    WHEN GET /api/v1/search?q=anything
    THEN 401 with AUTHENTICATION_REQUIRED
    """
    response = api_client.get(
        _search_url(app),
        query_string={"q": _HTTPS_QUERY},
    )

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.AUTHENTICATION_REQUIRED


def test_search_unvalidated_email_is_403(
    app: Flask,
    api_client: FlaskClient,
    access_token_unvalidated_user: str,
):
    """
    GIVEN a bearer token for a user whose email is NOT validated
    WHEN GET /api/v1/search?q=anything
    THEN 403 with EMAIL_VALIDATION_REQUIRED
    """
    response = api_client.get(
        _search_url(app),
        query_string={"q": _HTTPS_QUERY},
        headers=_bearer(access_token_unvalidated_user),
    )

    assert response.status_code == 403
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.EMAIL_VALIDATION_REQUIRED
