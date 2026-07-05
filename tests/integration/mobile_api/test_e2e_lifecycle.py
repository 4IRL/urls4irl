"""
E2E lifecycle integration tests for the /api/v1 mobile bearer-token surface.

Covers a complete single-device session (login through logout) and the
refresh-token family reuse-detection + revocation semantics, including a
full chain-revocation attack scenario and a fresh-login recovery check.

Conventions:
  - Uses api_client (plain FlaskClient, no session/CSRF/AjaxFlaskLoginClient).
  - URLs built with url_for() inside test_request_context.
  - All JSON key constants imported from backend string modules.
  - pytestmark = pytest.mark.mobile_api
"""

from flask import Flask, url_for
from flask.testing import FlaskClient
import pytest

from backend.api_v1.constants import ApiAuthErrorCodes
from backend.models.api_refresh_tokens import ApiRefreshTokens
from backend.utils.all_routes import ROUTES
from backend.utils.strings.api_auth_strs import (
    API_AUTH,
    API_AUTH_FAILURE,
    API_AUTH_SUCCESS,
)
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.splash_form_strs import REGISTER_FORM
from backend.utils.strings.utub_strs import UTUB_SUCCESS
from tests.models_for_test import valid_url_strings, valid_user_1

pytestmark = pytest.mark.mobile_api

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_ACCESS_TOKEN_KEY = "accessToken"
_REFRESH_TOKEN_KEY = "refreshToken"

_UTUB_NAME_FIELD = "utubName"
_UTUB_DESC_FIELD = "utubDescription"
_TAG_STRING_FIELD = MODELS.TAG_STRING

_TEST_UTUB_NAME = "E2E Lifecycle UTub"
_TEST_UTUB_DESC = "Created during the full session lifecycle test"
_TEST_URL_STRING = valid_url_strings[0]  # "https://www.abc.com/"
_TEST_URL_TITLE = "E2E Lifecycle URL"
_TEST_TAG_STRING = "lifecycle-tag"
_UPDATED_UTUB_NAME = "E2E Lifecycle UTub — Renamed"

# Matches _TEST_URL_STRING ("https://www.abc.com/")
_SEARCH_QUERY = "abc"


# ---------------------------------------------------------------------------
# URL helpers — resolved inside test_request_context so url_for works
# ---------------------------------------------------------------------------


def _login_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.AUTH_LOGIN)


def _refresh_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.AUTH_REFRESH)


def _logout_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.AUTH_LOGOUT)


def _get_utubs_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.GET_UTUBS)


def _create_utub_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.CREATE_UTUB)


def _get_single_utub_url(app: Flask, utub_id: int) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.GET_SINGLE_UTUB, utub_id=utub_id)


def _create_url_url(app: Flask, utub_id: int) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.CREATE_URL, utub_id=utub_id)


def _create_utub_tag_url(app: Flask, utub_id: int) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.CREATE_UTUB_TAG, utub_id=utub_id)


def _create_url_tag_url(app: Flask, utub_id: int, utub_url_id: int) -> str:
    with app.test_request_context():
        return url_for(
            ROUTES.API_V1.CREATE_URL_TAG, utub_id=utub_id, utub_url_id=utub_url_id
        )


def _search_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.SEARCH)


def _update_utub_name_url(app: Flask, utub_id: int) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.UPDATE_UTUB_NAME, utub_id=utub_id)


def _bearer(token: str) -> dict[str, str]:
    return {API_AUTH.AUTHORIZATION_HEADER: f"{API_AUTH.BEARER_PREFIX}{token}"}


def _valid_login_body() -> dict[str, str]:
    return {
        MODELS.USERNAME: valid_user_1[REGISTER_FORM.USERNAME],
        "password": valid_user_1[REGISTER_FORM.PASSWORD],
    }


# ===========================================================================
# Full session lifecycle
# ===========================================================================


