from copy import deepcopy
from flask import url_for, request
from flask_login import current_user
from werkzeug.security import check_password_hash
from pytest import raises

from tests.models_for_test import invalid_user_1, valid_user_1
from tests.utils_for_test import get_csrf_token
from src.models import User
from src.utils.all_routes import ROUTES
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.splash_form_strs import LOGIN_FORM
from src.utils.strings.user_strs import USER_FAILURE


def test_login_registered_and_logged_in_user(login_first_user_with_register):
    """
    GIVEN a registered and logged in user
    WHEN "/login" is POST'd with CSRF token
    THEN ensure the user is redirected to the home page since they are already logged in
    """
    client, csrf_token_str, user, app = login_first_user_with_register

    new_user = deepcopy(valid_user_1)
    new_user[LOGIN_FORM.CSRF_TOKEN] = csrf_token_str

    response = client.post(
        url_for(ROUTES.SPLASH.LOGIN), data=new_user, follow_redirects=True
    )

    # Correctly responds with URL to home page
    assert len(response.history) == 1
    redirect = response.history[-1]
    assert redirect.location == url_for(ROUTES.UTUBS.HOME)
    assert redirect.status_code == 302
    assert response.status_code == 200

    # Test if user logged in
    assert current_user.username == new_user[LOGIN_FORM.USERNAME]
    assert check_password_hash(current_user.password, new_user[LOGIN_FORM.PASSWORD])
    assert current_user.email == new_user[LOGIN_FORM.EMAIL].lower()

    # Ensure user id's match with  database
    with app.app_context():
        registered_db_user = User.query.filter_by(
            username=new_user[LOGIN_FORM.USERNAME]
        ).first()

    assert registered_db_user.id == int(current_user.get_id())


def test_login_unregistered_user(load_login_page):
    """
    GIVEN an unregistered user
    WHEN "/login" is POST'd with filled in correctly with form data
    THEN ensure login does not occur, and correct form error is given in the JSON response

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: USER_FAILURE.UNABLE_TO_LOGIN,
        STD_JSON.ERROR_CODE: Integer representing the failure code, 2 for invalid form inputs
        STD_JSON.ERRORS: Array containing objects for each field and their specific error. For example:
            [
                {
                    LOGIN_FORM.USERNAME: "That user does not exist. Note this is case sensitive."
                }
            ]
    }
    """
    client, csrf_token_str = load_login_page

    invalid_user = deepcopy(invalid_user_1)
    invalid_user[LOGIN_FORM.CSRF_TOKEN] = csrf_token_str

    response = client.post(
        url_for(ROUTES.SPLASH.LOGIN),
        data={
            LOGIN_FORM.CSRF_TOKEN: invalid_user[LOGIN_FORM.CSRF_TOKEN],
            LOGIN_FORM.USERNAME: invalid_user[LOGIN_FORM.USERNAME],
            LOGIN_FORM.PASSWORD: invalid_user[LOGIN_FORM.PASSWORD],
        },
    )

    # Ensure json response from server is valid
    login_user_response_json = response.json
    assert login_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert login_user_response_json[STD_JSON.MESSAGE] == USER_FAILURE.UNABLE_TO_LOGIN
    assert int(login_user_response_json[STD_JSON.ERROR_CODE]) == 2
    assert (
        USER_FAILURE.USER_NOT_EXIST
        in login_user_response_json[STD_JSON.ERRORS][LOGIN_FORM.USERNAME]
    )

    assert response.status_code == 401

    # Ensure no one is logged in
    assert current_user.get_id() is None
    assert current_user.is_active is False


