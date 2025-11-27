import threading
from unittest import mock
from flask import url_for
from flask_login import current_user
import pytest

from src.models.utils import VerifyTokenResponse
from src.splash.utils import verify_token
from tests.models_for_test import valid_user_1
from src import db
from src.models.email_validations import Email_Validations
from src.models.users import Users
from src.utils.all_routes import ROUTES
from src.utils.constants import EMAIL_CONSTANTS
from src.utils.datetime_utils import utc_now
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.html_identifiers import IDENTIFIERS
from src.utils.strings.splash_form_strs import REGISTER_FORM
from src.utils.strings.email_validation_strs import (
    EMAILS,
    EMAILS_FAILURE,
    VALIDATE_YOUR_EMAIL,
)
from src.utils.strings.user_strs import USER_FAILURE

pytestmark = pytest.mark.splash

VALIDATE_EMAIL_MODAL_TITLE = f'<h1 class="modal-title validate-email-text validate-email-title">{VALIDATE_YOUR_EMAIL}</h1>'


def test_registered_user_is_not_email_validated(app, load_register_page):
    """
    GIVEN a user trying to register
    WHEN they submit an registration form
    THEN ensure they don't have a validated email and are shown validation modal
    """
    client, csrf_token = load_register_page

    valid_user_1[REGISTER_FORM.CSRF_TOKEN] = csrf_token

    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER), data=valid_user_1, follow_redirects=True
    )

    # Assert user gets shown email validation modal
    assert response.status_code == 201
    assert VALIDATE_EMAIL_MODAL_TITLE.encode() in response.data
    assert f"{EMAILS.EMAIL_VALIDATION_MODAL_CALL}".encode() in response.data

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

    valid_user_1[REGISTER_FORM.CSRF_TOKEN] = csrf_token_string
    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER), data=valid_user_1, follow_redirects=True
    )

    # Correctly sends URL to email validation modal
    assert response.status_code == 201
    assert VALIDATE_EMAIL_MODAL_TITLE.encode() in response.data

    response = client.get(url_for(ROUTES.UTUBS.HOME), follow_redirects=True)
    assert response.history[0].status_code == 302
    assert response.history[0].location == url_for(ROUTES.SPLASH.SPLASH_PAGE)
    assert response.status_code == 200
    assert IDENTIFIERS.SPLASH_PAGE.encode() in response.data


def test_registered_not_email_validated_user_access_register_login(load_register_page):
    """
    GIVEN a registered user (but not logged in user) without a validated email, after just registering
    WHEN they try to access the login or register pages
    THEN ensure they are redirected to the email validation modal
    """
    client, csrf_token_string = load_register_page

    valid_user_1[REGISTER_FORM.CSRF_TOKEN] = csrf_token_string
    response = client.post(
        url_for(ROUTES.SPLASH.REGISTER), data=valid_user_1, follow_redirects=True
    )

    # Correctly sends URL to email validation modal
    assert response.status_code == 201
    assert VALIDATE_EMAIL_MODAL_TITLE.encode() in response.data

    urls_to_check = (url_for(ROUTES.SPLASH.REGISTER), url_for(ROUTES.SPLASH.LOGIN))

    for url in urls_to_check:
        response = client.get(url, follow_redirects=True)
        assert response.history[0].status_code == 302
        assert response.history[0].location == url_for(ROUTES.SPLASH.CONFIRM_EMAIL)
        assert response.status_code == 200
        assert VALIDATE_EMAIL_MODAL_TITLE.encode() in response.data


def test_registered_not_email_validated_tries_registering_again(
    register_first_user_without_email_validation, load_register_page
):
    """
    GIVEN a registered user (but not logged in user) without a validated email, starting a new session
    WHEN they try to register with their previously used email
    THEN ensure proper JSON response with form errors is returned

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED,
        STD_JSON.ERROR_CODE: Integer representing the failure code, 1 for registered but not email validated
    }
    """
    registered_user, _ = register_first_user_without_email_validation
    client, csrf_token_string = load_register_page

    registered_user[REGISTER_FORM.CSRF_TOKEN] = csrf_token_string
    response = client.post(url_for(ROUTES.SPLASH.REGISTER), data=valid_user_1)

    # Ensure json response from server is valid
    register_user_response_json = response.json
    assert register_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        register_user_response_json[STD_JSON.MESSAGE]
        == USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED
    )
    assert int(register_user_response_json[STD_JSON.ERROR_CODE]) == 1

    assert response.status_code == 401


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

    registered_user[REGISTER_FORM.CSRF_TOKEN] = csrf_token_string
    response = client.post(url_for(ROUTES.SPLASH.LOGIN), data=valid_user_1)

    # Ensure json response from server is valid
    login_user_response_json = response.json
    assert login_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        login_user_response_json[STD_JSON.MESSAGE]
        == USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED
    )
    assert int(login_user_response_json[STD_JSON.ERROR_CODE]) == 1

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


