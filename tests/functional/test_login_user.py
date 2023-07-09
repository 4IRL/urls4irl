import pytest
from flask import url_for, request
from flask_login import current_user
from werkzeug.security import check_password_hash

from models_for_test import invalid_user_1, valid_user_1
from urls4irl.models import User
from utils_for_test import get_csrf_token


def test_login_registered_and_logged_in_user(app, register_first_user, load_login_page):
    """
    GIVEN a registered and logged in user
    WHEN "/login" is POST'd with CSRF token
    THEN ensure the user is redirected to the home page since they are already logged in
    """
    registered_user_data, _ = register_first_user
    client, csrf_token_str = load_login_page

    registered_user_data["csrf_token"] = csrf_token_str

    response = client.post("/login", data=registered_user_data, follow_redirects=True)

    # Correctly responds with URL to home page
    assert response.data == b"/home"
    assert response.status_code == 200

    # Test if user logged in
    assert current_user.username == registered_user_data["username"]
    assert check_password_hash(current_user.password, registered_user_data["password"])
    assert current_user.email == registered_user_data["email"]

    # Ensure user id's match with  database
    with app.app_context():
        registered_db_user = User.query.filter_by(
            username=registered_user_data["username"]
        ).first()

    assert registered_db_user.id == int(current_user.get_id())


def test_login_unregistered_user(load_login_page):
    """
    GIVEN an unregistered user
    WHEN "/login" is POST'd with filled in correctly with form data
    THEN ensure login does not occur
    """
    client, csrf_token_str = load_login_page

    invalid_user_1["csrf_token"] = csrf_token_str

    response = client.post(
        "/login",
        data={
            "csrf_token": invalid_user_1["csrf_token"],
            "username": invalid_user_1["username"],
            "password": invalid_user_1["password"],
        },
    )

    # TODO: Check for error message of some kind here eventually

    assert response.status_code == 400
    assert request.path == url_for("users.login")

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
    response = client.get("/", follow_redirects=True)

    # Correctly redirects first to login page
    # Since already logged in, redirects to home page
    assert len(response.history) == 1
    assert response.history[0].status_code == 302
    assert response.history[0].request.path == url_for("main.splash")

    # Ensure lands on user's home page
    assert response.status_code == 200
    assert request.path == url_for("main.home")

    # Test if user logged in
    assert current_user.username == logged_in_user.username
    assert current_user.password == logged_in_user.password
    assert current_user.email == logged_in_user.email
    assert int(current_user.get_id()) == logged_in_user.id


def test_already_logged_in_user_to_login_page(login_first_user_with_register):
    """
    GIVEN a registered and logged in user
    WHEN "/login" is GET after user is already logged on
    THEN ensure redirection occurs and user is brought to their home page
        - Note: Redirects are "/login" -> "/home"
    """
    client, csrf_token, logged_in_user, app = login_first_user_with_register

    # Ensure redirect on home page access
    response = client.get("/login", follow_redirects=True)

    # Correctly redirects first to login page
    # Since already logged in, redirects to home page
    assert len(response.history) == 1
    assert response.history[0].status_code == 302
    assert response.history[0].request.path == url_for("users.login")

    # Ensure lands on user's home page
    assert response.status_code == 200
    assert request.path == url_for("main.home")

    # Test if user logged in
    assert current_user.username == logged_in_user.username
    assert current_user.password == logged_in_user.password
    assert current_user.email == logged_in_user.email
    assert int(current_user.get_id()) == logged_in_user.id


def test_already_logged_in_user_to_register_page(login_first_user_with_register):
    """
    GIVEN a registered and logged in user
    WHEN "/register" is GET after user is already logged on
    THEN ensure redirection occurs and user is brought to their home page
        - Note: Redirects are "/register" -> "/home"
    """
    client, csrf_token, logged_in_user, app = login_first_user_with_register

    # Ensure redirect on home page access
    response = client.get("/register", follow_redirects=True)

    # Correctly redirects first to login page
    # Since already logged in, redirects to home page
    assert len(response.history) == 1
    assert response.history[0].status_code == 302
    assert response.history[0].request.path == url_for("users.register_user")

    # Ensure lands on user's home page
    assert response.status_code == 200
    assert request.path == url_for("main.home")

    # Test if user logged in
    assert current_user.username == logged_in_user.username
    assert current_user.password == logged_in_user.password
    assert current_user.email == logged_in_user.email
    assert int(current_user.get_id()) == logged_in_user.id


