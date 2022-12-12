import pytest
from flask import url_for, request
from models_for_test import invalid_user_1
from flask_login import current_user
from urls4irl.models import User

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
    