def test_login_user_wrong_password(register_first_user, load_login_page):
    """
    GIVEN a registered user
    WHEN "/login" is POST'd with filled in correctly with form data, and an invalid password for this user
    THEN ensure login does not occur, and correct form error is given in the JSON resonse

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: USER_FAILURE.UNABLE_TO_LOGIN,
        STD_JSON.ERROR_CODE: Integer representing the failure code, 2 for invalid form inputs
        STD_JSON.ERRORS: Array containing objects for each field and their specific error. For example:
            [
                {
                    LOGIN_FORM.PASSWORD: "Invalid password."
                }
            ]
    }
    """
    client, csrf_token_str = load_login_page

    new_user = deepcopy(valid_user_1)
    new_user[LOGIN_FORM.CSRF_TOKEN] = csrf_token_str

    response = client.post(
        url_for(ROUTES.SPLASH.LOGIN),
        data={
            LOGIN_FORM.CSRF_TOKEN: new_user[LOGIN_FORM.CSRF_TOKEN],
            LOGIN_FORM.USERNAME: new_user[LOGIN_FORM.USERNAME],
            LOGIN_FORM.PASSWORD: "A",
        },
    )

    # Ensure json response from server is valid
    login_user_response_json = response.json
    assert login_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert login_user_response_json[STD_JSON.MESSAGE] == USER_FAILURE.UNABLE_TO_LOGIN
    assert int(login_user_response_json[STD_JSON.ERROR_CODE]) == 2
    assert (
        USER_FAILURE.INVALID_PASSWORD
        in login_user_response_json[STD_JSON.ERRORS][LOGIN_FORM.PASSWORD]
    )

    assert response.status_code == 401

    # Ensure no one is logged in
    assert current_user.get_id() is None
    assert current_user.is_active is False


def test_login_user_missing_csrf(register_first_user, load_login_page):
    """
    GIVEN a registered user
    WHEN "/login" is POST'd with filled in correctly with form data but a missing CSRF token
    THEN ensure login does not occur, and 400 status code is given with proper error message
    """
    client, _ = load_login_page

    response = client.post(
        url_for(ROUTES.SPLASH.LOGIN),
        data={
            LOGIN_FORM.USERNAME: valid_user_1[LOGIN_FORM.USERNAME],
            LOGIN_FORM.PASSWORD: "A",
        },
    )

    # Ensure json response from server is valid
    assert response.status_code == 400
    assert b"<p>The CSRF token is missing.</p>" in response.data

    # Ensure no one is logged in
    assert current_user.get_id() is None
    assert current_user.is_active is False


def test_already_logged_in_user_to_splash_page(login_first_user_with_register):
    """
    GIVEN a registered and logged in user
    WHEN "/" is GET after user is already logged on
    THEN ensure redirection occurs and user is brought to their home page
        - Note: One redirects, from "/" -> "/home"
    """
    client, _, logged_in_user, _ = login_first_user_with_register

    # Ensure redirect on home page access
    response = client.get(url_for(ROUTES.SPLASH.SPLASH_PAGE), follow_redirects=True)

    # Correctly redirects first to login page
    # Since already logged in, redirects to home page
    assert len(response.history) == 1
    assert response.history[0].status_code == 302
    assert response.history[0].request.path == url_for(ROUTES.SPLASH.SPLASH_PAGE)

    # Ensure lands on user's home page
    assert response.status_code == 200
    assert response.request.path == url_for(ROUTES.UTUBS.HOME)

    # Test if user logged in
    assert current_user.username == logged_in_user.username
    assert current_user.password == logged_in_user.password
    assert current_user.email == logged_in_user.email.lower()
    assert int(current_user.get_id()) == logged_in_user.id


def test_already_logged_in_user_to_login_page(login_first_user_with_register):
    """
    GIVEN a registered and logged in user
    WHEN "/login" is GET after user is already logged on
    THEN ensure redirection occurs and user is brought to their home page
        - Note: Redirects are "/login" -> "/home"
    """
    client, _, logged_in_user, _ = login_first_user_with_register

    # Ensure redirect on home page access
    response = client.get(url_for(ROUTES.SPLASH.LOGIN), follow_redirects=True)

    # Correctly redirects first to login page
    # Since already logged in, redirects to home page
    assert len(response.history) == 1
    assert response.history[0].status_code == 302
    assert response.history[0].request.path == url_for(ROUTES.SPLASH.LOGIN)

    # Ensure lands on user's home page
    assert response.status_code == 200
    assert response.request.path == url_for(ROUTES.UTUBS.HOME)

    # Test if user logged in
    assert current_user.username == logged_in_user.username
    assert current_user.password == logged_in_user.password
    assert current_user.email == logged_in_user.email.lower()
    assert int(current_user.get_id()) == logged_in_user.id


