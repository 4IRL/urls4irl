import json
import re

from flask import Flask, url_for
from flask.testing import FlaskClient
import pytest

from backend.api_common.error_handler import _is_reload_safe_request
from backend.utils.all_routes import ROUTES
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.splash_form_strs import LOGIN_FORM
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from tests.models_for_test import valid_user_1

pytestmark = pytest.mark.splash

APP_CONFIG_SCRIPT_PATTERN = re.compile(
    r'<script id="app-config" type="application/json">(?P<config>.*?)</script>',
    re.DOTALL,
)
# An empty X-Requested-With keeps AjaxFlaskClient from injecting the XHR header,
# so the 404 handler takes its HTML (full-page navigation) branch.
NON_XHR_HEADERS = {URL_VALIDATION.X_REQUESTED_WITH: ""}
RELOAD_SAFE_ATTRIBUTE = 'data-reload-safe="true"'
RELOAD_UNSAFE_ATTRIBUTE = 'data-reload-safe="false"'


def _assert_error_page_has_app_config(*, html: str) -> None:
    """The error page's error.ts imports lib/config.ts, which throws at import
    time unless `#app-config` holds the app's JSON config."""
    config_match = APP_CONFIG_SCRIPT_PATTERN.search(html)
    assert config_match is not None
    app_config = json.loads(config_match.group("config"))
    assert app_config["routes"]
    assert app_config["strings"]
    assert app_config["constants"]


def test_csrf_403_error_page_renders_app_config(load_login_page):
    """
    GIVEN the login page
    WHEN "/login" is POST'd without a CSRF token
    THEN ensure the HTML 403 error page embeds the #app-config JSON its script needs
    """
    client, _ = load_login_page

    response = client.post(
        url_for(ROUTES.SPLASH.LOGIN),
        json={
            LOGIN_FORM.USERNAME: valid_user_1[LOGIN_FORM.USERNAME],
            LOGIN_FORM.PASSWORD: "A",
        },
    )

    assert response.status_code == 403
    html = response.get_data(as_text=True)
    assert IDENTIFIERS.HTML_403 in html
    _assert_error_page_has_app_config(html=html)


def test_429_error_page_renders_app_config(load_login_page):
    """
    GIVEN an anonymous client
    WHEN a request is rate limited
    THEN ensure the HTML 429 error page embeds the #app-config JSON its script needs
    """
    client, _ = load_login_page
    response = client.get(
        url_for(ROUTES.SPLASH.LOGIN), headers={"X-Force-Rate-Limit": "true"}
    )

    assert response.status_code == 429
    html = response.get_data(as_text=True)
    assert IDENTIFIERS.HTML_429 in html
    _assert_error_page_has_app_config(html=html)


def test_csrf_403_from_full_page_post_marks_refresh_not_reload_safe(load_login_page):
    """
    GIVEN the login page
    WHEN "/login" is POST'd as a full-page (non-AJAX) form submit without a CSRF token
    THEN ensure the 403 page's refresh button is marked data-reload-safe="false",
         since reloading would GET the POST-only /login route
    """
    client, _ = load_login_page

    response = client.post(
        url_for(ROUTES.SPLASH.LOGIN),
        data={LOGIN_FORM.USERNAME: valid_user_1[LOGIN_FORM.USERNAME]},
        headers=NON_XHR_HEADERS,
    )

    assert response.status_code == 403
    assert RELOAD_UNSAFE_ATTRIBUTE in response.get_data(as_text=True)


def test_csrf_403_from_ajax_post_marks_refresh_reload_safe(load_login_page):
    """
    GIVEN the login page
    WHEN "/login" is POST'd via AJAX without a CSRF token
    THEN ensure the 403 page's refresh button is marked data-reload-safe="true",
         since the page is written over the GET-loaded page that sent the request
    """
    client, _ = load_login_page

    response = client.post(
        url_for(ROUTES.SPLASH.LOGIN),
        json={LOGIN_FORM.USERNAME: valid_user_1[LOGIN_FORM.USERNAME]},
    )

    assert response.status_code == 403
    assert RELOAD_SAFE_ATTRIBUTE in response.get_data(as_text=True)


def test_429_from_full_page_get_marks_refresh_reload_safe(load_login_page):
    """
    GIVEN an anonymous client
    WHEN a full-page GET is rate limited
    THEN ensure the 429 page's refresh button is marked data-reload-safe="true"
    """
    client, _ = load_login_page
    response = client.get(
        url_for(ROUTES.SPLASH.LOGIN),
        headers={**NON_XHR_HEADERS, "X-Force-Rate-Limit": "true"},
    )

    assert response.status_code == 429
    assert RELOAD_SAFE_ATTRIBUTE in response.get_data(as_text=True)


def test_full_page_head_request_is_reload_safe(app: Flask):
    """
    GIVEN a full-page (non-AJAX) HEAD request
    WHEN its error page decides whether the refresh button can reload the URL
    THEN ensure it is reload-safe, since a HEAD can be re-requested like a GET
         (checked on the request directly: a HEAD response carries no body)
    """
    with app.test_request_context(
        "/this-path-does-not-exist", method="HEAD", headers=NON_XHR_HEADERS
    ):
        assert _is_reload_safe_request()


def test_404_error_page_on_unmatched_path_renders_app_config(client: FlaskClient):
    """
    GIVEN an anonymous client
    WHEN a full-page navigation hits a path no blueprint matches
    THEN ensure the HTML 404 page still embeds #app-config (no blueprint context
         processor runs for an unmatched path, so the handler must supply it)
    """
    response = client.get("/this-path-does-not-exist", headers=NON_XHR_HEADERS)

    assert response.status_code == 404
    html = response.get_data(as_text=True)
    assert IDENTIFIERS.HTML_404 in html
    _assert_error_page_has_app_config(html=html)
