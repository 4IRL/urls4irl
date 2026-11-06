import threading
from unittest import mock
from urllib.parse import urlparse

import pytest
from flask import session, url_for
from flask_login import current_user
from requests import Response

from backend import db
from backend.extensions.email_sender.email_sender import EmailSender
from backend.metrics.events import EventName
from backend.models.email_validations import Email_Validations
from backend.models.users import Users
from backend.models.utils import VerifyTokenResponse
from backend.schemas.errors import LoginEmailNotValidatedErrorResponse
from backend.splash.constants import LoginErrorCodes
from backend.splash.utils import decode_resend_validation_token, verify_token
from backend.utils.all_routes import ROUTES
from backend.utils.strings.email_validation_strs import (
    EMAILS,
)
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.splash_form_strs import REGISTER_FORM
from backend.utils.strings.user_strs import MEMBER_SUCCESS, USER_FAILURE
from tests.integration.splash.conftest import register_json
from tests.integration.system.metrics_helpers import count_counter_keys
from tests.models_for_test import valid_user_1

pytestmark = pytest.mark.splash


def test_registered_user_is_not_email_validated(app, load_register_page):
    """
    GIVEN a user trying to register
    WHEN they submit an registration form
    THEN ensure they don't have a validated email and are shown validation modal
    """
    client, csrf_token = load_register_page

    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        json=register_json(valid_user_1),
        headers={"X-CSRFToken": csrf_token},
    )

    # Register returns the opaque success (200) without logging the user in
    assert response.status_code == 200
    assert response.json[STD_JSON.STATUS] == STD_JSON.SUCCESS

    with app.app_context():
        registered_user: Users = Users.query.filter(
            Users.username == valid_user_1[REGISTER_FORM.USERNAME]
        ).first_or_404()
        assert not registered_user.email_confirm.is_validated


def test_registered_not_email_validated_user_access_home_page(load_register_page):
    """
    GIVEN a registered user (but not logged in user) without a validated email, after just registering
    WHEN they try to access the validated user's home page
    THEN ensure they can't, and redirects them
    """
    client, csrf_token_string = load_register_page

    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        json=register_json(valid_user_1),
        headers={"X-CSRFToken": csrf_token_string},
    )

    # Correctly responds with the opaque success (200)
    assert response.status_code == 200
    assert response.json[STD_JSON.STATUS] == STD_JSON.SUCCESS

    # Register no longer logs the user in, so no session exists post-register
    assert current_user.is_authenticated is False

    response = client.get(url_for(ROUTES.UTUBS.HOME), follow_redirects=True)
    assert response.history[0].status_code == 302
    # An anonymous user hitting /home is bounced by login_required back to the
    # splash page (with a ?next= back-link) rather than the in-session
    # email-unvalidated guard that used to fire when register logged them in.
    assert urlparse(response.history[0].location).path == url_for(
        ROUTES.SPLASH.SPLASH_PAGE
    )
    assert response.status_code == 200
    assert IDENTIFIERS.SPLASH_PAGE.encode() in response.data


def test_registered_not_email_validated_tries_registering_again(
    register_first_user_without_email_validation, load_register_page
):
    """
    GIVEN a registered user (but not logged in) without a validated email, starting a new session
    WHEN they try to register again with their previously used email
    THEN the response is the uniform opaque success (no email-not-validated leak)

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: MEMBER_SUCCESS.CONFIRM_EMAIL_SENT,
    }
    """
    registered_user, _ = register_first_user_without_email_validation
    client, csrf_token_string = load_register_page

    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        json=register_json(valid_user_1),
        headers={"X-CSRFToken": csrf_token_string},
    )

    # Ensure json response from server is the opaque success
    register_user_response_json = response.json
    assert register_user_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        register_user_response_json[STD_JSON.MESSAGE]
        == MEMBER_SUCCESS.CONFIRM_EMAIL_SENT
    )

    assert response.status_code == 200


def test_registered_not_email_validated_tries_logging_in(
    register_first_user_without_email_validation, load_login_page
):
    """
    GIVEN a registered user (but not logged in user) without a validated email, starting a new session
    WHEN they try to login with their previously used email
    THEN ensure proper JSON response with form errors is returned

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED,
        STD_JSON.ERROR_CODE: Integer representing the failure code, 1 for registered but not email validated
    }
    """
    registered_user, _ = register_first_user_without_email_validation
    client, csrf_token_string = load_login_page

    response = client.post(
        url_for(ROUTES.SPLASH.LOGIN),
        json={
            REGISTER_FORM.USERNAME: valid_user_1[REGISTER_FORM.USERNAME],
            REGISTER_FORM.PASSWORD: valid_user_1[REGISTER_FORM.PASSWORD],
        },
        headers={"X-CSRFToken": csrf_token_string},
    )

    # Ensure json response from server is valid
    login_user_response_json = response.json
    assert login_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        login_user_response_json[STD_JSON.MESSAGE]
        == USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED
    )
    assert (
        int(login_user_response_json[STD_JSON.ERROR_CODE])
        == LoginErrorCodes.ACCOUNT_NOT_EMAIL_VALIDATED
    )
    assert login_user_response_json[STD_JSON.RESEND_TOKEN]
    LoginEmailNotValidatedErrorResponse.model_validate(login_user_response_json)

    assert response.status_code == 401


