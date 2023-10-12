from copy import deepcopy
from flask import url_for, request
from flask_login import current_user
from werkzeug.security import check_password_hash

from tests.models_for_test import valid_user_1
from tests.utils_for_test import get_csrf_token
from urls4irl.models import User
from urls4irl.utils import strings as U4I_STRINGS

STD_JSON = U4I_STRINGS.STD_JSON_RESPONSE
REGISTER_FORM = U4I_STRINGS.REGISTER_FORM
REGISTER_FAILURE = U4I_STRINGS.USER_FAILURE


def test_register_new_user(app, load_register_page):
    """
    GIVEN a new, unregistered user to the page
    WHEN they register to an empty database, and POST to "/register" correctly
    THEN ensure they are logged in and set to their home page
    """
    client, csrf_token_string = load_register_page

    new_user = deepcopy(valid_user_1)
    new_user[REGISTER_FORM.CSRF_TOKEN] = csrf_token_string

    # Ensure no user with this data exists in database
    with app.app_context():
        new_db_user = User.query.filter_by(
            username=new_user[REGISTER_FORM.USERNAME]
        ).first()

    assert new_db_user is None

    response = client.post(url_for("users.register_user"), data=new_user, follow_redirects=True)

    # Correctly sends URL to email validation modal
    assert response.status_code == 201
    assert (
        b'<h1 class="modal-title validate-email-text validate-email-title">Validate Your Email!</h1>'
        in response.data
    )

    # Test if user logged in
    assert current_user.username == new_user[REGISTER_FORM.USERNAME]
    assert current_user.password != new_user[REGISTER_FORM.PASSWORD]
    assert current_user.email == new_user[REGISTER_FORM.EMAIL]

    # Ensure user exists in database
    with app.app_context():
        new_db_user = User.query.filter_by(
            username=new_user[REGISTER_FORM.USERNAME]
        ).first()

    # Ensure user model after loading from database is logged in
    assert new_db_user.is_authenticated is True
    assert new_db_user.is_active is True

    # Test if user db data is same as input when registering
    assert new_db_user.username == new_user[REGISTER_FORM.USERNAME]
    assert new_db_user.password != new_user[REGISTER_FORM.PASSWORD]
    assert new_db_user.email == new_user[REGISTER_FORM.EMAIL]

    # Test if user db data is same as current user variable
    assert new_db_user.username == current_user.username
    assert new_db_user.password == current_user.password
    assert new_db_user.email == current_user.email
    assert new_db_user.id == int(current_user.get_id())


def test_register_duplicate_user(app, load_register_page, register_first_user):
    """
    GIVEN a user to the page
    WHEN they register with same credentials, and POST to "/register" correctly
    THEN ensure they are not logged in and not registered again

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: REGISTER_FAILURE.UNABLE_TO_REGISTER,
        STD_JSON.ERROR_CODE: Integer representing the failure code, 2 for invalid form inputs
        STD_JSON.ERRORS: Array containing objects for each field and their specific error. For example:
            [
                {
                    REGISTER_FORM.USERNAME: "That username is taken. Please choose another.",
                    REGISTER_FORM.EMAIL: "That email address is already in use."
                }
            ]
    }
    """
    client, csrf_token_string = load_register_page
    already_registered_user_data, _ = register_first_user

    already_registered_user_data[REGISTER_FORM.CSRF_TOKEN] = csrf_token_string

    # Ensure user already exists
    with app.app_context():
        new_db_user = User.query.filter_by(
            username=already_registered_user_data[REGISTER_FORM.USERNAME]
        ).first()

    assert new_db_user is not None

    # Ensure no one is logged in
    assert current_user.get_id() is None
    assert current_user.is_active is False

    response = client.post(
        url_for("users.register_user"), data=already_registered_user_data, follow_redirects=True
    )

    # Check that does not reroute
    assert response.status_code == 401
    assert request.path == url_for("users.register_user")
    assert len(response.history) == 0

    # Ensure json response from server is valid
    register_user_response_json = response.json
    assert register_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        register_user_response_json[STD_JSON.MESSAGE]
        == REGISTER_FAILURE.UNABLE_TO_REGISTER
    )
    assert int(register_user_response_json[STD_JSON.ERROR_CODE]) == 2
    assert (
        REGISTER_FAILURE.USERNAME_TAKEN
        in register_user_response_json[STD_JSON.ERRORS][REGISTER_FORM.USERNAME]
    )
    assert (
        REGISTER_FAILURE.EMAIL_TAKEN
        in register_user_response_json[STD_JSON.ERRORS][REGISTER_FORM.EMAIL]
    )