def test_full_mobile_session_lifecycle(
    app: Flask,
    api_client: FlaskClient,
    register_first_user,
):
    """
    GIVEN a registered, email-validated user
    WHEN a complete mobile session is executed:
         login → create UTub → create URL → add UTub tag → add URL tag →
         GET single UTub (assert URL + tags present) → GET search →
         refresh (get new token pair) → rename UTub with new token →
         logout with the new refresh token
    THEN each action succeeds (200); the old refresh token is revoked after
         logout so a subsequent /auth/refresh with it returns 401;
         and the still-unexpired access token continues to reach data routes
         after logout, because access tokens are stateless JWTs with no denylist.
    """
    with app.app_context():
        initial_refresh_token_count = ApiRefreshTokens.query.count()

    assert initial_refresh_token_count == 0

    # ---- Login ----
    login_response = api_client.post(_login_url(app), json=_valid_login_body())

    assert login_response.status_code == 200
    login_data = login_response.get_json()
    assert login_data[STD_JSON.STATUS] == STD_JSON.SUCCESS
    access_token: str = login_data[_ACCESS_TOKEN_KEY]
    refresh_token: str = login_data[_REFRESH_TOKEN_KEY]

    with app.app_context():
        assert ApiRefreshTokens.query.count() == initial_refresh_token_count + 1

    auth_headers = _bearer(access_token)

    # ---- Create UTub ----
    create_utub_response = api_client.post(
        _create_utub_url(app),
        json={_UTUB_NAME_FIELD: _TEST_UTUB_NAME, _UTUB_DESC_FIELD: _TEST_UTUB_DESC},
        headers=auth_headers,
    )

    assert create_utub_response.status_code == 200
    create_utub_data = create_utub_response.get_json()
    assert create_utub_data[STD_JSON.STATUS] == STD_JSON.SUCCESS
    utub_id: int = create_utub_data[UTUB_SUCCESS.UTUB_ID]

    # ---- Create URL in the UTub ----
    create_url_response = api_client.post(
        _create_url_url(app, utub_id=utub_id),
        json={
            MODELS.URL_STRING: _TEST_URL_STRING,
            MODELS.URL_TITLE: _TEST_URL_TITLE,
        },
        headers=auth_headers,
    )

    assert create_url_response.status_code == 200
    create_url_data = create_url_response.get_json()
    assert create_url_data[STD_JSON.STATUS] == STD_JSON.SUCCESS
    utub_url_id: int = create_url_data[MODELS.URL][MODELS.UTUB_URL_ID]

    # ---- Add a UTub-level tag ----
    add_utub_tag_response = api_client.post(
        _create_utub_tag_url(app, utub_id=utub_id),
        json={_TAG_STRING_FIELD: _TEST_TAG_STRING},
        headers=auth_headers,
    )

    assert add_utub_tag_response.status_code == 200
    assert add_utub_tag_response.get_json()[STD_JSON.STATUS] == STD_JSON.SUCCESS

    # ---- Add the same tag to the URL ----
    add_url_tag_response = api_client.post(
        _create_url_tag_url(app, utub_id=utub_id, utub_url_id=utub_url_id),
        json={_TAG_STRING_FIELD: _TEST_TAG_STRING},
        headers=auth_headers,
    )

    assert add_url_tag_response.status_code == 200
    assert add_url_tag_response.get_json()[STD_JSON.STATUS] == STD_JSON.SUCCESS

    # ---- GET single UTub — verify URL and tags are present ----
    get_utub_response = api_client.get(
        _get_single_utub_url(app, utub_id=utub_id),
        headers=auth_headers,
    )

    assert get_utub_response.status_code == 200
    get_utub_data = get_utub_response.get_json()
    assert get_utub_data[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert len(get_utub_data[MODELS.URLS]) == 1
    assert len(get_utub_data[MODELS.TAGS]) == 1

    # ---- Search — confirm the URL surfaces in results ----
    search_response = api_client.get(
        _search_url(app),
        query_string={"q": _SEARCH_QUERY},
        headers=auth_headers,
    )

    assert search_response.status_code == 200
    search_data = search_response.get_json()
    assert search_data[STD_JSON.STATUS] == STD_JSON.SUCCESS
    search_groups = search_data[MODELS.SEARCH_RESULTS]
    assert isinstance(search_groups, list)
    assert len(search_groups) >= 1

    # ---- Rotate the refresh token ----
    refresh_response = api_client.post(
        _refresh_url(app), json={_REFRESH_TOKEN_KEY: refresh_token}
    )

    assert refresh_response.status_code == 200
    refresh_data = refresh_response.get_json()
    assert refresh_data[STD_JSON.STATUS] == STD_JSON.SUCCESS
    new_access_token: str = refresh_data[_ACCESS_TOKEN_KEY]
    new_refresh_token: str = refresh_data[_REFRESH_TOKEN_KEY]
    assert new_refresh_token != refresh_token

    new_auth_headers = _bearer(new_access_token)

    # ---- Continue with the new access token ----
    patch_name_response = api_client.patch(
        _update_utub_name_url(app, utub_id=utub_id),
        json={_UTUB_NAME_FIELD: _UPDATED_UTUB_NAME},
        headers=new_auth_headers,
    )

    assert patch_name_response.status_code == 200
    assert patch_name_response.get_json()[STD_JSON.STATUS] == STD_JSON.SUCCESS

    # ---- Logout — revoke the new refresh-token family ----
    logout_response = api_client.post(
        _logout_url(app), json={_REFRESH_TOKEN_KEY: new_refresh_token}
    )

    assert logout_response.status_code == 200
    assert logout_response.get_json()[STD_JSON.MESSAGE] == API_AUTH_SUCCESS.LOGGED_OUT

    # ---- The revoked refresh token must no longer be usable ----
    post_logout_refresh_response = api_client.post(
        _refresh_url(app), json={_REFRESH_TOKEN_KEY: new_refresh_token}
    )

    assert post_logout_refresh_response.status_code == 401
    assert post_logout_refresh_response.get_json()[STD_JSON.MESSAGE] == (
        API_AUTH_FAILURE.INVALID_REFRESH_TOKEN
    )

    # ---- The still-unexpired access token continues to reach data routes ----
    # Access tokens are stateless JWTs; logout revokes the refresh family only.
    # There is no denylist, so the bearer token keeps working until its exp claim.
    post_logout_data_response = api_client.get(
        _get_utubs_url(app), headers=new_auth_headers
    )

    assert post_logout_data_response.status_code == 200
    assert post_logout_data_response.get_json()[STD_JSON.STATUS] == STD_JSON.SUCCESS


# ===========================================================================
# Reuse-detection revokes the entire rotation chain
# ===========================================================================


def test_replaying_pre_rotation_token_after_lifecycle_revokes_chain(
    app: Flask,
    api_client: FlaskClient,
    register_first_user,
):
    """
    GIVEN a registered, email-validated user who logs in and refreshes once
         (original token A → replacement token B)
    WHEN the spent token A is replayed
    THEN 401 with the REFRESH_TOKEN_REUSE_DETECTED message and error code is
         returned, token B is also revoked (the whole family is poisoned), and
         a subsequent fresh login still succeeds (user is not locked out).
    """
    # ---- Login to obtain the initial token pair ----
    login_response = api_client.post(_login_url(app), json=_valid_login_body())

    assert login_response.status_code == 200
    login_data = login_response.get_json()
    original_refresh_token: str = login_data[_REFRESH_TOKEN_KEY]

    # ---- Rotate once: original → replacement ----
    first_refresh_response = api_client.post(
        _refresh_url(app), json={_REFRESH_TOKEN_KEY: original_refresh_token}
    )

    assert first_refresh_response.status_code == 200
    replacement_token: str = first_refresh_response.get_json()[_REFRESH_TOKEN_KEY]
    assert replacement_token != original_refresh_token

    # ---- Replay the spent original token — reuse detected ----
    replay_response = api_client.post(
        _refresh_url(app), json={_REFRESH_TOKEN_KEY: original_refresh_token}
    )

    assert replay_response.status_code == 401
    replay_data = replay_response.get_json()
    assert replay_data[STD_JSON.MESSAGE] == (
        API_AUTH_FAILURE.REFRESH_TOKEN_REUSE_DETECTED
    )
    assert replay_data[STD_JSON.ERROR_CODE] == (
        ApiAuthErrorCodes.REFRESH_TOKEN_REUSE_DETECTED
    )

    # ---- The replacement token is also dead — family was revoked ----
    post_revocation_response = api_client.post(
        _refresh_url(app), json={_REFRESH_TOKEN_KEY: replacement_token}
    )

    assert post_revocation_response.status_code == 401
    assert post_revocation_response.get_json()[STD_JSON.ERROR_CODE] == (
        ApiAuthErrorCodes.INVALID_REFRESH_TOKEN
    )

    # ---- A fresh login still succeeds — user is not globally locked out ----
    fresh_login_response = api_client.post(_login_url(app), json=_valid_login_body())

    assert fresh_login_response.status_code == 200
    fresh_login_data = fresh_login_response.get_json()
    assert fresh_login_data[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert fresh_login_data[_ACCESS_TOKEN_KEY]
    assert fresh_login_data[_REFRESH_TOKEN_KEY]