def test_valid_token_generated_on_user_register(
    app, register_first_user_without_email_validation
):
    """
    GIVEN a registered user with an unvalidated email
    WHEN they registered
    THEN ensure a token was correctly created referencing the user
    """
    new_user, _ = register_first_user_without_email_validation

    with app.app_context():
        registered_user: Users = Users.query.filter(
            Users.email == new_user[REGISTER_FORM.EMAIL].lower()
        ).first()
        user_token = registered_user.email_confirm.validation_token
        assert verify_token(user_token, EMAILS.VALIDATE_EMAIL) == VerifyTokenResponse(
            user=registered_user, is_expired=False, failed_due_to_exception=False
        )


@mock.patch("backend.extensions.notifications.notifications.requests.post")
@mock.patch.object(EmailSender, "send_account_email_confirmation")
def test_token_validates_user(
    mock_send_confirmation, mock_request_post, app, load_register_page
):
    """
    GIVEN a user trying to register via the register page
    WHEN they register and click on the link received in their email
    THEN ensure their email is validated and they are logged in and token to the home page
    """
    # Register now sends the confirmation email server-side through the same
    # global requests.post mailjet uses; stub that send so the welcome
    # notification dispatched on validation is the only requests.post counted.
    ok_response = Response()
    ok_response.status_code = 200
    mock_send_confirmation.return_value = ok_response

    notification_sent = threading.Event()

    def mock_post_with_event(*args, **kwargs):
        mock_response = type("MockResponse", (), {"status_code": 200})()
        notification_sent.set()  # Signal that the request was made
        return mock_response

    mock_request_post.side_effect = mock_post_with_event

    client, csrf_token = load_register_page

    client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        json=register_json(valid_user_1),
        headers={"X-CSRFToken": csrf_token},
    )

    with app.app_context():
        user: Users = Users.query.filter(
            Users.email == valid_user_1[REGISTER_FORM.EMAIL].lower()
        ).first()
        user_token = user.email_confirm.validation_token
        assert not user.email_validated and not user.email_confirm.is_validated

    response = client.get(
        url_for(ROUTES.SPLASH.VALIDATE_EMAIL, token=user_token), follow_redirects=True
    )

    # Wait for notification to be sent (with timeout)
    assert notification_sent.wait(timeout=5.0), (
        "Notification was not sent within timeout"
    )

    assert len(response.history) == 1
    assert response.history[0].status_code == 302
    assert response.history[0].location == url_for(ROUTES.UTUBS.HOME)
    assert response.status_code == 200
    mock_request_post.assert_called_once()

    # Ensure user logged in
    assert current_user.get_id() == user.get_id()
    assert current_user == user
    assert session[EMAILS.EMAIL_VALIDATED_SESS_KEY] is True

    with app.app_context():
        user: Users = Users.query.filter(
            Users.email == valid_user_1[REGISTER_FORM.EMAIL].lower()
        ).first()
        assert user.email_validated and user.email_confirm is None


@mock.patch("backend.extensions.notifications.notifications.requests.post")
@mock.patch.object(EmailSender, "send_account_email_confirmation")
def test_token_validates_user_records_email_verified_metric(
    mock_send_confirmation,
    mock_request_post,
    metrics_enabled_app,
    provide_metrics_redis,
    app,
    load_register_page,
):
    """
    GIVEN a user with metrics enabled who has just registered
    WHEN they click the validation link in their email
    THEN the email is validated AND exactly one EMAIL_VERIFIED counter key
        is written to the metrics Redis DB.
    """
    # Isolate the register-time server-side confirmation send from the global
    # requests.post the welcome notification uses (see test_token_validates_user).
    ok_response = Response()
    ok_response.status_code = 200
    mock_send_confirmation.return_value = ok_response

    notification_sent = threading.Event()

    def mock_post_with_event(*args, **kwargs):
        mock_response = type("MockResponse", (), {"status_code": 200})()
        notification_sent.set()
        return mock_response

    mock_request_post.side_effect = mock_post_with_event

    client, csrf_token = load_register_page

    client.post(
        url_for(ROUTES.SPLASH.REGISTER),
        json=register_json(valid_user_1),
        headers={"X-CSRFToken": csrf_token},
    )

    with app.app_context():
        user: Users = Users.query.filter(
            Users.email == valid_user_1[REGISTER_FORM.EMAIL].lower()
        ).first()
        user_token = user.email_confirm.validation_token

    # Before-state: no EMAIL_VERIFIED counter exists yet
    assert count_counter_keys(provide_metrics_redis, EventName.EMAIL_VERIFIED) == 0

    response = client.get(
        url_for(ROUTES.SPLASH.VALIDATE_EMAIL, token=user_token), follow_redirects=True
    )

    assert notification_sent.wait(timeout=5.0)
    assert response.status_code == 200
    assert count_counter_keys(provide_metrics_redis, EventName.EMAIL_VERIFIED) == 1