def test_register_modal_is_shown(app_with_server_name, client):
    """
    GIVEN a non-registered user visiting the splash page ("/")
    WHEN the user makes a request to "/register"
    THEN verify that the backends responds with a modal in the HTML
    """
    with client:
        with app_with_server_name.app_context():
            client.get(url_for("main.splash"))
            response = client.get(url_for("users.register_user"))
        assert (
            b'<form id="ModalForm" method="POST" class="login-register-form" action="" novalidate>'
            in response.data
        )

        # Ensure on register page
        assert (
            b'<input id="csrf_token" name="csrf_token" type="hidden" value='
            in response.data
        )
        assert (
            b'<input class="form-control login-register-form-group" id="username" maxlength="20" minlength="4" name="username" required type="text" value="">'
            in response.data
        )
        assert (
            b'<input class="form-control login-register-form-group" id="email" name="email" required type="text" value="">'
            in response.data
        )
        assert (
            b'<input class="form-control login-register-form-group" id="confirm_email" name="confirm_email" required type="text" value="">'
            in response.data
        )
        assert (
            b'<input class="form-control login-register-form-group" id="password" maxlength="64" minlength="12" name="password" required type="password" value="">'
            in response.data
        )
        assert (
            b'<input class="form-control login-register-form-group" id="confirm_password" name="confirm_password" required type="password" value="">'
            in response.data
        )
        assert request.path == url_for("users.register_user")


def test_register_modal_logs_user_in(app_with_server_name, client):
    """
    GIVEN a non-logged in user visiting the splash page ("/")
    WHEN the user makes a GET request to "/register", and then a POST request with the applicable form info
    THEN verify that the backends responds with URL to "/home" on response to the post, and logs the user in
    """
    with client:
        with app_with_server_name.app_context():
            client.get(url_for("main.splash"))
            response = client.get(url_for("users.register_user"))
        csrf_token = get_csrf_token(response.data)

        new_user = deepcopy(valid_user_1)
        new_user[REGISTER_FORM.CSRF_TOKEN] = csrf_token

        response = client.post(url_for("users.register_user"), data=new_user)

        assert response.status_code == 201
        assert (
            b'<h1 class="modal-title validate-email-text validate-email-title">Validate Your Email!</h1>'
            in response.data
        )

        assert current_user.username == new_user[REGISTER_FORM.USERNAME]
        assert check_password_hash(
            current_user.password, new_user[REGISTER_FORM.PASSWORD]
        )
        assert current_user.email == new_user[REGISTER_FORM.EMAIL]


def test_register_user_missing_csrf(app, load_register_page):
    """
    GIVEN a new, unregistered user to the page
    WHEN they register to an empty database, and POST to "/register" without a CSRF token
    THEN ensure server responds with 400 and proper error message
    """
    client, _ = load_register_page

    # Ensure no user with this data exists in database
    with app.app_context():
        new_db_user = User.query.filter_by(
            username=valid_user_1[REGISTER_FORM.USERNAME]
        ).first()

    assert new_db_user is None

    response = client.post(url_for("users.register_user"), data={
        REGISTER_FORM.USERNAME: valid_user_1[REGISTER_FORM.USERNAME],
        REGISTER_FORM.EMAIL: valid_user_1[REGISTER_FORM.EMAIL],
        REGISTER_FORM.CONFIRM_EMAIL: valid_user_1[REGISTER_FORM.CONFIRM_EMAIL],
        REGISTER_FORM.PASSWORD: valid_user_1[REGISTER_FORM.PASSWORD],
        REGISTER_FORM.CONFIRM_PASSWORD: valid_user_1[REGISTER_FORM.CONFIRM_PASSWORD],
        }, 
        follow_redirects=True)

    # Correctly sends URL to email validation modal
    assert response.status_code == 400
    assert b"<p>The CSRF token is missing.</p>" in response.data

    # Ensure no one is logged in
    assert current_user.get_id() is None
    assert current_user.is_active is False

    # Ensure no user with this data exists in database
    with app.app_context():
        new_db_user = User.query.filter_by(
            username=valid_user_1[REGISTER_FORM.USERNAME]
        ).first()

    assert new_db_user is None
