from flask import Flask, url_for
from markupsafe import escape
import pytest

from backend.utils.all_routes import ROUTES
from backend.utils.constants import CONSTANTS

pytestmark = pytest.mark.splash

GOOGLE_OAUTH_LOGIN_BUTTON_ID = 'id="GoogleOAuthLogin"'
GOOGLE_OAUTH_REGISTER_BUTTON_ID = 'id="GoogleOAuthRegister"'


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
        assert str(escape(CONSTANTS.STRINGS.SPLASH_TAGLINE)).encode() in response.data


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


def test_google_oauth_buttons_shown_when_credentials_configured(
    app_with_server_name, client
):
    """
    GIVEN the test app, built with dummy Google OAuth credentials by default
        (`tests/conftest.py`'s `build_app` fixture)
    WHEN "/" is requested (GET)
    THEN the rendered splash page includes both the login and register
        Google OAuth buttons
    """
    with client:
        with app_with_server_name.app_context():
            response = client.get(url_for(ROUTES.SPLASH.SPLASH_PAGE))

        assert response.status_code == 200
        assert GOOGLE_OAUTH_LOGIN_BUTTON_ID.encode() in response.data
        assert GOOGLE_OAUTH_REGISTER_BUTTON_ID.encode() in response.data


def test_google_oauth_buttons_hidden_when_credentials_unconfigured(
    app_with_server_name: Flask, client
):
    """
    GIVEN the test app with Google OAuth credentials temporarily cleared,
        mirroring a deployment/checkout where `GOOGLE_OAUTH_CLIENT_ID`/
        `GOOGLE_OAUTH_CLIENT_SECRET` are unset
    WHEN "/" is requested (GET)
    THEN the rendered splash page omits both Google OAuth buttons, since
        `should_register_google_oauth` gates `google_oauth_enabled` in
        `backend.utils.constants.provide_config_for_constants`
    """
    original_client_id = app_with_server_name.config.get("GOOGLE_OAUTH_CLIENT_ID")
    original_client_secret = app_with_server_name.config.get(
        "GOOGLE_OAUTH_CLIENT_SECRET"
    )
    app_with_server_name.config["GOOGLE_OAUTH_CLIENT_ID"] = None
    app_with_server_name.config["GOOGLE_OAUTH_CLIENT_SECRET"] = None
    try:
        with client:
            with app_with_server_name.app_context():
                response = client.get(url_for(ROUTES.SPLASH.SPLASH_PAGE))

            assert response.status_code == 200
            assert GOOGLE_OAUTH_LOGIN_BUTTON_ID.encode() not in response.data
            assert GOOGLE_OAUTH_REGISTER_BUTTON_ID.encode() not in response.data
    finally:
        app_with_server_name.config["GOOGLE_OAUTH_CLIENT_ID"] = original_client_id
        app_with_server_name.config["GOOGLE_OAUTH_CLIENT_SECRET"] = (
            original_client_secret
        )
