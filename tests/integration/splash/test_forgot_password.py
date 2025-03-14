from datetime import datetime, timedelta
from flask import url_for
import pytest

from src.utils.strings.email_validation_strs import EMAILS_FAILURE
from src.utils.strings.html_identifiers import IDENTIFIERS
from tests.models_for_test import valid_user_1
from src import db
from src.models.forgot_passwords import Forgot_Passwords
from src.models.users import Users
from src.models.utils import verify_token
from src.utils import constants as U4I_CONSTANTS
from src.utils.all_routes import ROUTES
from src.utils.datetime_utils import utc_now
from src.utils.strings.splash_form_strs import REGISTER_FORM
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.reset_password_strs import FORGOT_PASSWORD, RESET_PASSWORD

pytestmark = pytest.mark.splash

USER_CONSTANTS = U4I_CONSTANTS.USER_CONSTANTS
FORGOT_PASSWORD_MODAL_TITLE = '<h4 class="modal-title">Forgot your password?</h4>'


def test_user_logged_in_email_validated_cannot_access_forgot_password(
    register_first_user, login_first_user_without_register
):
    """
    GIVEN a user who is already logged in and email validated
    WHEN they try to make a GET to the /forgot-password URL
    THEN ensure they cannot access - only access is from non-logged in users
        who are email validated. User should get redirected to their home page
    """
    client, _, _, _ = login_first_user_without_register

    forgot_password_response = client.get(
        url_for(ROUTES.SPLASH.FORGOT_PASSWORD_PAGE), follow_redirects=True
    )

    # Only one redirect to user home page
    assert len(forgot_password_response.history) == 1
    redirect_response = forgot_password_response.history[0]

    assert redirect_response.location == url_for(ROUTES.UTUBS.HOME)
    assert redirect_response.status_code == 302


def test_user_registered_not_email_validated_cannot_access_forgot_password(
    load_register_page,
):
    """
    GIVEN a user who just registered and the email confirmation modal has popped up
    WHEN they try to make a GET to the /forgot-password URL
    THEN ensure they cannot access - only access is from non-logged in users
        who are email validated. User should get redirected to the email confirmation page
    """
    client, csrf_token = load_register_page

    register_response = client.post(
        "/register",
        data={
            REGISTER_FORM.USERNAME: valid_user_1[REGISTER_FORM.USERNAME],
            REGISTER_FORM.EMAIL: valid_user_1[REGISTER_FORM.EMAIL],
            REGISTER_FORM.CONFIRM_EMAIL: valid_user_1[REGISTER_FORM.EMAIL],
            REGISTER_FORM.PASSWORD: valid_user_1[REGISTER_FORM.PASSWORD],
            REGISTER_FORM.CONFIRM_PASSWORD: valid_user_1[REGISTER_FORM.PASSWORD],
            REGISTER_FORM.CSRF_TOKEN: csrf_token,
        },
    )

    assert register_response.status_code == 201

    forgot_password_response = client.get(
        url_for(ROUTES.SPLASH.FORGOT_PASSWORD_PAGE), follow_redirects=True
    )

    # Only one redirect to user home page
    assert len(forgot_password_response.history) == 1
    redirect_response = forgot_password_response.history[0]

    assert redirect_response.location == url_for(ROUTES.SPLASH.CONFIRM_EMAIL)
    assert redirect_response.status_code == 302


def test_valid_user_requests_forgot_password_form(register_first_user, load_login_page):
    """
    GIVEN a user who is not logged in but is email validated and registered
    WHEN they try to make a GET to the /forgot-password URL
    THEN server successfully sends the user the forgot password form and responds with
        200 status code
    """
    client, _ = load_login_page

    forgot_password_response = client.get(url_for(ROUTES.SPLASH.FORGOT_PASSWORD_PAGE))

    assert forgot_password_response.status_code == 200
    assert FORGOT_PASSWORD_MODAL_TITLE.encode() in forgot_password_response.data


