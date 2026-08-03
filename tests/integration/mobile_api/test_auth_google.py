from flask import Flask, url_for
from flask.testing import FlaskClient
import pytest

from backend import db
from backend.api_v1.constants import ApiAuthErrorCodes
from backend.api_v1.services.google_tokens import GoogleIdTokenClaims
from backend.models.api_refresh_tokens import ApiRefreshTokens
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.utils.all_routes import ROUTES
from backend.utils.strings.api_auth_strs import API_AUTH_FAILURE
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.oauth_strs import (
    EMAIL_COLLISION_MESSAGE,
    UNVERIFIED_EMAIL_MESSAGE,
)

pytestmark = pytest.mark.mobile_api

_ID_TOKEN_KEY = "idToken"
_ACCESS_TOKEN_KEY = "accessToken"
_USER_KEY = "user"
_FAKE_ID_TOKEN = "fake-google-id-token"
_GOOGLE_SUBJECT = "google-subject-1234567890"
_GOOGLE_EMAIL = "google_mobile_user@example.com"
_GOOGLE_NAME = "Google Mobile User"

_VERIFY_FN_PATH = "backend.api_v1.services.auth.verify_google_id_token"


def _google_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.AUTH_GOOGLE)


def _verified_claims() -> GoogleIdTokenClaims:
    return GoogleIdTokenClaims(
        subject=_GOOGLE_SUBJECT,
        email=_GOOGLE_EMAIL,
        email_verified=True,
        name=_GOOGLE_NAME,
    )


def test_google_auth_creates_account_and_issues_tokens(
    app: Flask, api_client: FlaskClient, monkeypatch: pytest.MonkeyPatch
):
    """
    GIVEN a verifiable Google id_token for a brand-new user
    WHEN POST /api/v1/auth/google is called
    THEN an account + linked identity are created (email pre-validated) and
        a token pair is issued
    """
    monkeypatch.setattr(_VERIFY_FN_PATH, lambda *, id_token: _verified_claims())

    with app.app_context():
        assert Users.query.count() == 0
        assert ApiRefreshTokens.query.count() == 0

    response = api_client.post(_google_url(app), json={_ID_TOKEN_KEY: _FAKE_ID_TOKEN})

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[_ACCESS_TOKEN_KEY]
    assert response_json[_USER_KEY][MODELS.EMAIL] == _GOOGLE_EMAIL
    assert response_json[_USER_KEY][MODELS.EMAIL_VALIDATED]

    with app.app_context():
        created_user = Users.query.filter(Users.email == _GOOGLE_EMAIL).first()
        assert created_user is not None
        assert created_user.password is None
        assert created_user.email_validated
        linked_identity = UserOAuthIdentity.query.filter_by(
            provider_subject=_GOOGLE_SUBJECT
        ).first()
        assert linked_identity is not None
        assert linked_identity.user_id == created_user.id
        assert ApiRefreshTokens.query.count() == 1


def test_google_auth_existing_identity_reuses_account(
    app: Flask, api_client: FlaskClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(_VERIFY_FN_PATH, lambda *, id_token: _verified_claims())

    first_response = api_client.post(
        _google_url(app), json={_ID_TOKEN_KEY: _FAKE_ID_TOKEN}
    )
    assert first_response.status_code == 200

    second_response = api_client.post(
        _google_url(app), json={_ID_TOKEN_KEY: _FAKE_ID_TOKEN}
    )
    assert second_response.status_code == 200

    with app.app_context():
        assert Users.query.count() == 1
        assert UserOAuthIdentity.query.count() == 1
        # Two logins = two independent device families
        assert ApiRefreshTokens.query.count() == 2


def test_google_auth_unverifiable_token_is_401(
    app: Flask, api_client: FlaskClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(_VERIFY_FN_PATH, lambda *, id_token: None)

    response = api_client.post(_google_url(app), json={_ID_TOKEN_KEY: _FAKE_ID_TOKEN})

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.MESSAGE] == (
        API_AUTH_FAILURE.UNABLE_TO_VERIFY_GOOGLE_TOKEN
    )
    assert response_json[STD_JSON.ERROR_CODE] == ApiAuthErrorCodes.INVALID_GOOGLE_TOKEN

    with app.app_context():
        assert Users.query.count() == 0


def test_google_auth_unverified_email_is_403(
    app: Flask, api_client: FlaskClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        _VERIFY_FN_PATH,
        lambda *, id_token: GoogleIdTokenClaims(
            subject=_GOOGLE_SUBJECT,
            email=_GOOGLE_EMAIL,
            email_verified=False,
            name=_GOOGLE_NAME,
        ),
    )

    response = api_client.post(_google_url(app), json={_ID_TOKEN_KEY: _FAKE_ID_TOKEN})

    assert response.status_code == 403
    assert response.get_json()[STD_JSON.MESSAGE] == UNVERIFIED_EMAIL_MESSAGE

    with app.app_context():
        assert Users.query.count() == 0


def test_google_auth_email_collision_is_409(
    app: Flask, api_client: FlaskClient, monkeypatch: pytest.MonkeyPatch
):
    """
    GIVEN a local password account owning the Google token's email, with no
        linked Google identity
    WHEN the id_token exchange is attempted
    THEN 409 with the collision error code is returned and no identity is created
    """
    monkeypatch.setattr(_VERIFY_FN_PATH, lambda *, id_token: _verified_claims())

    with app.app_context():
        local_user = Users(
            username="localPasswordUser",
            email=_GOOGLE_EMAIL,
            plaintext_password="someLocalPassword1!",
        )
        local_user.email_validated = True
        db.session.add(local_user)
        db.session.commit()

    response = api_client.post(_google_url(app), json={_ID_TOKEN_KEY: _FAKE_ID_TOKEN})

    assert response.status_code == 409
    response_json = response.get_json()
    assert response_json[STD_JSON.MESSAGE] == EMAIL_COLLISION_MESSAGE
    assert response_json[STD_JSON.ERROR_CODE] == (
        ApiAuthErrorCodes.OAUTH_EMAIL_COLLISION
    )

    with app.app_context():
        assert UserOAuthIdentity.query.count() == 0


def test_google_auth_missing_body_is_400(app: Flask, api_client: FlaskClient):
    response = api_client.post(_google_url(app))

    assert response.status_code == 400
    assert response.get_json()[STD_JSON.ERROR_CODE] == (
        ApiAuthErrorCodes.INVALID_FORM_INPUT
    )
