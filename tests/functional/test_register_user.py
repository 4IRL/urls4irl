import pytest
from flask import url_for, request
from flask_login import current_user
from urls4irl import db
from models_for_test import valid_user_1
from urls4irl.models import User

def test_register_new_user(app, load_register_page):
    """
    GIVEN a new, unregistered user to the page
    WHEN they register to an empty database, and POST to "/register" correctly
    THEN ensure they are logged in and set to their home page
    """
    client, csrf_token_string = load_register_page

    valid_user_1["csrf_token"] = csrf_token_string

    # Ensure no user with this data exists in database
    with app.app_context():
        new_db_user = User.query.filter_by(username=valid_user_1["username"]).first()

    assert new_db_user is None

    response = client.post("/register", data=valid_user_1, follow_redirects = True)

    # Correctly redirects to home page
    assert response.history[0].status_code == 302
    assert response.status_code == 200
    assert request.path == url_for("main.home")
    assert len(response.history) == 1
    
    # Test if user logged in
    assert current_user.username == valid_user_1["username"]
    assert current_user.password != valid_user_1["password"]
    assert current_user.email == valid_user_1["email"]

    # Ensure user exists in database
    with app.app_context():
        new_db_user = User.query.filter_by(username=valid_user_1["username"]).first()

    # Ensure user model after loading from database is logged in
    assert new_db_user.is_authenticated is True
    assert new_db_user.is_active is True

    # Test if user db data is same as input when registering
    assert new_db_user.username == valid_user_1["username"]
    assert new_db_user.password != valid_user_1["password"]
    assert new_db_user.email == valid_user_1["email"]

    # Test if user db data is same as current user variable
    assert new_db_user.username == current_user.username
    assert new_db_user.password == current_user.password
    assert new_db_user.email == current_user.email
    assert new_db_user.id == int(current_user.get_id())

def test_register_duplicate_user(app, load_register_page, register_first_user):
    """
    GIVEN a user to the page
    WHEN they register with same credentials database, and POST to "/register" correctly
    THEN ensure they are not logged in and not registered again
    """
    client, csrf_token_string = load_register_page
    already_registered_user_data, _ = register_first_user

    already_registered_user_data["csrf_token"] = csrf_token_string

    # Ensure user already exists
    with app.app_context():
        new_db_user = User.query.filter_by(username=already_registered_user_data["username"]).first()

    assert new_db_user is not None

    # Ensure no one is logged in
    assert current_user.get_id() is None
    assert current_user.is_active is False

    response = client.post("/register", data=already_registered_user_data, follow_redirects = True)

    # Check that does not reroute
    assert response.status_code == 200
    assert request.path == url_for("users.register_user")
    assert len(response.history) == 0

    # Check that correctly displays error message
    assert b"<span>That username is already taken. Please choose another.</span>" in response.data
    assert b"<span>That email address is already in use.</span>" in response.data
