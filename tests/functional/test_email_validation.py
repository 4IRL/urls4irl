from datetime import datetime
from flask import url_for
from flask_login import current_user

from tests.models_for_test import valid_user_1
from tests.utils_for_test import get_csrf_token
from urls4irl import db
from urls4irl.models import URLS, Utub_Urls, Utub, Url_Tags, User
from urls4irl.utils.constants import EmailConstants
from urls4irl.utils import strings as U4I_STRINGS

STD_JSON = U4I_STRINGS.STD_JSON_RESPONSE
REGISTER_FORM = U4I_STRINGS.REGISTER_FORM
USER_FAILURE = U4I_STRINGS.USER_FAILURE
EMAILS = U4I_STRINGS.EMAILS
EMAILS_FAILURE = U4I_STRINGS.EMAILS_FAILURE
VALIDATE_EMAIL_MODAL_TITLE = '<h1 class="modal-title validate-email-text validate-email-title">Validate Your Email!</h1>'

def test_registered_user_is_not_email_validated(app, load_register_page):
    """
    GIVEN a user trying to register
    WHEN they submit an registration form
    THEN ensure they don't have a validated email
    """
    client, csrf_token = load_register_page

    valid_user_1[REGISTER_FORM.CSRF_TOKEN] = csrf_token

    response = client.post("/register", data=valid_user_1, follow_redirects=True)

    # Assert user gets shown email validation modal
    assert response.status_code == 201
    assert VALIDATE_EMAIL_MODAL_TITLE.encode() in response.data

    with app.app_context():
        registered_user: User = User.query.filter(User.username == valid_user_1[REGISTER_FORM.USERNAME]).first_or_404()
        assert not registered_user.email_confirm.is_validated


def test_registered_not_email_validated_user_access_splash_page(load_register_page):
    """
    GIVEN a registered user (but not logged in user) without a validated email, after just registering
    WHEN they try to access the splash page
    THEN ensure they can, but the email validation modal pops up
    """
    client, csrf_token_string = load_register_page

    valid_user_1[REGISTER_FORM.CSRF_TOKEN] = csrf_token_string
    response = client.post("/register", data=valid_user_1, follow_redirects=True)

    # Correctly sends URL to email validation modal
    assert response.status_code == 201
    assert VALIDATE_EMAIL_MODAL_TITLE.encode() in response.data

    response = client.get("/")
    assert response.status_code == 200
    assert f'{EMAILS.EMAIL_VALIDATION_MODAL_CALL}'.encode() in response.data


def test_registered_not_email_validated_user_access_home_page(load_register_page):
    """
    GIVEN a registered user (but not logged in user) without a validated email, after just registering
    WHEN they try to access the validated user's home page
    THEN ensure they can't, and redirects them
    """
    client, csrf_token_string = load_register_page

    valid_user_1[REGISTER_FORM.CSRF_TOKEN] = csrf_token_string
    response = client.post("/register", data=valid_user_1, follow_redirects=True)

    # Correctly sends URL to email validation modal
    assert response.status_code == 201
    assert VALIDATE_EMAIL_MODAL_TITLE.encode() in response.data

    response = client.get("/home", follow_redirects=True)
    assert response.history[0].status_code == 302
    assert response.history[0].location == url_for("main.splash")
    assert response.status_code == 200
    assert f'{EMAILS.EMAIL_VALIDATION_MODAL_CALL}'.encode() in response.data


def test_registered_not_email_validated_user_access_register_login(load_register_page):
    """
    GIVEN a registered user (but not logged in user) without a validated email, after just registering
    WHEN they try to access the login or register pages
    THEN ensure they are redirected to the email validation modal
    """
    client, csrf_token_string = load_register_page

    valid_user_1[REGISTER_FORM.CSRF_TOKEN] = csrf_token_string
    response = client.post("/register", data=valid_user_1, follow_redirects=True)

    # Correctly sends URL to email validation modal
    assert response.status_code == 201
    assert VALIDATE_EMAIL_MODAL_TITLE.encode() in response.data

    urls_to_check = ("/register", "/login")

    for url in urls_to_check:
        response = client.get(url, follow_redirects=True)
        assert response.history[0].status_code == 302
        assert response.history[0].location == url_for("users.confirm_email_after_register")
        assert response.status_code == 200
        assert VALIDATE_EMAIL_MODAL_TITLE.encode() in response.data


def test_registered_not_email_validated_tries_registering_again(register_first_user_without_email_validation, load_register_page):
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
    response = client.post("/register", data=valid_user_1)

    # Ensure json response from server is valid
    register_user_response_json = response.json
    assert register_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert register_user_response_json[STD_JSON.MESSAGE] == USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED
    assert int(register_user_response_json[STD_JSON.ERROR_CODE]) == 1

    assert response.status_code == 401


