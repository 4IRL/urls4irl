from flask import url_for
from markupsafe import escape
import pytest

from backend.utils.all_routes import ROUTES
from backend.utils.constants import CONSTANTS

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