def test_token_can_expire(app, register_first_user_without_email_validation):
    """
    GIVEN a user trying to validate their email
    WHEN they click on the validation link in their email after the token has expired
    THEN ensure that the verification will not be successful
    """
    registered_user, _ = register_first_user_without_email_validation

    with app.app_context():
        user: Users = Users.query.filter(
            Users.email == registered_user[REGISTER_FORM.EMAIL].lower()
        ).first()
        quick_expiring_token = user.get_email_validation_token(expires_in=0)

        assert verify_token(
            quick_expiring_token, EMAILS.VALIDATE_EMAIL
        ) == VerifyTokenResponse(
            user=None,
            is_expired=True,
        )


def test_expired_token_accessed_shows_error_to_user(
    app, register_first_user_without_email_validation, load_register_page
):
    """
    GIVEN a user trying to validate their email
    WHEN they click on the validation link in their email after the token has expired
    THEN ensure that the user is shown the validate email modal again with an error message
    """
    registered_user, _ = register_first_user_without_email_validation
    client, _ = load_register_page

    with app.app_context():
        user: Users = Users.query.filter(
            Users.email == registered_user[REGISTER_FORM.EMAIL].lower()
        ).first()
        quick_expiring_token = user.get_email_validation_token(expires_in=0)
        email_validation = Email_Validations(validation_token=quick_expiring_token)
        user.email_confirm = email_validation
        db.session.commit()

    response = client.get(
        url_for(ROUTES.SPLASH.VALIDATE_EMAIL, token=quick_expiring_token),
        follow_redirects=True,
    )

    assert EMAILS.TOKEN_EXPIRED.encode() in response.data

    # Visiting the expired link creates no session
    home_response = client.get(url_for(ROUTES.UTUBS.HOME))
    assert home_response.status_code == 302
    assert urlparse(home_response.location).path == url_for(ROUTES.SPLASH.SPLASH_PAGE)

    # The page carries a resend token that resolves to the link's owner, and
    # the dismiss button is labelled "Close" (no login modal to go back to)
    page = response.get_data(as_text=True)
    resend_token = page.split('data-resend-token="', 1)[1].split('"', 1)[0]
    with app.app_context():
        resend_user = decode_resend_validation_token(resend_token)
        assert resend_user is not None
        assert resend_user.email == registered_user[REGISTER_FORM.EMAIL].lower()
    assert 'id="BackToLoginFromConfirmEmail"' in page
    assert ">Close</button>" in page


def test_expired_token_second_visit_returns_404(
    app, register_first_user_without_email_validation, load_register_page
):
    """
    GIVEN an expired validation token that was already used once on /validate/expired
    WHEN the same expired token is presented again
    THEN ensure a 404 is returned, because the first visit re-minted the token
    """
    registered_user, _ = register_first_user_without_email_validation
    client, _ = load_register_page

    with app.app_context():
        user: Users = Users.query.filter(
            Users.email == registered_user[REGISTER_FORM.EMAIL].lower()
        ).first()
        quick_expiring_token = user.get_email_validation_token(expires_in=0)
        user.email_confirm = Email_Validations(validation_token=quick_expiring_token)
        db.session.commit()

    expired_url = url_for("splash.validate_email_expired", token=quick_expiring_token)
    first_response = client.get(expired_url)
    assert first_response.status_code == 200

    second_response = client.get(expired_url)
    assert second_response.status_code == 404


def test_authenticated_user_on_expired_page_redirects_home_without_remint(
    login_first_user_with_register,
):
    """
    GIVEN a logged-in user
    WHEN they request /validate/expired with an expired token
    THEN ensure they are redirected to HOME and the stored token is not re-minted
    """
    client, _, logged_in_user, app = login_first_user_with_register

    with app.app_context():
        user: Users = Users.query.get(logged_in_user.id)
        quick_expiring_token = user.get_email_validation_token(expires_in=0)
        user.email_confirm = Email_Validations(validation_token=quick_expiring_token)
        db.session.commit()

    response = client.get(
        url_for("splash.validate_email_expired", token=quick_expiring_token)
    )

    assert response.status_code == 302
    assert urlparse(response.location).path == url_for(ROUTES.UTUBS.HOME)

    with app.app_context():
        user = Users.query.get(logged_in_user.id)
        assert user.email_confirm.validation_token == quick_expiring_token