def test_registered_not_email_validated_tries_logging_in(register_first_user_without_email_validation, load_login_page):
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
    response = client.post("/login", data=valid_user_1)

    # Ensure json response from server is valid
    login_user_response_json = response.json
    assert login_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert login_user_response_json[STD_JSON.MESSAGE] == USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED
    assert int(login_user_response_json[STD_JSON.ERROR_CODE]) == 1

    assert response.status_code == 401


def test_valid_token_generated_on_user_register(app, register_first_user_without_email_validation):
    """
    GIVEN a registered user with an unvalidated email
    WHEN they registered
    THEN ensure a token was correctly created referencing the user
    """
    registered_user, _ = register_first_user_without_email_validation
    
    with app.app_context():
        registered_user: User = User.query.filter(User.email == registered_user[REGISTER_FORM.EMAIL]).first()
        user_token = registered_user.email_confirm.confirm_url
        assert User.verify_email_validation_token(user_token) == (registered_user, False)


def test_token_validates_user(app, load_register_page):
    """
    GIVEN a user trying to register via the register page
    WHEN they register and click on the link received in their email
    THEN ensure their email is validated and they are logged in and token to the home page
    """
    client, csrf_token = load_register_page

    valid_user_1[REGISTER_FORM.CSRF_TOKEN] = csrf_token

    client.post("/register", data=valid_user_1, follow_redirects=True)

    with app.app_context():
        user: User = User.query.filter(User.email == valid_user_1[REGISTER_FORM.EMAIL]).first()
        user_token = user.email_confirm.confirm_url
        assert not user.is_email_authenticated() and not user.email_confirm.is_validated

    response = client.get(url_for("users.validate_email", token=user_token), follow_redirects=True)

    assert len(response.history) == 1
    assert response.history[0].status_code == 302
    assert response.history[0].location == url_for("main.home")
    assert response.status_code == 200

    # Ensure user logged in
    assert current_user.get_id() == user.get_id()
    assert current_user == user

    with app.app_context():
        user: User = User.query.filter(User.email == valid_user_1[REGISTER_FORM.EMAIL]).first()
        assert user.is_email_authenticated() and user.email_confirm.is_validated


def test_token_can_expire(app, register_first_user_without_email_validation):
    """
    GIVEN a user trying to validate their email
    WHEN they click on the validation link in their email after the token has expired
    THEN ensure that the verification will not be successful
    """
    registered_user, _ = register_first_user_without_email_validation

    with app.app_context():
        user: User = User.query.filter(User.email == registered_user[REGISTER_FORM.EMAIL]).first()
        quick_expiring_token = user.get_email_validation_token(expires_in=0)
        
        assert User.verify_email_validation_token(quick_expiring_token) == (None, True)


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

    register_response = client.post("/register", data=valid_user_1, follow_redirects=True)
    new_csrf_token = get_csrf_token(register_response.data)
    send_email_response = client.post("/send_validation_email", data={REGISTER_FORM.CSRF_TOKEN: csrf_token})

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

    client.post("/register", data=valid_user_1, follow_redirects=True)
    client.post("/send_validation_email", data={REGISTER_FORM.CSRF_TOKEN: csrf_token})

    send_second_email_response = client.post("/send_validation_email", data={REGISTER_FORM.CSRF_TOKEN: csrf_token})
    second_email_send_json = send_second_email_response.json

    assert send_second_email_response.status_code == 429
    assert second_email_send_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert int(second_email_send_json[STD_JSON.ERROR_CODE]) == 2
    assert second_email_send_json[STD_JSON.MESSAGE] == str(EmailConstants.MAX_EMAIL_ATTEMPTS_IN_HOUR - 1) + EMAILS_FAILURE.TOO_MANY_ATTEMPTS


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

    client.post("/register", data=valid_user_1, follow_redirects=True)

    with app.app_context():
        user: User = User.query.filter(User.email == valid_user_1[REGISTER_FORM.EMAIL]).first()
        user.email_confirm.attempts = EmailConstants.MAX_EMAIL_ATTEMPTS_IN_HOUR + 1
        user.email_confirm.last_attempt = datetime.utcnow()
        db.session.commit()

    email_response = client.post("/send_validation_email", data={REGISTER_FORM.CSRF_TOKEN: csrf_token})
    email_response_json = email_response.json

    assert email_response.status_code == 429
    assert email_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert int(email_response_json[STD_JSON.ERROR_CODE]) == 1
    assert email_response_json[STD_JSON.MESSAGE] == EMAILS_FAILURE.TOO_MANY_ATTEMPTS_MAX