def test_already_logged_in_user_to_home_page(login_first_user_with_register):
    """
    GIVEN a registered and logged in user
    WHEN "/home" is GET after user is already logged on
    THEN ensure 200 and user is brought to their home page
    """
    client, csrf_token, logged_in_user, app = login_first_user_with_register

    # Ensure redirect on home page access
    response = client.get("/home", follow_redirects=True)

    assert len(response.history) == 0
    assert response.status_code == 200
    assert request.path == url_for("main.home")

    # Test if user logged in
    assert current_user.username == logged_in_user.username
    assert current_user.password == logged_in_user.password
    assert current_user.email == logged_in_user.email
    assert int(current_user.get_id()) == logged_in_user.id

    assert bytes(f"Logged in as {current_user.username}", "utf-8") in response.data


def test_user_can_logout_after_login(login_first_user_with_register):
    """
    GIVEN a registered and logged in user
    WHEN "/logout" is GET after user is already logged on
    THEN ensure 200, user is brought to login page, user no longer logged in
    """
    client, csrf_token, logged_in_user, app = login_first_user_with_register

    # Ensure logout is successful
    response = client.get("/logout", follow_redirects=True)

    assert len(response.history) == 1
    assert response.history[0].status_code == 302
    assert response.history[0].request.path == url_for("users.logout")

    # Ensure lands on login page
    assert response.status_code == 200
    assert request.path == url_for("users.login")

    # Test if user logged in
    with pytest.raises(AttributeError):
        assert current_user.username != logged_in_user.username
        assert current_user.password != logged_in_user.password
        assert current_user.email != logged_in_user.email

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
    response = client.get("/logout", follow_redirects=True)

    # Ensure on login page
    assert (
        b'<input id="csrf_token" name="csrf_token" type="hidden" value='
        in response.data
    )
    assert (
        b'<input class="form-control form-control-lg" id="username" name="username" required type="text" value="">'
        in response.data
    )
    assert (
        b'<input class="form-control form-control-lg" id="password" name="password" required type="password" value="">'
        in response.data
    )
    assert request.path == url_for("users.login")

    # Grab csrf token from login page
    valid_user_1["csrf_token"] = get_csrf_token(response.data)

    # Post data to login page
    response = client.post(
        "/login",
        data={
            "csrf_token": valid_user_1["csrf_token"],
            "username": valid_user_1["username"],
            "password": valid_user_1["password"],
        },
        follow_redirects=True,
    )

    # Ensure backend sends url to home page for frontend to redirect to
    assert response.status_code == 200
    assert response.data == bytes(f"{url_for('main.home')}", "utf-8")

    # test if user logged in
    assert current_user.username == logged_in_user.username
    assert current_user.password == logged_in_user.password
    assert current_user.email == logged_in_user.email


def test_login_modal_is_shown(client):
    """
    GIVEN a non-logged in user visiting the splash page ("/")
    WHEN the user makes a request to "/login"
    THEN verify that the backends responds with a modal in the HTML
    """
    with client:
        response = client.get("/")
        response = client.get("/login")
        assert (
            b'<form id="ModalForm" method="POST" class="login-register-form" action="" novalidate>'
            in response.data
        )

        # Ensure on login page
        assert (
            b'<input id="csrf_token" name="csrf_token" type="hidden" value='
            in response.data
        )
        assert (
            b'<input class="form-control form-control-lg" id="username" name="username" required type="text" value="">'
            in response.data
        )
        assert (
            b'<input class="form-control form-control-lg" id="password" name="password" required type="password" value="">'
            in response.data
        )
        assert request.path == url_for("users.login")


def test_login_modal_logs_user_in(client, register_first_user):
    """
    GIVEN a non-logged in user visiting the splash page ("/")
    WHEN the user makes a GET request to "/login", and then a POST request with the applicable form info
    THEN verify that the backends responds with URL to "/home" on response to the post
    """
    registered_user_data, _ = register_first_user
    with client:
        response = client.get("/")
        response = client.get("/login")
        csrf_token = get_csrf_token(response.data)

        registered_user_data["csrf_token"] = csrf_token

        response = client.post("/login", data=registered_user_data)

        assert response.status_code == 200
        assert response.data == bytes(f"{url_for('main.home')}", "utf-8")

        assert current_user.username == registered_user_data["username"]
        assert check_password_hash(
            current_user.password, registered_user_data["password"]
        )
        assert current_user.email == registered_user_data["email"]
