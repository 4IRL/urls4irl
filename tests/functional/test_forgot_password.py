from datetime import datetime
from flask import url_for

from tests.models_for_test import valid_user_1
from urls4irl.models import User, PasswordReset
from urls4irl.utils import strings as U4I_STRINGS

STD_JSON = U4I_STRINGS.STD_JSON_RESPONSE
REGISTER_FORM = U4I_STRINGS.REGISTER_FORM
USER_FAILURE = U4I_STRINGS.USER_FAILURE
RESET_PASSWORD = U4I_STRINGS.RESET_PASSWORD
FORGOT_PASSWORD_MODAL_TITLE = '<h4 class="modal-title">Forgot your password?</h4>'

# TODO: User can't access if already logged in + email validated
def test_user_logged_in_email_validated_cannot_access_forgot_password(
        register_first_user,
        login_first_user_without_register
    ):
    """
    GIVEN a user who is already logged in and email validated
    WHEN they try to make a GET to the /forgot_password URL
    THEN ensure they cannot access - only access is from non-logged in users
        who are email validated. User should get redirected to their home page
    """
    client, _, _, _ = login_first_user_without_register

    forgot_password_response = client.get(url_for("users.forgot_password"), follow_redirects=True)
    
    # Only one redirect to user home page
    assert len(forgot_password_response.history) == 1
    redirect_response = forgot_password_response.history[0]

    assert redirect_response.location == url_for("main.home")
    assert redirect_response.status_code == 302


# TODO: User gets redirected to email validation if just registered + not email validated
def test_user_registered_not_email_validated_cannot_access_forgot_password(
        load_register_page
    ):
    """
    GIVEN a user who just registered and the email confirmation modal has popped up
    WHEN they try to make a GET to the /forgot_password URL
    THEN ensure they cannot access - only access is from non-logged in users
        who are email validated. User should get redirected to the email confirmation page
    """
    client, csrf_token = load_register_page

    register_response = client.post("/register", data = {
        REGISTER_FORM.USERNAME: valid_user_1[REGISTER_FORM.USERNAME],
        REGISTER_FORM.EMAIL: valid_user_1[REGISTER_FORM.EMAIL],
        REGISTER_FORM.CONFIRM_EMAIL: valid_user_1[REGISTER_FORM.EMAIL],
        REGISTER_FORM.PASSWORD: valid_user_1[REGISTER_FORM.PASSWORD],
        REGISTER_FORM.CONFIRM_PASSWORD: valid_user_1[REGISTER_FORM.PASSWORD],
        REGISTER_FORM.CSRF_TOKEN: csrf_token
    })

    assert register_response.status_code == 201

    forgot_password_response = client.get(url_for("users.forgot_password"), follow_redirects=True)
    
    # Only one redirect to user home page
    assert len(forgot_password_response.history) == 1
    redirect_response = forgot_password_response.history[0]

    assert redirect_response.location == url_for("users.confirm_email_after_register")
    assert redirect_response.status_code == 302

    
# TODO: Test get on route gets the form sent to the user
def test_valid_user_requests_forgot_password_form(
        register_first_user,
        load_login_page
        ):
    """
    GIVEN a user who is not logged in but is email validated and registered
    WHEN they try to make a GET to the /forgot_password URL
    THEN server successfully sends the user the forgot password form and responds with
        200 status code
    """
    client, csrf_token = load_login_page

    forgot_password_response = client.get(url_for("users.forgot_password"))

    assert forgot_password_response.status_code == 200
    assert FORGOT_PASSWORD_MODAL_TITLE.encode() in forgot_password_response.data


# TODO: Test post without csrf token fails
def test_valid_user_posts_forgot_password_form_without_csrf(
        register_first_user,
        load_login_page
        ):
    """
    GIVEN a user who is not logged in but is email validated and registered
    WHEN they try to make a POST to the /forgot_password URL with a missing CSRF token
    THEN server responds with a 400 and proper error message    
    """
    new_user, _ = register_first_user
    client, csrf_token = load_login_page

    _ = client.get(url_for("users.forgot_password"))

    forgot_password_post_response = client.post(url_for("users.forgot_password"), data={
        RESET_PASSWORD.EMAIL: new_user[RESET_PASSWORD.EMAIL] 
    })

    # Assert invalid response code
    assert forgot_password_post_response.status_code == 400
    assert b"<p>The CSRF token is missing.</p>" in forgot_password_post_response.data


