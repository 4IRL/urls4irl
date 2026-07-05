from flask import Flask, url_for
from flask.testing import FlaskClient
import pytest

from backend import db
from backend.models.email_validations import Email_Validations
from backend.splash.constants import EmailValidationErrorCodes
from backend.utils.all_routes import ROUTES
from backend.utils.constants import EMAIL_CONSTANTS
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.api_auth_strs import API_AUTH_FAILURE
from backend.utils.strings.email_validation_strs import EMAILS, EMAILS_FAILURE
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON

pytestmark = pytest.mark.mobile_api


def _resend_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.AUTH_RESEND_VALIDATION)


def test_resend_validation_sends_email(
    app: Flask,
    api_client: FlaskClient,
    access_token_unvalidated_user: str,
    make_bearer_headers,
):
    """
    GIVEN an authenticated but unvalidated-email bearer user with a pending
        Email_Validations row
    WHEN POST /api/v1/auth/resend-validation is called
    THEN the validation email is sent and 200 is returned
    """
    with app.app_context():
        assert Email_Validations.query.first().attempts == 0

    response = api_client.post(
        _resend_url(app), headers=make_bearer_headers(access_token_unvalidated_user)
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == EMAILS.EMAIL_SENT

    with app.app_context():
        email_validation_row = Email_Validations.query.first()
        assert email_validation_row.attempts == 1


def test_resend_validation_requires_auth(app: Flask, api_client: FlaskClient):
    response = api_client.post(_resend_url(app))

    assert response.status_code == 401
    assert response.get_json()[STD_JSON.MESSAGE] == (
        API_AUTH_FAILURE.AUTHENTICATION_REQUIRED
    )


def test_resend_validation_already_validated_is_400(
    app: Flask,
    api_client: FlaskClient,
    access_token_unvalidated_user: str,
    make_bearer_headers,
):
    """
    GIVEN a bearer user whose email became validated while a stale
        Email_Validations row still exists
    WHEN resend-validation is called
    THEN 400 is returned (the web flow redirects; the API cannot) and the
        stale row is cleaned up
    """
    with app.app_context():
        email_validation_row = Email_Validations.query.first()
        email_validation_row.user.validate_email()
        db.session.commit()

    response = api_client.post(
        _resend_url(app), headers=make_bearer_headers(access_token_unvalidated_user)
    )

    assert response.status_code == 400
    assert response.get_json()[STD_JSON.MESSAGE] == (
        API_AUTH_FAILURE.EMAIL_ALREADY_VALIDATED
    )

    with app.app_context():
        assert Email_Validations.query.count() == 0


def test_resend_validation_rate_limited_within_minute_is_429(
    app: Flask,
    api_client: FlaskClient,
    access_token_unvalidated_user: str,
    make_bearer_headers,
):
    """
    GIVEN an unvalidated user who requested a resend less than a minute ago
    WHEN resend-validation is called again
    THEN 429 with the time-window error code is returned as JSON
    """
    with app.app_context():
        email_validation_row = Email_Validations.query.first()
        email_validation_row.last_attempt = utc_now()
        email_validation_row.attempts = 1
        db.session.commit()

    response = api_client.post(
        _resend_url(app), headers=make_bearer_headers(access_token_unvalidated_user)
    )

    assert response.status_code == 429
    response_json = response.get_json()
    assert response_json[STD_JSON.ERROR_CODE] == (
        EmailValidationErrorCodes.MAX_TIME_EMAIL_VALIDATION_ATTEMPTS
    )
    assert response_json[STD_JSON.MESSAGE].endswith(EMAILS_FAILURE.TOO_MANY_ATTEMPTS)


def test_resend_validation_max_attempts_is_429(
    app: Flask,
    api_client: FlaskClient,
    access_token_unvalidated_user: str,
    make_bearer_headers,
):
    with app.app_context():
        email_validation_row = Email_Validations.query.first()
        email_validation_row.last_attempt = utc_now()
        email_validation_row.attempts = EMAIL_CONSTANTS.MAX_EMAIL_ATTEMPTS_IN_HOUR
        db.session.commit()

    response = api_client.post(
        _resend_url(app), headers=make_bearer_headers(access_token_unvalidated_user)
    )

    assert response.status_code == 429
    response_json = response.get_json()
    assert response_json[STD_JSON.ERROR_CODE] == (
        EmailValidationErrorCodes.MAX_TOTAL_EMAIL_VALIDATION_ATTEMPTS
    )
    assert response_json[STD_JSON.MESSAGE] == EMAILS_FAILURE.TOO_MANY_ATTEMPTS_MAX


def test_resend_validation_missing_row_is_json_404(
    app: Flask,
    api_client: FlaskClient,
    bearer_headers_first_user: dict[str, str],
):
    """
    GIVEN an authenticated user with no Email_Validations row at all
    WHEN resend-validation is called
    THEN the blueprint-scoped 404 errorhandler returns the JSON envelope
        (first_or_404 raised inside an api_v1 view)
    """
    response = api_client.post(_resend_url(app), headers=bearer_headers_first_user)

    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.FAILURE
