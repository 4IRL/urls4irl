from flask import Flask, url_for
from flask.testing import FlaskClient
import pytest

from backend.api_v1.constants import ApiAuthErrorCodes
from backend.api_v1.services.tokens import issue_refresh_token
from backend.models.api_refresh_tokens import ApiRefreshTokens
from backend.models.users import Users
from backend.utils.all_routes import ROUTES
from backend.utils.strings.api_auth_strs import API_AUTH_FAILURE, API_AUTH_SUCCESS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON

pytestmark = pytest.mark.mobile_api

_REFRESH_TOKEN_KEY = "refreshToken"
_ACCESS_TOKEN_KEY = "accessToken"
_UNKNOWN_REFRESH_TOKEN = "never-issued-refresh-token"


def _refresh_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.AUTH_REFRESH)


def _logout_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.AUTH_LOGOUT)


def _logout_all_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.AUTH_LOGOUT_ALL)


def _me_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.GET_ME)


def test_refresh_rotates_token_pair(
    app: Flask,
    api_client: FlaskClient,
    refresh_token_first_user: str,
    make_bearer_headers,
):
    """
    GIVEN an active refresh token
    WHEN POST /api/v1/auth/refresh presents it
    THEN a new token pair is returned, the new access token authenticates,
        and the old refresh token is superseded
    """
    response = api_client.post(
        _refresh_url(app), json={_REFRESH_TOKEN_KEY: refresh_token_first_user}
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[_REFRESH_TOKEN_KEY] != refresh_token_first_user

    me_response = api_client.get(
        _me_url(app),
        headers=make_bearer_headers(response_json[_ACCESS_TOKEN_KEY]),
    )
    assert me_response.status_code == 200


def test_refresh_replay_revokes_family(
    app: Flask, api_client: FlaskClient, refresh_token_first_user: str
):
    """
    GIVEN a refresh token that was already rotated
    WHEN the spent token is replayed
    THEN 401 with the reuse-detection error code is returned and the
        replacement token is also revoked (whole family)
    """
    first_response = api_client.post(
        _refresh_url(app), json={_REFRESH_TOKEN_KEY: refresh_token_first_user}
    )
    assert first_response.status_code == 200
    replacement_token = first_response.get_json()[_REFRESH_TOKEN_KEY]

    replay_response = api_client.post(
        _refresh_url(app), json={_REFRESH_TOKEN_KEY: refresh_token_first_user}
    )

    assert replay_response.status_code == 401
    replay_json = replay_response.get_json()
    assert replay_json[STD_JSON.MESSAGE] == (
        API_AUTH_FAILURE.REFRESH_TOKEN_REUSE_DETECTED
    )
    assert replay_json[STD_JSON.ERROR_CODE] == (
        ApiAuthErrorCodes.REFRESH_TOKEN_REUSE_DETECTED
    )

    # The revoked replacement can no longer be used either
    post_revocation_response = api_client.post(
        _refresh_url(app), json={_REFRESH_TOKEN_KEY: replacement_token}
    )
    assert post_revocation_response.status_code == 401
    assert post_revocation_response.get_json()[STD_JSON.ERROR_CODE] == (
        ApiAuthErrorCodes.INVALID_REFRESH_TOKEN
    )


def test_refresh_unknown_token_is_401(
    app: Flask, api_client: FlaskClient, register_first_user
):
    response = api_client.post(
        _refresh_url(app), json={_REFRESH_TOKEN_KEY: _UNKNOWN_REFRESH_TOKEN}
    )

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.INVALID_REFRESH_TOKEN
    assert response_json[STD_JSON.ERROR_CODE] == (
        ApiAuthErrorCodes.INVALID_REFRESH_TOKEN
    )


def test_refresh_missing_body_is_400(app: Flask, api_client: FlaskClient):
    response = api_client.post(_refresh_url(app))

    assert response.status_code == 400
    assert response.get_json()[STD_JSON.ERROR_CODE] == (
        ApiAuthErrorCodes.INVALID_FORM_INPUT
    )


def test_logout_revokes_device_family(
    app: Flask, api_client: FlaskClient, refresh_token_first_user: str
):
    """
    GIVEN an active refresh token
    WHEN POST /api/v1/auth/logout presents it
    THEN 200 is returned and the token can no longer be refreshed
    """
    logout_response = api_client.post(
        _logout_url(app), json={_REFRESH_TOKEN_KEY: refresh_token_first_user}
    )

    assert logout_response.status_code == 200
    logout_json = logout_response.get_json()
    assert logout_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert logout_json[STD_JSON.MESSAGE] == API_AUTH_SUCCESS.LOGGED_OUT

    refresh_response = api_client.post(
        _refresh_url(app), json={_REFRESH_TOKEN_KEY: refresh_token_first_user}
    )
    assert refresh_response.status_code == 401


def test_logout_unknown_token_is_401(
    app: Flask, api_client: FlaskClient, register_first_user
):
    response = api_client.post(
        _logout_url(app), json={_REFRESH_TOKEN_KEY: _UNKNOWN_REFRESH_TOKEN}
    )

    assert response.status_code == 401
    assert response.get_json()[STD_JSON.ERROR_CODE] == (
        ApiAuthErrorCodes.INVALID_REFRESH_TOKEN
    )


def test_logout_all_revokes_every_device(
    app: Flask,
    api_client: FlaskClient,
    register_first_user,
    bearer_headers_first_user: dict[str, str],
):
    """
    GIVEN a user with two active device families
    WHEN POST /api/v1/auth/logout-all is called with a valid access token
    THEN every refresh token for the user is revoked
    """
    with app.app_context():
        assert ApiRefreshTokens.query.count() == 0
        first_user: Users = Users.query.get(1)
        first_device_token = issue_refresh_token(user=first_user)
        second_device_token = issue_refresh_token(user=first_user)

    response = api_client.post(_logout_all_url(app), headers=bearer_headers_first_user)

    assert response.status_code == 200
    assert response.get_json()[STD_JSON.MESSAGE] == (
        API_AUTH_SUCCESS.LOGGED_OUT_EVERYWHERE
    )

    with app.app_context():
        all_rows = ApiRefreshTokens.query.all()
        assert len(all_rows) == 2
        assert all(row.is_revoked() for row in all_rows)

    for revoked_token in (first_device_token, second_device_token):
        refresh_response = api_client.post(
            _refresh_url(app), json={_REFRESH_TOKEN_KEY: revoked_token}
        )
        assert refresh_response.status_code == 401


def test_logout_all_requires_bearer_auth(app: Flask, api_client: FlaskClient):
    response = api_client.post(_logout_all_url(app))

    assert response.status_code == 401
    assert response.get_json()[STD_JSON.MESSAGE] == (
        API_AUTH_FAILURE.AUTHENTICATION_REQUIRED
    )