@mock.patch("src.extensions.notifications.notifications.requests.post")
def test_token_validates_user(mock_request_post, app, load_register_page):
    """
    GIVEN a user trying to register via the register page
    WHEN they register and click on the link received in their email
    THEN ensure their email is validated and they are logged in and token to the home page
    """
    notification_sent = threading.Event()

    def mock_post_with_event(*args, **kwargs):
        mock_response = type("MockResponse", (), {"status_code": 200})()
        notification_sent.set()  # Signal that the request was made
        return mock_response

    mock_request_post.side_effect = mock_post_with_event

    client, csrf_token = load_register_page

    valid_user_1[REGISTER_FORM.CSRF_TOKEN] = csrf_token

    client.post(
        url_for(ROUTES.SPLASH.REGISTER), data=valid_user_1, follow_redirects=True
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
    assert notification_sent.wait(
        timeout=5.0
    ), "Notification was not sent within timeout"

    assert len(response.history) == 1
    assert response.history[0].status_code == 302
    assert response.history[0].location == url_for(ROUTES.UTUBS.HOME)
    assert response.status_code == 200
    mock_request_post.assert_called_once()

    # Ensure user logged in
    assert current_user.get_id() == user.get_id()
    assert current_user == user

    with app.app_context():
        user: Users = Users.query.filter(
            Users.email == valid_user_1[REGISTER_FORM.EMAIL].lower()
        ).first()
        assert user.email_validated and user.email_confirm is None


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

        assert verify_token(quick_expiring_token, EMAILS.VALIDATE_EMAIL) == (
            None,
            True,
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


def test_success_on_send_of_email(app, load_register_page):
    """
    GIVEN a user trying to validate email after registering
    WHEN they request a validation email
    THEN ensure that server responds with a success and proper JSON

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: EMAILS.EMAIL_SENT
    }
    """
    client, csrf_token = load_register_page

    valid_user_1[REGISTER_FORM.CSRF_TOKEN] = csrf_token

    client.post(
        url_for(ROUTES.SPLASH.REGISTER), data=valid_user_1, follow_redirects=True
    )
    send_email_response = client.post(
        url_for(ROUTES.SPLASH.SEND_VALIDATION_EMAIL),
        data={REGISTER_FORM.CSRF_TOKEN: csrf_token},
    )

    email_send_json = send_email_response.json
    assert send_email_response.status_code == 200
    assert email_send_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert email_send_json[STD_JSON.MESSAGE] == EMAILS.EMAIL_SENT


def test_min_rate_limiting_of_sending_email(app, load_register_page):
    """
    GIVEN a user trying to validate email after registering
    WHEN they request a validation email twice within a minute
    THEN ensure that the second attempt responds in an error with a JSON

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: "{Max Attempts in 1 Hr - attempts used}" + EMAILS_FAILURE.TOO_MANY_ATTEMPTS,
        STD_JSON.ERROR_CODE: Integer representing the failure code, 2 for too many attempts within 1 minute
    }
    """
    client, csrf_token = load_register_page

    valid_user_1[REGISTER_FORM.CSRF_TOKEN] = csrf_token

    client.post(
        url_for(ROUTES.SPLASH.REGISTER), data=valid_user_1, follow_redirects=True
    )
    client.post(
        url_for(ROUTES.SPLASH.SEND_VALIDATION_EMAIL),
        data={REGISTER_FORM.CSRF_TOKEN: csrf_token},
    )

    send_second_email_response = client.post(
        url_for(ROUTES.SPLASH.SEND_VALIDATION_EMAIL),
        data={REGISTER_FORM.CSRF_TOKEN: csrf_token},
    )
    second_email_send_json = send_second_email_response.json

    assert send_second_email_response.status_code == 429
    assert second_email_send_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert int(second_email_send_json[STD_JSON.ERROR_CODE]) == 2
    assert (
        second_email_send_json[STD_JSON.MESSAGE]
        == str(EMAIL_CONSTANTS.MAX_EMAIL_ATTEMPTS_IN_HOUR - 1)
        + EMAILS_FAILURE.TOO_MANY_ATTEMPTS
    )


def test_max_rate_limiting_of_sending_email(app, load_register_page):
    """
    GIVEN a user trying to validate email after registering
    WHEN they request a validation email more than 5 times in one hour
    THEN ensure that the second attempt responds in an error with a JSON

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: "{Max Attempts in 1 Hr - attempts used}" + EMAILS_FAILURE.TOO_MANY_ATTEMPTS,
        STD_JSON.ERROR_CODE: Integer representing the failure code, 1 for too many attempts within 1 hr
    }
    """
    client, csrf_token = load_register_page

    valid_user_1[REGISTER_FORM.CSRF_TOKEN] = csrf_token

    client.post(
        url_for(ROUTES.SPLASH.REGISTER), data=valid_user_1, follow_redirects=True
    )

    with app.app_context():
        user: Users = Users.query.filter(
            Users.email == valid_user_1[REGISTER_FORM.EMAIL].lower()
        ).first()
        user.email_confirm.attempts = EMAIL_CONSTANTS.MAX_EMAIL_ATTEMPTS_IN_HOUR + 1
        user.email_confirm.last_attempt = utc_now()
        db.session.commit()

    email_response = client.post(
        url_for(ROUTES.SPLASH.SEND_VALIDATION_EMAIL),
        data={REGISTER_FORM.CSRF_TOKEN: csrf_token},
    )
    email_response_json = email_response.json

    assert email_response.status_code == 429
    assert email_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert int(email_response_json[STD_JSON.ERROR_CODE]) == 1
    assert email_response_json[STD_JSON.MESSAGE] == EMAILS_FAILURE.TOO_MANY_ATTEMPTS_MAX
