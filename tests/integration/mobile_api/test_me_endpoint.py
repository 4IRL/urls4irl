from flask import Flask, url_for
from flask.testing import FlaskClient
import pytest

from backend import db
from backend.api_v1.services.tokens import create_access_token
from backend.models.users import Users
from backend.utils.all_routes import ROUTES
from backend.utils.strings.api_auth_strs import API_AUTH, API_AUTH_FAILURE
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.splash_form_strs import REGISTER_FORM
from tests.models_for_test import valid_user_1

pytestmark = pytest.mark.mobile_api

_UNVALIDATED_USERNAME = "unvalidated_mobile_user"
_UNVALIDATED_EMAIL = "unvalidated_mobile_user@example.com"


def _me_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.GET_ME)


def _register_unvalidated_user_token(app: Flask) -> str:
    with app.app_context():
        unvalidated_user = Users(
            username=_UNVALIDATED_USERNAME,
            email=_UNVALIDATED_EMAIL,
            plaintext_password="somePassword123!",
        )
        unvalidated_user.email_validated = False
        db.session.add(unvalidated_user)
        db.session.commit()
        return create_access_token(user=unvalidated_user)


def test_get_me_with_valid_bearer_token(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
):
    """
    GIVEN a registered, email-validated user holding a valid access token
    WHEN GET /api/v1/me is called with only an Authorization: Bearer header
        (no session cookie, no CSRF token, no X-Requested-With)
    THEN the user's profile is returned in the Success envelope
    """
    response = api_client.get(_me_url(app), headers=bearer_headers_first_user)

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[MODELS.ID] == 1
    assert response_json[MODELS.USERNAME] == valid_user_1[REGISTER_FORM.USERNAME]
    assert response_json[MODELS.EMAIL] == valid_user_1[REGISTER_FORM.EMAIL].lower()
    assert response_json[MODELS.EMAIL_VALIDATED]


def test_get_me_without_token_is_json_401(app: Flask, api_client: FlaskClient):
    """
    GIVEN no Authorization header at all
    WHEN GET /api/v1/me is called
    THEN a 401 JSON ErrorResponse envelope is returned — never a 302 redirect
    """
    response = api_client.get(_me_url(app))

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == API_AUTH_FAILURE.AUTHENTICATION_REQUIRED


def test_get_me_with_invalid_token_is_json_401(app: Flask, api_client: FlaskClient):
    response = api_client.get(
        _me_url(app),
        headers={API_AUTH.AUTHORIZATION_HEADER: f"{API_AUTH.BEARER_PREFIX}invalid"},
    )

    assert response.status_code == 401
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_get_me_reachable_by_unvalidated_email_user(
    app: Flask, api_client: FlaskClient, make_bearer_headers
):
    """
    GIVEN an authenticated user whose email is NOT validated
    WHEN GET /api/v1/me is called
    THEN the profile is returned (design doc: unvalidated accounts can
        authenticate) with emailValidated false so the client can render its
        verify-email screen
    """
    unvalidated_token = _register_unvalidated_user_token(app)

    response = api_client.get(
        _me_url(app), headers=make_bearer_headers(unvalidated_token)
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert not response_json[MODELS.EMAIL_VALIDATED]
    assert response_json[MODELS.USERNAME] == _UNVALIDATED_USERNAME