def test_valid_user_posts_forgot_password_form_without_csrf(
    register_first_user, load_login_page
):
    """
    GIVEN a user who is not logged in but is email validated and registered
    WHEN they try to make a POST to the /forgot-password URL with a missing CSRF token
    THEN server responds with a 400 and proper error message
    """
    new_user, _ = register_first_user
    client, _ = load_login_page

    client.get(url_for(ROUTES.SPLASH.FORGOT_PASSWORD_PAGE))

    forgot_password_post_response = client.post(
        url_for(ROUTES.SPLASH.FORGOT_PASSWORD_PAGE),
        data={FORGOT_PASSWORD.EMAIL: new_user[FORGOT_PASSWORD.EMAIL]},
    )

    # Assert invalid response code
    assert forgot_password_post_response.status_code == 403
    assert forgot_password_post_response.content_type == "text/html; charset=utf-8"
    assert IDENTIFIERS.HTML_403.encode() in forgot_password_post_response.data


def test_forgot_password_with_invalid_email_fails(load_login_page):
    """
    GIVEN a user who accesses the forgot password form from the login page
    WHEN the user inputs an ill-formatted email, such as "Cat"
    THEN server responds with 401 and JSON containing form errors


    JSON response as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.ERROR_CODE: 1,
        STD_JSON.MESSAGE: FORGOT_PASSWORD.INVALID_EMAIL,
        STD_JSON.ERRORS: {
            STD_JSON.EMAIL: ["Invalid email address.",]
        }
    }
    """
    client, csrf_token = load_login_page
    improper_email = "Cat"

    response = client.post(
        url_for(ROUTES.SPLASH.FORGOT_PASSWORD_PAGE),
        data={
            FORGOT_PASSWORD.EMAIL: improper_email,
            FORGOT_PASSWORD.CSRF_TOKEN: csrf_token,
        },
    )

    assert response.status_code == 401
    response_json = response.json

    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert int(response_json[STD_JSON.ERROR_CODE]) == 1
    assert response_json[STD_JSON.MESSAGE] == FORGOT_PASSWORD.INVALID_EMAIL
    assert (
        EMAILS_FAILURE.INVALID_EMAIL_INPUT
        in response_json[STD_JSON.ERRORS][FORGOT_PASSWORD.EMAIL][-1]
    )


def test_forgot_password_with_email_not_in_database(app, load_login_page):
    """
    GIVEN a user who accesses the forgot password form from the login page
    WHEN the user inputs an email that isn't in the database
    THEN server still shows success with a 200 response status code, with proper JSON response
        Forgot_Passwords object is not created.

    JSON response as follows:
    {
        STD_JSON.STATUS: STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: RESET_PASSWORD.EMAIL_SENT_MESSAGE,
    }
    """
    client, csrf_token = load_login_page
    nonregistered_user = valid_user_1

    with app.app_context():
        num_of_forgot_password_objs = Forgot_Passwords.query.count()

    response = client.post(
        url_for(ROUTES.SPLASH.FORGOT_PASSWORD_PAGE),
        data={
            FORGOT_PASSWORD.EMAIL: nonregistered_user[FORGOT_PASSWORD.EMAIL],
            FORGOT_PASSWORD.CSRF_TOKEN: csrf_token,
        },
    )

    assert response.status_code == 200

    response_json = response.json
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == FORGOT_PASSWORD.EMAIL_SENT_MESSAGE

    with app.app_context():
        assert num_of_forgot_password_objs == Forgot_Passwords.query.count()