def test_already_logged_in_user_to_register_page(login_first_user_with_register):
    """
    GIVEN a registered and logged in user
    WHEN "/register" is GET after user is already logged on
    THEN ensure redirection occurs and user is brought to their home page
        - Note: Redirects are "/register" -> "/home"
    """
    client, _, logged_in_user, _ = login_first_user_with_register

    # Ensure redirect on home page access
    response = client.get(url_for(ROUTES.SPLASH.REGISTER), follow_redirects=True)

    # Correctly redirects first to login page
    # Since already logged in, redirects to home page
    assert len(response.history) == 1
    assert response.history[0].status_code == 302
    assert response.history[0].request.path == url_for(ROUTES.SPLASH.REGISTER)

    # Ensure lands on user's home page
    assert response.status_code == 200
    assert response.request.path == url_for(ROUTES.UTUBS.HOME)

    # Test if user logged in
    assert current_user.username == logged_in_user.username
    assert current_user.password == logged_in_user.password
    assert current_user.email == logged_in_user.email.lower()
    assert int(current_user.get_id()) == logged_in_user.id


def test_already_logged_in_user_to_home_page(login_first_user_with_register):
    """
    GIVEN a registered and logged in user
    WHEN "/home" is GET after user is already logged on
    THEN ensure 200 and user is brought to their home page
    """
    client, _, logged_in_user, _ = login_first_user_with_register

    # Ensure redirect on home page access
    response = client.get(url_for(ROUTES.UTUBS.HOME), follow_redirects=True)

    assert len(response.history) == 0
    assert response.status_code == 200
    assert request.path == url_for(ROUTES.UTUBS.HOME)

    # Test if user logged in
    assert current_user.username == logged_in_user.username
    assert current_user.password == logged_in_user.password
    assert current_user.email == logged_in_user.email.lower()
    assert int(current_user.get_id()) == logged_in_user.id

    assert bytes(f"Logged in as {current_user.username}", "utf-8") in response.data


def test_user_can_logout_after_login(login_first_user_with_register):
    """
    GIVEN a registered and logged in user
    WHEN "/logout" is GET after user is already logged on
    THEN ensure 200, user is brought to splash page, user no longer logged in
    """
    client, _, logged_in_user, _ = login_first_user_with_register

    # Ensure logout is successful
    response = client.get(url_for("users.logout"), follow_redirects=True)

    assert len(response.history) == 1
    assert response.history[0].status_code == 302
    assert response.history[0].request.path == url_for("users.logout")

    # Ensure lands on splash page
    assert response.status_code == 200
    assert response.request.path == url_for(ROUTES.SPLASH.SPLASH_PAGE)

    # Test if user logged in
    with raises(AttributeError):
        assert current_user.username != logged_in_user.username
        assert current_user.password != logged_in_user.password
        assert current_user.email != logged_in_user.email.lower()

    # Ensure no one is logged in
    assert current_user.get_id() is None
    assert current_user.is_active is False


