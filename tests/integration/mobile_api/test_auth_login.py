from flask import Flask, url_for
from flask.testing import FlaskClient
import pytest

from backend import db
from backend.api_v1.constants import ApiAuthErrorCodes
from backend.models.api_refresh_tokens import ApiRefreshTokens
from backend.models.users import Users
from backend.utils.all_routes import ROUTES
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.splash_form_strs import REGISTER_FORM
from backend.utils.strings.user_strs import USER_FAILURE
from tests.integration.mobile_api.conftest import (
    UNVALIDATED_PASSWORD,
    UNVALIDATED_USERNAME,
)
from tests.models_for_test import valid_user_1

pytestmark = pytest.mark.mobile_api

_ACCESS_TOKEN_KEY = "accessToken"
_REFRESH_TOKEN_KEY = "refreshToken"
_TOKEN_TYPE_KEY = "tokenType"
_EXPIRES_IN_KEY = "expiresIn"
_USER_KEY = "user"
_BEARER_TOKEN_TYPE = "Bearer"


def _login_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.AUTH_LOGIN)


def _me_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.GET_ME)


def _valid_login_body() -> dict[str, str]:
    return {
        MODELS.USERNAME: valid_user_1[REGISTER_FORM.USERNAME],
        "password": valid_user_1[REGISTER_FORM.PASSWORD],
    }


def test_login_issues_token_pair(
    app: Flask, api_client: FlaskClient, register_first_user, make_bearer_headers
):
    """
    GIVEN a registered, email-validated user
    WHEN POST /api/v1/auth/login is called with valid credentials and no
        cookie/CSRF/XHR machinery
    THEN a 200 token-pair response is returned, a refresh-token row is
        persisted, and the access token authenticates a data call
    """
    with app.app_context():
        assert ApiRefreshTokens.query.count() == 0

    response = api_client.post(_login_url(app), json=_valid_login_body())

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[_TOKEN_TYPE_KEY] == _BEARER_TOKEN_TYPE
    assert response_json[_EXPIRES_IN_KEY] > 0
    assert response_json[_USER_KEY][MODELS.ID] == 1
    assert response_json[_USER_KEY][MODELS.EMAIL_VALIDATED]

    with app.app_context():
        persisted_rows = ApiRefreshTokens.query.all()
        assert len(persisted_rows) == 1
        assert persisted_rows[0].token == response_json[_REFRESH_TOKEN_KEY]
        assert persisted_rows[0].user_id == 1

    me_response = api_client.get(
        _me_url(app), headers=make_bearer_headers(response_json[_ACCESS_TOKEN_KEY])
    )
    assert me_response.status_code == 200
    assert me_response.get_json()[MODELS.ID] == 1


def test_login_unknown_user_is_400_field_error(
    app: Flask, api_client: FlaskClient, register_first_user
):
    response = api_client.post(
        _login_url(app),
        json={MODELS.USERNAME: "notARealUser", "password": "whatever123"},
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == USER_FAILURE.UNABLE_TO_LOGIN
    assert response_json[STD_JSON.ERROR_CODE] == ApiAuthErrorCodes.INVALID_FORM_INPUT
    assert response_json[STD_JSON.ERRORS][MODELS.USERNAME] == [
        USER_FAILURE.USER_NOT_EXIST
    ]

    with app.app_context():
        assert ApiRefreshTokens.query.count() == 0


def test_login_wrong_password_is_400_field_error(
    app: Flask, api_client: FlaskClient, register_first_user
):
    response = api_client.post(
        _login_url(app),
        json={
            MODELS.USERNAME: valid_user_1[REGISTER_FORM.USERNAME],
            "password": "definitelyWrongPassword1",
        },
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.ERRORS]["password"] == [USER_FAILURE.INVALID_PASSWORD]

    with app.app_context():
        assert ApiRefreshTokens.query.count() == 0


def test_login_oauth_only_account_matches_wrong_password_response(
    app: Flask, api_client: FlaskClient
):
    """
    GIVEN an OAuth-only account (password is NULL)
    WHEN a password login is attempted against it
    THEN the response is byte-identical to the wrong-password branch so the
        account type cannot be fingerprinted
    """
    with app.app_context():
        oauth_only_user = Users(
            username="oauthOnlyUser", email="oauth_only@example.com"
        )
        oauth_only_user.email_validated = True
        db.session.add(oauth_only_user)
        db.session.commit()

    response = api_client.post(
        _login_url(app),
        json={MODELS.USERNAME: "oauthOnlyUser", "password": "somePassword123"},
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.ERRORS]["password"] == [USER_FAILURE.INVALID_PASSWORD]


def test_login_unvalidated_email_still_issues_tokens(
    app: Flask,
    api_client: FlaskClient,
    register_unvalidated_user_with_email_validation_row: int,
):
    """
    GIVEN a registered user whose email is NOT validated
    WHEN they log in via /api/v1 (unlike the web's 401)
    THEN a token pair IS issued (design-doc gating decision) with
        user.emailValidated false so the client shows its verify-email screen
    """
    response = api_client.post(
        _login_url(app),
        json={
            MODELS.USERNAME: UNVALIDATED_USERNAME,
            "password": UNVALIDATED_PASSWORD,
        },
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[_ACCESS_TOKEN_KEY]
    assert response_json[_REFRESH_TOKEN_KEY]
    assert not response_json[_USER_KEY][MODELS.EMAIL_VALIDATED]


def test_login_missing_body_is_400(
    app: Flask, api_client: FlaskClient, register_first_user
):
    response = api_client.post(_login_url(app))

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.ERROR_CODE] == ApiAuthErrorCodes.INVALID_FORM_INPUT