# TODO: Test post with ill-formatted email fails
def test_forgot_password_with_invalid_email_fails(
        load_login_page
):
    """
    GIVEN a user who accesses the forgot password form from the login page
    WHEN the user inputs an ill-formatted email, such as "Cat"
    THEN server responds with 401 and JSON containing form errors


    JSON response as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.ERROR_CODE: 1,
        STD_JSON.MESSAGE: USER_FAILURE.INVALID_EMAIL,
        STD_JSON.ERRORS: {
            STD_JSON.EMAIL: ["Invalid email address.",]
        }
    }
    """
    client, csrf_token = load_login_page
    improper_email = "Cat"

    response = client.post(url_for("users.forgot_password"), data={
        RESET_PASSWORD.EMAIL: improper_email,
        RESET_PASSWORD.CSRF_TOKEN: csrf_token
    })

    assert response.status_code == 401
    response_json = response.json

    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert int(response_json[STD_JSON.ERROR_CODE]) == 1
    assert response_json[STD_JSON.MESSAGE] == USER_FAILURE.INVALID_EMAIL
    assert "Invalid email address." in response_json[STD_JSON.ERRORS][RESET_PASSWORD.EMAIL][-1] 


# TODO: Test post with email that isn't in database still shows successful
def test_forgot_password_with_email_not_in_database(
        app,
        load_login_page
):
    """
    GIVEN a user who accesses the forgot password form from the login page
    WHEN the user inputs an email that isn't in the database
    THEN server still shows success with a 200 response status code, with proper JSON response
        PasswordReset object is not created.

    JSON response as follows:
    {
        STD_JSON.STATUS: STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: RESET_PASSWORD.EMAIL_SENT_MESSAGE,
    }
    """
    client, csrf_token = load_login_page
    nonregistered_user = valid_user_1

    with app.app_context():
        user_with_email = User.query.filter(User.email == nonregistered_user[RESET_PASSWORD.EMAIL]).all()
        assert len(user_with_email) == 0
        num_of_password_reset_objects = len(PasswordReset.query.all())

    response = client.post(url_for("users.forgot_password"), data={
        RESET_PASSWORD.EMAIL: nonregistered_user[RESET_PASSWORD.EMAIL],
        RESET_PASSWORD.CSRF_TOKEN: csrf_token
    })

    assert response.status_code == 200

    response_json = response.json
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == RESET_PASSWORD.EMAIL_SENT_MESSAGE 

    with app.app_context():
        assert num_of_password_reset_objects == len(PasswordReset.query.all())


# TODO: Test post with validated email that is in database shows successful and PasswordReset object created
def test_forgot_password_with_validated_email(
        app,
        register_first_user,
        load_login_page
):
    """
    GIVEN a user who accesses the forgot password form from the login page
    WHEN the user inputs an email that has been validated
    THEN server still shows success with a 200 response status code, with proper JSON response
        PasswordReset object is created to keep track of password resets for this user.

    JSON response as follows:
    {
        STD_JSON.STATUS: STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: RESET_PASSWORD.EMAIL_SENT_MESSAGE,
    }
    """
    new_user, _ = register_first_user
    client, csrf_token = load_login_page

    with app.app_context():
        assert len(PasswordReset.query.all()) == 0
        all_users_with_email = User.query.filter(User.email == new_user[RESET_PASSWORD.EMAIL]).all()
        assert len(all_users_with_email) == 1
        user = all_users_with_email[-1]
        user_id = user.id

    response = client.post(url_for("users.forgot_password"), data={
        RESET_PASSWORD.EMAIL: new_user[RESET_PASSWORD.EMAIL],
        RESET_PASSWORD.CSRF_TOKEN: csrf_token
    })

    assert response.status_code == 200

    response_json = response.json
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == RESET_PASSWORD.EMAIL_SENT_MESSAGE 

    with app.app_context():
        assert len(PasswordReset.query.filter(PasswordReset.user_id == user_id).all()) == 1
        

# TODO: Test post with email that isn't validated shows successful and no PasswordReset object created
def test_forgot_password_with_non_validated_email(
        app,
        register_first_user_without_email_validation,
        load_login_page
):
    """
    GIVEN a user who accesses the forgot password form from the login page
    WHEN the user inputs an email that has not been validated
    THEN server still shows success with a 200 response status code, with proper JSON response
        PasswordReset object is not created.

    JSON response as follows:
    {
        STD_JSON.STATUS: STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: RESET_PASSWORD.EMAIL_SENT_MESSAGE,
    }
    """
    new_user, _ = register_first_user_without_email_validation
    client, csrf_token = load_login_page

    with app.app_context():
        assert len(PasswordReset.query.all()) == 0
        all_users_with_email = User.query.filter(User.email == new_user[RESET_PASSWORD.EMAIL]).all()
        assert len(all_users_with_email) == 1
        user = all_users_with_email[-1]
        user_id = user.id

    response = client.post(url_for("users.forgot_password"), data={
        RESET_PASSWORD.EMAIL: new_user[RESET_PASSWORD.EMAIL],
        RESET_PASSWORD.CSRF_TOKEN: csrf_token
    })

    assert response.status_code == 200

    response_json = response.json
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == RESET_PASSWORD.EMAIL_SENT_MESSAGE 

    with app.app_context():
        assert len(PasswordReset.query.filter(PasswordReset.user_id == user_id).all()) == 0


