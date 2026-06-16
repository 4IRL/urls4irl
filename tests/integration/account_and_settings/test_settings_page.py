from typing import Tuple
from urllib.parse import quote, urlsplit

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient

from backend.models.users import Users
from backend.utils.all_routes import ROUTES

pytestmark = pytest.mark.account_and_support

_SETTINGS_PATH = "/settings"
_SPLASH_PATH = "/"


def test_settings_page_renders_for_authenticated_user(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """Authenticated GET /settings returns 200 HTML with the settings shell
    and all four tab buttons."""
    logged_in_client, _, _, _ = login_first_user_with_register

    resp = logged_in_client.get(url_for(ROUTES.USERS.SETTINGS))

    assert resp.status_code == 200
    assert resp.mimetype == "text/html"
    assert b'id="SettingsPage"' in resp.data
    assert b'data-tab="account"' in resp.data
    assert b'data-tab="stats"' in resp.data
    assert b'data-tab="privacy_data"' in resp.data
    assert b'data-tab="ui_settings"' in resp.data


def test_settings_page_default_tab_is_account(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """The Account tab is the default selection and its panel is the only one
    rendered without the ``hidden`` attribute."""
    logged_in_client, _, _, _ = login_first_user_with_register

    resp = logged_in_client.get(url_for(ROUTES.USERS.SETTINGS))

    assert resp.status_code == 200
    assert b'aria-selected="true"' in resp.data
    assert b'id="SettingsPanelAccount"' in resp.data
    assert b" hidden" in resp.data

    # Semantically precise: the Account tab button — and only it — carries
    # aria-selected="true". Locate the Account button's tag and assert the
    # selected state appears within it, without coupling to whitespace.
    account_tag_start = resp.data.index(b'id="SettingsTabAccount"')
    account_tag_end = resp.data.index(b">", account_tag_start)
    account_button_tag = resp.data[account_tag_start:account_tag_end]
    assert b'aria-selected="true"' in account_button_tag


def test_settings_page_redirects_anonymous_to_splash(client: FlaskClient) -> None:
    """Anonymous GET /settings 302 redirects to splash (`/`) with the original
    path preserved in the ``next`` query parameter."""
    resp = client.get(_SETTINGS_PATH)

    assert resp.status_code == 302
    assert resp.location is not None

    redirect_path = urlsplit(resp.location).path
    assert redirect_path == _SPLASH_PATH
    assert (
        f"next={quote(_SETTINGS_PATH, safe='')}" in resp.location
        or _SETTINGS_PATH in resp.location
    )


def test_settings_page_redirects_unvalidated_user_to_splash(
    login_unvalidated_user: Tuple[FlaskClient, Users, Flask],
) -> None:
    """An authenticated-but-unvalidated user GET /settings receives a plain 302
    to splash (`/`) with no ``next`` query parameter."""
    logged_in_client, _, _ = login_unvalidated_user

    resp = logged_in_client.get(_SETTINGS_PATH)

    assert resp.status_code == 302
    assert resp.location is not None

    redirect_path = urlsplit(resp.location).path
    assert redirect_path == _SPLASH_PATH


def test_settings_page_exposes_csrf_meta_and_app_config(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """The settings page renders the standard CSRF meta tag and the
    ``app-config`` JSON script the JS bundle depends on."""
    logged_in_client, _, _, _ = login_first_user_with_register

    resp = logged_in_client.get(url_for(ROUTES.USERS.SETTINGS))

    assert resp.status_code == 200
    assert b'name="csrf-token"' in resp.data
    assert b'id="app-config"' in resp.data


def test_settings_nav_link_present_on_home(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """The authenticated home page renders the Settings nav link."""
    logged_in_client, _, _, _ = login_first_user_with_register

    resp = logged_in_client.get(url_for(ROUTES.UTUBS.HOME))

    assert resp.status_code == 200
    assert b'href="/settings"' in resp.data
    assert b'id="userSettingsLink"' in resp.data


def test_settings_nav_link_hidden_on_settings_page(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """The Settings nav link is omitted while viewing the settings page itself."""
    logged_in_client, _, _, _ = login_first_user_with_register

    resp = logged_in_client.get(url_for(ROUTES.USERS.SETTINGS))

    assert resp.status_code == 200
    assert b'id="userSettingsLink"' not in resp.data