def test_user_can_login_logout_login(login_first_user_with_register):
    """
    GIVEN a registered and logged in user
    WHEN they logout via GET "/logout"
    THEN ensure they can login in again successfully
    """
    client, _, logged_in_user, _ = login_first_user_with_register

    # Ensure logout is successful
    response = client.get(url_for("users.logout"), follow_redirects=True)

    # Ensure lands on splash page
    assert response.status_code == 200
    assert response.request.path == url_for(ROUTES.SPLASH.SPLASH_PAGE)

    response = client.get(url_for(ROUTES.SPLASH.LOGIN))

    # Ensure on login page
    assert (
        b'<input id="csrf_token" name="csrf_token" type="hidden" value='
        in response.data
    )
    assert (
        b'<input class="form-control login-register-form-group" id="username" name="username" required type="text" value="">'
        in response.data
    )
    assert (
        b'<input class="form-control login-register-form-group" id="password" name="password" required type="password" value="">'
        in response.data
    )
    assert response.request.path == url_for(ROUTES.SPLASH.LOGIN)

    # Grab csrf token from login page
    valid_user_1[LOGIN_FORM.CSRF_TOKEN] = get_csrf_token(response.data)

    # Post data to login page
    response = client.post(
        url_for(ROUTES.SPLASH.LOGIN),
        data={
            LOGIN_FORM.CSRF_TOKEN: valid_user_1[LOGIN_FORM.CSRF_TOKEN],
            LOGIN_FORM.USERNAME: valid_user_1[LOGIN_FORM.USERNAME],
            LOGIN_FORM.PASSWORD: valid_user_1[LOGIN_FORM.PASSWORD],
        },
        follow_redirects=True,
    )

    # Ensure backend sends url to home page for frontend to redirect to
    assert response.status_code == 200
    assert response.data == bytes(f"{url_for(ROUTES.UTUBS.HOME)}", "utf-8")

    # test if user logged in
    assert current_user.username == logged_in_user.username
    assert current_user.password == logged_in_user.password
    assert current_user.email == logged_in_user.email.lower()


def test_login_modal_is_shown(app_with_server_name, client):
    """
    GIVEN a non-logged in user visiting the splash page ("/")
    WHEN the user makes a request to "/login"
    THEN verify that the backends responds with a modal in the HTML
    """
    with client:
        with app_with_server_name.app_context():
            client.get(url_for(ROUTES.SPLASH.SPLASH_PAGE))
            response = client.get(url_for(ROUTES.SPLASH.LOGIN))
        assert (
            b'<form id="ModalForm" method="POST" class="login-register-form" action="/login" novalidate>'
            in response.data
        )

        # Ensure on login page
        assert (
            b'<input id="csrf_token" name="csrf_token" type="hidden" value='
            in response.data
        )
        assert (
            b'<input class="form-control login-register-form-group" id="username" name="username" required type="text" value="">'
            in response.data
        )
        assert (
            b'<input class="form-control login-register-form-group" id="password" name="password" required type="password" value="">'
            in response.data
        )
        assert request.path == url_for(ROUTES.SPLASH.LOGIN)


def test_login_modal_logs_user_in(app_with_server_name, client, register_first_user):
    """
    GIVEN a non-logged in user visiting the splash page ("/")
    WHEN the user makes a GET request to "/login", and then a POST request with the applicable form info
    THEN verify that the backends responds with URL to "/home" on response to the post
    """
    registered_user_data, _ = register_first_user
    with client:
        with app_with_server_name.app_context():
            client.get(url_for(ROUTES.SPLASH.SPLASH_PAGE))
            response = client.get(url_for(ROUTES.SPLASH.LOGIN))
        csrf_token = get_csrf_token(response.data)

        registered_user_data[LOGIN_FORM.CSRF_TOKEN] = csrf_token

        response = client.post(url_for(ROUTES.SPLASH.LOGIN), data=registered_user_data)

        assert response.status_code == 200
        assert response.data == bytes(f"{url_for(ROUTES.UTUBS.HOME)}", "utf-8")

        assert current_user.username == registered_user_data[LOGIN_FORM.USERNAME]
        assert check_password_hash(
            current_user.password, registered_user_data[LOGIN_FORM.PASSWORD]
        )
        assert current_user.email == registered_user_data[LOGIN_FORM.EMAIL].lower()