# TODO: Test user can't send two within one minute (check attempts and last attempts)
def test_forgot_password_rate_limits_correctly(
        app,
        register_first_user,
        load_login_page
):
    """
    GIVEN a user who accesses the forgot password form from the login page
    WHEN the user inputs an email that has been validated, and POSTs the form twice in one minute
    THEN server still shows success with a 200 response status code, with proper JSON response
        PasswordReset object is created, and is used to rate limit the user.

    JSON response as follows:
    {
        STD_JSON.STATUS: STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: RESET_PASSWORD.EMAIL_SENT_MESSAGE,
    }
    """
    new_user, _ = register_first_user
    client, csrf_token = load_login_page

    with app.app_context():
        assert len(PasswordReset.query.all()) == 0
        all_users_with_email = User.query.filter(User.email == new_user[RESET_PASSWORD.EMAIL]).all()
        assert len(all_users_with_email) == 1
        user = all_users_with_email[-1]
        user_id = user.id

    initial_send_time = datetime.utcnow()
    first_response = client.post(url_for("users.forgot_password"), data={
        RESET_PASSWORD.EMAIL: new_user[RESET_PASSWORD.EMAIL],
        RESET_PASSWORD.CSRF_TOKEN: csrf_token
    })

    second_send_time = datetime.utcnow()
    second_response = client.post(url_for("users.forgot_password"), data={
        RESET_PASSWORD.EMAIL: new_user[RESET_PASSWORD.EMAIL],
        RESET_PASSWORD.CSRF_TOKEN: csrf_token
    })

    for response in (first_response, second_response,):
        assert response.status_code == 200

        response_json = response.json
        assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
        assert response_json[STD_JSON.MESSAGE] == RESET_PASSWORD.EMAIL_SENT_MESSAGE 

    with app.app_context():
        password_reset_objs = PasswordReset.query.all()
        assert len(password_reset_objs) == 1
        new_password_reset: PasswordReset = password_reset_objs[-1]
        assert new_password_reset.user_id == user_id

        assert new_password_reset.attempts == 1
        last_attempt_time = new_password_reset.last_attempt
        assert last_attempt_time < second_send_time and last_attempt_time >= initial_send_time


# TODO: Check token generated correctly after valid user requests password reset
def test_forgot_password_generates_token_correctly(
        app,
        register_first_user,
        load_login_page
):
    """
    GIVEN a user who accesses the forgot password form from the login page
    WHEN the user inputs an email that has been validated, and POSTs the form twice in one minute
    THEN server still shows success with a 200 response status code, with proper JSON response
        PasswordReset object is created, and is used to rate limit the user.

    JSON response as follows:
    {
        STD_JSON.STATUS: STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: RESET_PASSWORD.EMAIL_SENT_MESSAGE,
    }
    """
    new_user, _ = register_first_user
    client, csrf_token = load_login_page

    with app.app_context():
        assert len(PasswordReset.query.all()) == 0
        all_users_with_email = User.query.filter(User.email == new_user[RESET_PASSWORD.EMAIL]).all()
        assert len(all_users_with_email) == 1
        user = all_users_with_email[-1]
        user_id = user.id

    response = client.post(url_for("users.forgot_password"), data={
        RESET_PASSWORD.EMAIL: valid_user_1[RESET_PASSWORD.EMAIL],
        RESET_PASSWORD.CSRF_TOKEN: csrf_token
    })

    with app.app_context():
        password_reset_objs = PasswordReset.query.all()
        assert len(password_reset_objs) == 1
        new_password_reset: PasswordReset = password_reset_objs[-1]
        assert new_password_reset.user_id == user_id

        registered_user = User.query.filter(User.email == new_user[RESET_PASSWORD.EMAIL]).first()

        token = new_password_reset.reset_token
        assert User.verify_token(token, RESET_PASSWORD.RESET_PASSWORD_KEY) == (
            registered_user,
            False
        )
