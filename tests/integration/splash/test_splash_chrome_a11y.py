import re

from flask import url_for
import pytest

from backend.utils.all_routes import ROUTES
from backend.utils.datetime_utils import utc_now

pytestmark = pytest.mark.splash

MODAL_LABEL_IDS = (
    b'id="LoginModalLabel"',
    b'id="RegisterModalLabel"',
    b'id="ForgotPasswordModalLabel"',
    b'id="EmailValidationModalLabel"',
)
FAVICON_IMG_PATTERN = re.compile(rb'<img[^>]*id="u4iFavicon"[^>]*>', re.IGNORECASE)
FAVICON_EMPTY_ALT_PATTERN = re.compile(rb'alt=""', re.IGNORECASE)
META_DESCRIPTION_PATTERN = re.compile(
    rb'<meta[^>]*name="description"[^>]*content="([^"]*)"', re.IGNORECASE
)


def test_modal_labels_have_matching_ids(app_with_server_name, client):
    """
    GIVEN a fresh user to the website who isn't logged in
    WHEN "/" is requested (GET)
    THEN all four modal-title elements carry the id their shell's
        aria-labelledby attribute references, fixing the broken a11y link
    """
    with client:
        with app_with_server_name.app_context():
            response = client.get(
                url_for(ROUTES.SPLASH.SPLASH_PAGE), follow_redirects=True
            )

        assert response.status_code == 200
        for label_id in MODAL_LABEL_IDS:
            assert label_id in response.data


def test_navbar_favicon_has_alt_attribute(app_with_server_name, client):
    """
    GIVEN a fresh user to the website who isn't logged in
    WHEN "/" is requested (GET)
    THEN the navbar favicon <img> carries an empty alt attribute,
        marking it decorative for assistive technology
    """
    with client:
        with app_with_server_name.app_context():
            response = client.get(
                url_for(ROUTES.SPLASH.SPLASH_PAGE), follow_redirects=True
            )

        assert response.status_code == 200

        favicon_tag_match = FAVICON_IMG_PATTERN.search(response.data)
        assert favicon_tag_match is not None
        assert FAVICON_EMPTY_ALT_PATTERN.search(favicon_tag_match.group(0)) is not None


def test_meta_description_populated_on_splash(app_with_server_name, client):
    """
    GIVEN a fresh user to the website who isn't logged in
    WHEN "/" is requested (GET)
    THEN the shared meta description is non-empty
    """
    with client:
        with app_with_server_name.app_context():
            response = client.get(
                url_for(ROUTES.SPLASH.SPLASH_PAGE), follow_redirects=True
            )

        assert response.status_code == 200

        description_match = META_DESCRIPTION_PATTERN.search(response.data)
        assert description_match is not None
        assert len(description_match.group(1)) > 0


def test_meta_description_populated_on_home(login_first_user_with_register):
    """
    GIVEN a registered, logged-in user
    WHEN "/home" is requested (GET)
    THEN the shared meta description is non-empty, closing the
        cross-blueprint coverage gap for the shared meta.html partial
    """
    client, _, _, _ = login_first_user_with_register

    response = client.get("/home")

    assert response.status_code == 200

    description_match = META_DESCRIPTION_PATTERN.search(response.data)
    assert description_match is not None
    assert len(description_match.group(1)) > 0


def test_footer_year_uses_current_year(app_with_server_name, client):
    """
    GIVEN a fresh user to the website who isn't logged in
    WHEN "/" is requested (GET)
    THEN the footer renders the current year, proving current_year
        is injected and resolved (not emitted as a literal Jinja tag)
    """
    year = utc_now().year
    with client:
        with app_with_server_name.app_context():
            response = client.get(
                url_for(ROUTES.SPLASH.SPLASH_PAGE), follow_redirects=True
            )

        assert response.status_code == 200
        assert f"© {year} URLS4IRL".encode() in response.data