def test_forgot_password_with_validated_email(
    app, register_first_user, load_login_page
):
    """
    GIVEN a user who accesses the forgot password form from the login page
    WHEN the user inputs an email that has been validated
    THEN server still shows success with a 200 response status code, with proper JSON response
        Forgot_Passwords object is created to keep track of password resets for this user, and
        attempts are incremented to 1.

    JSON response as follows:
    {
        STD_JSON.STATUS: STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: RESET_PASSWORD.EMAIL_SENT_MESSAGE,
    }
    """
    new_user, _ = register_first_user
    client, csrf_token = load_login_page

    with app.app_context():
        num_forgot_passwords = Forgot_Passwords.query.count()
        users: list[Users] = Users.query.filter(
            Users.email == new_user[FORGOT_PASSWORD.EMAIL].lower()
        ).all()
        user_id = users[-1].id

    response = client.post(
        url_for(ROUTES.SPLASH.FORGOT_PASSWORD_PAGE),
        data={
            FORGOT_PASSWORD.EMAIL: new_user[FORGOT_PASSWORD.EMAIL],
            FORGOT_PASSWORD.CSRF_TOKEN: csrf_token,
        },
    )

    assert response.status_code == 200

    response_json = response.json
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == FORGOT_PASSWORD.EMAIL_SENT_MESSAGE

    with app.app_context():
        forgot_password_objs = Forgot_Passwords.query.filter(
            Forgot_Passwords.user_id == user_id
        ).all()
        assert len(forgot_password_objs) == num_forgot_passwords + 1
        assert forgot_password_objs[-1].attempts == 1


def test_forgot_password_with_validated_email_uppercase(
    app, register_first_user, load_login_page
):
    """
    GIVEN a user who accesses the forgot password form from the login page
    WHEN the user inputs an email that has been validated
    THEN server still shows success with a 200 response status code, with proper JSON response
        Forgot_Passwords object is created to keep track of password resets for this user, and
        attempts are incremented to 1.

    JSON response as follows:
    {
        STD_JSON.STATUS: STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: RESET_PASSWORD.EMAIL_SENT_MESSAGE,
    }
    """
    new_user, _ = register_first_user
    client, csrf_token = load_login_page

    with app.app_context():
        num_forgot_passwords = Forgot_Passwords.query.count()
        all_users_with_email: list[Users] = Users.query.filter(
            Users.email == new_user[FORGOT_PASSWORD.EMAIL].lower()
        ).all()
        user = all_users_with_email[-1]
        user.email = new_user[FORGOT_PASSWORD.EMAIL].lower()
        db.session.commit()
        user_id = user.id

    response = client.post(
        url_for(ROUTES.SPLASH.FORGOT_PASSWORD_PAGE),
        data={
            FORGOT_PASSWORD.EMAIL: new_user[FORGOT_PASSWORD.EMAIL].upper(),
            FORGOT_PASSWORD.CSRF_TOKEN: csrf_token,
        },
    )

    assert response.status_code == 200

    response_json = response.json
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == FORGOT_PASSWORD.EMAIL_SENT_MESSAGE

    with app.app_context():
        forgot_password_objs: list[Forgot_Passwords] = Forgot_Passwords.query.all()
        assert len(forgot_password_objs) == num_forgot_passwords + 1
        forgot_password_user_object = forgot_password_objs[-1]
        assert forgot_password_user_object.user_id == user_id
        assert forgot_password_user_object.attempts == 1


def test_forgot_password_with_non_validated_email(
    app, register_first_user_without_email_validation, load_login_page
):
    """
    GIVEN a user who accesses the forgot password form from the login page
    WHEN the user inputs an email that has not been validated
    THEN server still shows success with a 200 response status code, with proper JSON response
        Forgot_Passwords object is not created.

    JSON response as follows:
    {
        STD_JSON.STATUS: STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: RESET_PASSWORD.EMAIL_SENT_MESSAGE,
    }
    """
    new_user, _ = register_first_user_without_email_validation
    client, csrf_token = load_login_page

    with app.app_context():
        num_forgot_passwords = Forgot_Passwords.query.count()

    response = client.post(
        url_for(ROUTES.SPLASH.FORGOT_PASSWORD_PAGE),
        data={
            FORGOT_PASSWORD.EMAIL: new_user[FORGOT_PASSWORD.EMAIL],
            FORGOT_PASSWORD.CSRF_TOKEN: csrf_token,
        },
    )

    assert response.status_code == 200

    response_json = response.json
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == FORGOT_PASSWORD.EMAIL_SENT_MESSAGE

    with app.app_context():
        assert Forgot_Passwords.query.count() == num_forgot_passwords


