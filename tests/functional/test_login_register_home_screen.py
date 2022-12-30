import pytest
from flask import url_for, request

def test_get_home_screen_not_logged_in(client):
    """
    GIVEN a fresh user to the website who isn't logged in
    WHEN "/" is requested (GET)
    THEN ensure redirect to "login"
    """
    with client:
        response = client.get("/", follow_redirects = True)
        
        # Currently redirects to login page, no splash page
        assert response.history[0].status_code == 302
        assert response.status_code == 200
        assert request.path == url_for("users.login")
        assert len(response.history) == 1

def test_post_home_screen_not_logged_in(client):
    """
    GIVEN a fresh user to the website who isn't logged in
    WHEN "/" is requested (POST)
    THEN check 405 occurs and user is not redirected
    """
    with client:
        response = client.post("/", follow_redirects = True)

        assert response.status_code == 405
        assert len(response.history) == 0
        assert request.path != url_for("users.login")

def test_get_login_screen_not_logged_in(client):
    """
    GIVEN a fresh user to the website who isn't logged in
    WHEN "/login" is requested (GET)
    THEN ensure page contains Login form data, and successful page load
    """
    with client:
        response = client.get("/login")

        assert response.status_code == 200

        assert b'<input class="form-control form-control-lg" id="username" name="username" required type="text" value="">' in response.data
        assert b'<input class="form-control form-control-lg" id="password" name="password" required type="password" value="">' in response.data
        assert b'<input id="csrf_token" name="csrf_token" type="hidden" value=' in response.data

        assert request.path == url_for("users.login")

def test_get_register_screen_not_logged_in(client):
    """
    GIVEN a fresh user to the website who isn't logged in
    WHEN "/register" is requested (GET)
    THEN ensure page contains Register form data, and successful page load
    """
    with client:
        response = client.get("/register")

        assert response.status_code == 200

        assert b'<input class="form-control form-control-lg" id="username" maxlength="20" minlength="4" name="username" required type="text" value="">' in response.data
        assert b'<input class="form-control form-control-lg" id="email" name="email" required type="text" value="">' in response.data
        assert b'<input class="form-control form-control-lg" id="confirm_email" name="confirm_email" required type="text" value="">' in response.data
        assert b'<input class="form-control form-control-lg" id="password" maxlength="64" minlength="12" name="password" required type="password" value="">' in response.data
        assert b'<input class="form-control form-control-lg" id="confirm_password" name="confirm_password" required type="password" value="">' in response.data
        assert b'<input id="csrf_token" name="csrf_token" type="hidden" value=' in response.data

        assert request.path == url_for("users.register_user")
