import pytest
from flask import url_for, request
from models_for_test import invalid_user_1, valid_user_1
from flask_login import current_user
from urls4irl.models import User
from utils_for_test import get_csrf_token

def test_login_registered_user(app, register_first_user, load_login_page):
    """
    GIVEN a registered user
    WHEN "/login" is POST'd with filled in correctly with form data
    THEN ensure login does occur
    """
    registered_user = register_first_user
    client, csrf_token_str = load_login_page

    registered_user["csrf_token"] = csrf_token_str    

    response = client.post("/login", data=registered_user, follow_redirects = True)

    # Correctly redirects to home page
    assert response.history[0].status_code == 302
    assert response.status_code == 200
    assert request.path == url_for("main.home")
    assert len(response.history) == 1
    
    # Test if user logged in
    assert current_user.username == registered_user["username"]
    assert current_user.password != registered_user["password"]
    assert current_user.email == registered_user["email"]

    # Ensure user id's match with  database
    with app.app_context():
        registered_db_user = User.query.filter_by(username=registered_user["username"]).first()

    assert registered_db_user.id == int(current_user.get_id())

def test_login_unregistered_user(load_login_page):
    """
    GIVEN an unregistered user
    WHEN "/login" is POST'd with filled in correctly with form data
    THEN ensure login does not occur
    """
    client, csrf_token_str = load_login_page

    invalid_user_1["csrf_token"] = csrf_token_str

    response = client.post("/login", data={
        "csrf_token": invalid_user_1["csrf_token"],
        "username": invalid_user_1["username"],
        "password": invalid_user_1["password"]
    })

    #TODO: Check for error message of some kind here eventually

    assert response.status_code == 400
    assert request.path == url_for("users.login")

    # Ensure no one is logged in
    assert current_user.get_id() is None
    assert current_user.is_active is False

def test_already_logged_in_user_to_splash_page(login_first_user):
    """
    GIVEN a registered and logged in user
    WHEN "/" is GET after user is already logged on
    THEN ensure redirection occurs and user is brought to their home page
        - Note: Two redirects, from "/" -> "/login" -> "/home"
    """
    client, logged_in_user = login_first_user

    # Ensure redirect on home page access
    response = client.get("/", follow_redirects = True)

    # Correctly redirects first to login page
    # Since already logged in, redirects to home page
    assert len(response.history) == 2
    assert response.history[0].status_code == 302
    assert response.history[0].request.path == url_for("main.splash")
    assert response.history[1].status_code == 302
    assert response.history[1].request.path == url_for("users.login")

    # Ensure lands on user's home page
    assert response.status_code == 200
    assert request.path == url_for("main.home")

    # Test if user logged in
    assert current_user.username == logged_in_user.username
    assert current_user.password == logged_in_user.password
    assert current_user.email == logged_in_user.email
    assert int(current_user.get_id()) == logged_in_user.id

def test_already_logged_in_user_to_login_page(login_first_user):
    """
    GIVEN a registered and logged in user
    WHEN "/login" is GET after user is already logged on
    THEN ensure redirection occurs and user is brought to their home page
        - Note: Redirects are "/login" -> "/home"
    """
    client, logged_in_user = login_first_user

    # Ensure redirect on home page access
    response = client.get("/login", follow_redirects = True)

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

def test_already_logged_in_user_to_register_page(login_first_user):
    """
    GIVEN a registered and logged in user
    WHEN "/register" is GET after user is already logged on
    THEN ensure redirection occurs and user is brought to their home page
        - Note: Redirects are "/register" -> "/home"
    """
    client, logged_in_user = login_first_user

    # Ensure redirect on home page access
    response = client.get("/register", follow_redirects = True)

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

def test_already_logged_in_user_to_home_page(login_first_user):
    """
    GIVEN a registered and logged in user
    WHEN "/home" is GET after user is already logged on
    THEN ensure 200 and user is brought to their home page
    """
    client, logged_in_user = login_first_user

    # Ensure redirect on home page access
    response = client.get("/home", follow_redirects = True)

    assert len(response.history) == 0
    assert response.status_code == 200
    assert request.path == url_for("main.home")

    # Test if user logged in
    assert current_user.username == logged_in_user.username
    assert current_user.password == logged_in_user.password
    assert current_user.email == logged_in_user.email
    assert int(current_user.get_id()) == logged_in_user.id

    assert bytes(f'Logged in as {current_user.username}', 'utf-8') in response.data
    
def test_user_can_logout_after_login(login_first_user):
    """
    GIVEN a registered and logged in user
    WHEN "/logout" is GET after user is already logged on
    THEN ensure 200, user is brought to login page, user no longer logged in
    """
    client, logged_in_user = login_first_user

    # Ensure logout is successful
    response = client.get("/logout", follow_redirects = True)

    assert len(response.history) == 1
    assert response.history[0].status_code == 302
    assert response.history[0].request.path == url_for("users.logout")

    # Ensure lands on splash page
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

def test_user_can_login_logout_login(login_first_user):
    """
    GIVEN a registered and logged in user
    WHEN they logout via GET "/logout"
    THEN ensure they can login in again successfully
    """
    client, logged_in_user = login_first_user

    # Ensure logout is successful
    response = client.get("/logout", follow_redirects = True)

    # Ensure on login page
    assert b'<input id="csrf_token" name="csrf_token" type="hidden" value=' in response.data

    # Grab csrf token from login page
    valid_user_1["csrf_token"] = get_csrf_token(response.data)

    # Post data to login page
    response = client.post("/login", data = {
        "csrf_token": valid_user_1["csrf_token"],
        "username": valid_user_1["username"],
        "password": valid_user_1["password"]
    }, follow_redirects = True)

    # Ensure logged in user landed on home page
    assert len(response.history) == 1
    assert response.history[0].status_code == 302
    assert response.history[0].request.path == url_for("users.login")

    # Ensure lands on splash page
    assert response.status_code == 200
    assert request.path == url_for("main.home")

    # Test if user logged in
    assert current_user.username == logged_in_user.username
    assert current_user.password == logged_in_user.password
    assert current_user.email == logged_in_user.email
    assert int(current_user.get_id()) == logged_in_user.id

    assert bytes(f'Logged in as {current_user.username}', 'utf-8') in response.data