def test_forgot_password_rate_limits_correctly(
    app, register_first_user, load_login_page
):
    """
    GIVEN a user who accesses the forgot password form from the login page
    WHEN the user inputs an email that has been validated, and POSTs the form twice in one minute
    THEN server still shows success with a 200 response status code, with proper JSON response
        Forgot_Passwords object is created, and is used to rate limit the user.

    JSON response as follows:
    {
        STD_JSON.STATUS: STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: RESET_PASSWORD.EMAIL_SENT_MESSAGE,
    }
    """
    new_user, _ = register_first_user
    client, csrf_token = load_login_page

    with app.app_context():
        num_forgot_passwords = Forgot_Passwords.query.count()
        all_users_with_email: list[Users] = Users.query.filter(
            Users.email == new_user[FORGOT_PASSWORD.EMAIL].lower()
        ).all()
        user_id = all_users_with_email[-1].id

    initial_send_time: datetime = utc_now()
    first_response = client.post(
        url_for(ROUTES.SPLASH.FORGOT_PASSWORD_PAGE),
        data={
            FORGOT_PASSWORD.EMAIL: new_user[FORGOT_PASSWORD.EMAIL],
            FORGOT_PASSWORD.CSRF_TOKEN: csrf_token,
        },
    )

    second_send_time: datetime = utc_now()
    second_response = client.post(
        url_for(ROUTES.SPLASH.FORGOT_PASSWORD_PAGE),
        data={
            FORGOT_PASSWORD.EMAIL: new_user[FORGOT_PASSWORD.EMAIL],
            FORGOT_PASSWORD.CSRF_TOKEN: csrf_token,
        },
    )

    for response in (
        first_response,
        second_response,
    ):
        assert response.status_code == 200

        response_json = response.json
        assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
        assert response_json[STD_JSON.MESSAGE] == FORGOT_PASSWORD.EMAIL_SENT_MESSAGE

    with app.app_context():
        forgot_password_objs = Forgot_Passwords.query.all()
        assert len(forgot_password_objs) == num_forgot_passwords + 1
        new_forgot_password: Forgot_Passwords = forgot_password_objs[-1]
        assert new_forgot_password.user_id == user_id

        assert new_forgot_password.attempts == 1
        last_attempt_time = new_forgot_password.last_attempt
        assert (
            last_attempt_time < second_send_time
            and last_attempt_time >= initial_send_time
        )


def test_forgot_password_generates_token_correctly(
    app, register_first_user, load_login_page
):
    """
    GIVEN a user who accesses the forgot password form from the login page
    WHEN the user inputs an email that has been validated, and POSTs the form twice in one minute
    THEN server successfully generates a reset password token for the user, and responds properly
        with a 200 status code and a formatted JSON message

    JSON response as follows:
    {
        STD_JSON.STATUS: STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: FORGOT_PASSWORD.EMAIL_SENT_MESSAGE,
    }
    """
    new_user, _ = register_first_user
    client, csrf_token = load_login_page

    with app.app_context():
        num_forgot_passwords = Forgot_Passwords.query.count()
        all_users_with_email: list[Users] = Users.query.filter(
            Users.email == new_user[FORGOT_PASSWORD.EMAIL].lower()
        ).all()
        user_id = all_users_with_email[-1].id

    forgot_password_response = client.post(
        url_for(ROUTES.SPLASH.FORGOT_PASSWORD_PAGE),
        data={
            FORGOT_PASSWORD.EMAIL: valid_user_1[FORGOT_PASSWORD.EMAIL],
            FORGOT_PASSWORD.CSRF_TOKEN: csrf_token,
        },
    )

    assert forgot_password_response.status_code == 200
    forgot_password_response_json = forgot_password_response.json
    assert forgot_password_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        forgot_password_response_json[STD_JSON.MESSAGE]
        == FORGOT_PASSWORD.EMAIL_SENT_MESSAGE
    )

    with app.app_context():
        forgot_password_objs = Forgot_Passwords.query.all()
        assert len(forgot_password_objs) == num_forgot_passwords + 1
        new_forgot_password: Forgot_Passwords = forgot_password_objs[-1]
        assert new_forgot_password.user_id == user_id

        registered_user = Users.query.filter(
            Users.email == new_user[FORGOT_PASSWORD.EMAIL].lower()
        ).first()

        token = new_forgot_password.reset_token
        assert verify_token(token, RESET_PASSWORD.RESET_PASSWORD_KEY) == (
            registered_user,
            False,
        )


