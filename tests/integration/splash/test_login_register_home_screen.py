from flask import url_for, request
import pytest

from src.utils.all_routes import ROUTES
from src.utils.constants import USER_CONSTANTS

pytestmark = pytest.mark.splash


def test_get_home_screen_not_logged_in(app_with_server_name, client):
    """
    GIVEN a fresh user to the website who isn't logged in
    WHEN "/" is requested (GET)
    THEN ensure redirect to splash page
    """
    with client:
        with app_with_server_name.app_context():
            response = client.get(
                url_for(ROUTES.SPLASH.SPLASH_PAGE), follow_redirects=True
            )

        # Hits splash page
        assert response.status_code == 200
        assert (
            bytes("A simple, clean way to permanently save and share URLs.", "utf-8")
            in response.data
        )


def test_post_home_screen_not_logged_in(app_with_server_name, client):
    """
    GIVEN a fresh user to the website who isn't logged in
    WHEN "/" is requested (POST)
    THEN check 405 occurs and user is not redirected
    """
    with client:
        with app_with_server_name.app_context():
            response = client.post(
                url_for(ROUTES.SPLASH.SPLASH_PAGE), follow_redirects=True
            )

        assert response.status_code == 405
        assert len(response.history) == 0
        assert request.path != url_for(ROUTES.SPLASH.LOGIN)


def test_get_login_screen_not_logged_in(app_with_server_name, client):
    """
    GIVEN a fresh user to the website who isn't logged in
    WHEN "/login" is requested (GET)
    THEN ensure page contains Login form data, and successful page load
    """
    with client:
        with app_with_server_name.app_context():
            response = client.get(url_for(ROUTES.SPLASH.LOGIN))

        assert response.status_code == 200

        login_input_html = f'<input class="form-control login-register-form-group" id="username" maxlength="{USER_CONSTANTS.MAX_USERNAME_LENGTH}" minlength="{USER_CONSTANTS.MIN_USERNAME_LENGTH}" name="username" required type="text" value="">'

        assert login_input_html.encode() in response.data
        assert (
            b'<input class="form-control login-register-form-group" id="password" name="password" required type="password" value="">'
            in response.data
        )
        assert (
            b'<input id="csrf_token" name="csrf_token" type="hidden" value='
            in response.data
        )

        assert request.path == url_for(ROUTES.SPLASH.LOGIN)


def test_get_register_screen_not_logged_in(app_with_server_name, client):
    """
    GIVEN a fresh user to the website who isn't logged in
    WHEN "/register" is requested (GET)
    THEN ensure page contains Register form data, and successful page load
    """
    with client:
        with app_with_server_name.app_context():
            response = client.get(url_for(ROUTES.SPLASH.REGISTER))

        assert response.status_code == 200

        assert (
            b'<input class="form-control login-register-form-group" id="username" maxlength="20" minlength="3" name="username" required type="text" value="">'
            in response.data
        )
        assert (
            b'<input class="form-control login-register-form-group" id="email" name="email" required type="text" value="">'
            in response.data
        )
        assert (
            b'<input class="form-control login-register-form-group" id="confirmEmail" name="confirmEmail" required type="text" value="">'
            in response.data
        )
        password_input_html = f'<input class="form-control login-register-form-group" id="password" maxlength="{USER_CONSTANTS.MAX_PASSWORD_LENGTH}" minlength="{USER_CONSTANTS.MIN_PASSWORD_LENGTH}" name="password" required type="password" value="">'
        assert password_input_html.encode() in response.data
        assert (
            b'<input class="form-control login-register-form-group" id="confirmPassword" name="confirmPassword" required type="password" value="">'
            in response.data
        )
        assert (
            b'<input id="csrf_token" name="csrf_token" type="hidden" value='
            in response.data
        )

        assert request.path == url_for(ROUTES.SPLASH.REGISTER)