def test_user_requests_reset_after_password_reset_object_older_than_hour(
    user_attempts_reset_password_one_hour_old,
):
    """
    GIVEN a user having previously forgotten their password
    WHEN the user forgets password more than one hour after their previous attempt
    THEN ensure a new token is generated and captured attempt timings in Forgot_Passwords object are updated
     and the server responds with a 200 status code

    JSON response as follows:
    {
        STD_JSON.STATUS: STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: FORGOT_PASSWORD.EMAIL_SENT_MESSAGE,
    }
    """
    (
        app,
        client,
        new_user,
        old_reset_token,
        csrf_token,
    ) = user_attempts_reset_password_one_hour_old

    forgot_password_response = client.post(
        url_for(ROUTES.SPLASH.FORGOT_PASSWORD_PAGE),
        data={
            FORGOT_PASSWORD.EMAIL: new_user[FORGOT_PASSWORD.EMAIL],
            FORGOT_PASSWORD.CSRF_TOKEN: csrf_token,
        },
    )

    current_time: datetime = utc_now()

    assert forgot_password_response.status_code == 200
    forgot_password_response_json = forgot_password_response.json
    assert forgot_password_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        forgot_password_response_json[STD_JSON.MESSAGE]
        == FORGOT_PASSWORD.EMAIL_SENT_MESSAGE
    )

    with app.app_context():
        user: Users = Users.query.filter(
            Users.email == new_user[FORGOT_PASSWORD.EMAIL].lower()
        ).first()
        new_forgot_password: Forgot_Passwords = Forgot_Passwords.query.filter(
            Forgot_Passwords.user_id == user.id
        ).first()
        assert new_forgot_password.reset_token != old_reset_token
        assert (
            current_time - new_forgot_password.initial_attempt
        ).total_seconds() <= 15
        assert (current_time - new_forgot_password.last_attempt).total_seconds() <= 15
        assert new_forgot_password.attempts == 1


def test_two_forgot_password_attempts_more_than_minute_apart_increments_attempts(
    user_attempts_reset_password,
):
    """
    GIVEN a user who previously forgot their password more than a minute ago
    WHEN the user accesses the Forgot Password feature again
    THEN ensure that a new token is not generated, the attempts are properly incremented, and the server
        responds with a 200 status code and properly formatted JSON

    JSON response as follows:
    {
        STD_JSON.STATUS: STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: FORGOT_PASSWORD.EMAIL_SENT_MESSAGE,
    }
    """
    app, client, new_user, reset_token, csrf_token = user_attempts_reset_password

    with app.app_context():
        forgot_password: Forgot_Passwords = Forgot_Passwords.query.filter(
            Forgot_Passwords.reset_token == reset_token
        ).first()
        forgot_password.last_attempt = utc_now() - timedelta(
            seconds=USER_CONSTANTS.WAIT_TO_RETRY_FORGOT_PASSWORD_MIN + 1
        )
        current_attempts = forgot_password.attempts
        db.session.commit()

    forgot_password_response = client.post(
        url_for(ROUTES.SPLASH.FORGOT_PASSWORD_PAGE),
        data={
            FORGOT_PASSWORD.EMAIL: new_user[FORGOT_PASSWORD.EMAIL],
            FORGOT_PASSWORD.CSRF_TOKEN: csrf_token,
        },
    )

    assert forgot_password_response.status_code == 200
    forgot_password_response_json = forgot_password_response.json
    assert forgot_password_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        forgot_password_response_json[STD_JSON.MESSAGE]
        == FORGOT_PASSWORD.EMAIL_SENT_MESSAGE
    )

    with app.app_context():
        incremented_forgot_password: Forgot_Passwords = Forgot_Passwords.query.filter(
            Forgot_Passwords.reset_token == reset_token
        ).first()
        assert incremented_forgot_password.attempts == current_attempts + 1
