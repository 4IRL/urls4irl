from typing import Tuple
from urllib.parse import quote, urlsplit

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient

from backend import db
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.utils.all_routes import ROUTES
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.conftest import AjaxFlaskLoginClient

pytestmark = pytest.mark.account_and_support

_SETTINGS_PATH = "/settings"
_SPLASH_PATH = "/"

# The next settings panel opens immediately after #SettingsPanelStats closes,
# so it bounds the final ("member-since") card's slice.
_NEXT_PANEL_MARKER = b'id="SettingsPanelPrivacyData"'


def _slice_stat_card(resp_data: bytes, stat_name: str) -> bytes:
    """Return the byte slice spanning a single stats card, from its
    ``data-stat="…"`` attribute up to the next card's ``data-stat`` (or, for
    the last card, the next settings panel's opening tag).

    Mirrors the account-tab slicing precedent
    (``test_settings_page_default_tab_is_account``) so a count rendered in the
    *wrong* card fails the assertion, unlike a bare ``in resp.data`` check.
    """
    card_start = resp_data.index(f'data-stat="{stat_name}"'.encode())
    next_card = resp_data.find(b'data-stat="', card_start + 1)
    card_end = (
        next_card
        if next_card != -1
        else resp_data.index(_NEXT_PANEL_MARKER, card_start)
    )
    return resp_data[card_start:card_end]


# The account-info grid is the first <dl> in document order (the Account panel
# precedes the Stats panel), so its closing tag bounds the final
# ("email-verified") account-info card's slice.
_ACCOUNT_INFO_GRID_END = b"</dl>"


def _slice_account_info_card(resp_data: bytes, info_name: str) -> bytes:
    """Return the byte slice spanning a single account-info card, from its
    ``data-account-info="…"`` attribute up to the next card's
    ``data-account-info`` (or, for the last card, the account-info grid's
    closing ``</dl>``).

    Mirrors ``_slice_stat_card`` so a value rendered in the *wrong* card fails
    the assertion, unlike a bare ``in resp.data`` check.
    """
    card_start = resp_data.index(f'data-account-info="{info_name}"'.encode())
    next_card = resp_data.find(b'data-account-info="', card_start + 1)
    card_end = (
        next_card
        if next_card != -1
        else resp_data.index(_ACCOUNT_INFO_GRID_END, card_start)
    )
    return resp_data[card_start:card_end]


def test_settings_account_info_renders_user_details(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """The Account panel's read-only account-info block renders the user's
    username, email, exact member-since date, and a verified email indicator,
    each within its own card slice so a value in the wrong card fails."""
    logged_in_client, _, _, app = login_first_user_with_register

    resp = logged_in_client.get(url_for(ROUTES.USERS.SETTINGS))

    assert resp.status_code == 200

    # Section heading + all four card labels render.
    for label in (
        UI_TEST_STRINGS.SETTINGS_ACCOUNT_INFO_TITLE,
        UI_TEST_STRINGS.SETTINGS_ACCOUNT_USERNAME_LABEL,
        UI_TEST_STRINGS.SETTINGS_ACCOUNT_EMAIL_LABEL,
        UI_TEST_STRINGS.SETTINGS_ACCOUNT_MEMBER_SINCE_LABEL,
        UI_TEST_STRINGS.SETTINGS_ACCOUNT_EMAIL_STATUS_LABEL,
    ):
        assert label.encode() in resp.data

    with app.app_context():
        seeded_user: Users = Users.query.get(1)
        expected_username = seeded_user.username.encode()
        expected_email = seeded_user.email.encode()
        expected_iso = seeded_user.created_at.date().isoformat().encode()
        expected_exact = (
            f"{seeded_user.created_at:%B} {seeded_user.created_at.day}, "
            f"{seeded_user.created_at:%Y}"
        ).encode()

    assert expected_username in _slice_account_info_card(resp.data, "username")
    assert expected_email in _slice_account_info_card(resp.data, "email")

    member_since_slice = _slice_account_info_card(resp.data, "member-since")
    assert expected_iso in member_since_slice
    assert expected_exact in member_since_slice

    # The email-status card shows the verified indicator (the settings page is
    # gated by email_validation_required, so a reaching user is always verified).
    verified_slice = _slice_account_info_card(resp.data, "email-verified")
    assert UI_TEST_STRINGS.SETTINGS_ACCOUNT_EMAIL_VERIFIED.encode() in verified_slice


def test_settings_account_info_renders_username_for_oauth_only_user(
    app: Flask,
) -> None:
    """A password-less (OAuth-only) user still sees the account-info block with
    their username rendered — the block always renders regardless of whether the
    account has a password."""
    app.test_client_class = AjaxFlaskLoginClient

    oauth_only_username = "settingsinfooauthonly"
    oauth_only_email = "settingsinfooauthonly@example.com"

    with app.app_context():
        oauth_user = Users(
            username=oauth_only_username,
            email=oauth_only_email,
            plaintext_password=None,
        )
        oauth_user.oauth_identities.append(
            UserOAuthIdentity(
                provider="google",
                provider_subject="sub_settings_info_oauth_only",
            )
        )
        oauth_user.email_validated = True
        db.session.add(oauth_user)
        db.session.commit()

    with app.app_context():
        user_to_login: Users = Users.query.filter_by(email=oauth_only_email).first()

    with app.test_client(user=user_to_login) as logged_in_client:
        # Warm up the FlaskLoginClient login on /home first (matches every
        # login_* fixture); the first request establishes the session before
        # the settings page is fetched.
        logged_in_client.get("/home")
        resp = logged_in_client.get(_SETTINGS_PATH)

    assert resp.status_code == 200
    assert oauth_only_username.encode() in _slice_account_info_card(
        resp.data, "username"
    )


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


def test_settings_stats_zero_state_renders_zero_counts(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A brand-new user (no seeded content) sees all six stat cards, every
    count card reading ``0``, and the member-since card showing its exact join
    date via ``<time datetime>``."""
    logged_in_client, _, _, app = login_first_user_with_register

    resp = logged_in_client.get(url_for(ROUTES.USERS.SETTINGS))

    assert resp.status_code == 200

    # All six card labels render.
    for card_label in (
        UI_TEST_STRINGS.SETTINGS_STATS_UTUBS_CREATED,
        UI_TEST_STRINGS.SETTINGS_STATS_MEMBER_OF,
        UI_TEST_STRINGS.SETTINGS_STATS_URLS_ADDED,
        UI_TEST_STRINGS.SETTINGS_STATS_TAGS_CREATED,
        UI_TEST_STRINGS.SETTINGS_STATS_TAGS_APPLIED,
        UI_TEST_STRINGS.SETTINGS_STATS_MEMBER_SINCE,
    ):
        assert card_label.encode() in resp.data

    # Every count card reads 0 — asserted only within its own card slice so a
    # 0 rendered in the wrong card would still fail.
    for stat_name in (
        "utubs-created",
        "member-of",
        "urls-added",
        "tags-created",
        "tags-applied",
    ):
        card_slice = _slice_stat_card(resp.data, stat_name)
        assert b">0</dd>" in card_slice

    # The member-since card shows the exact join date (never a 0 count).
    with app.app_context():
        seeded_user: Users = Users.query.get(1)
        expected_exact = (
            f"{seeded_user.created_at:%B} {seeded_user.created_at.day}, "
            f"{seeded_user.created_at:%Y}"
        ).encode()
        expected_iso = seeded_user.created_at.date().isoformat().encode()

    member_since_slice = _slice_stat_card(resp.data, "member-since")
    assert expected_iso in member_since_slice
    assert expected_exact in member_since_slice


def test_settings_stats_populated_renders_distinct_counts(
    login_first_user_with_distinct_stats: Tuple[FlaskClient, Users, Flask],
) -> None:
    """With mutually-distinct seeded counts (2/4/5/7/11) plus noise rows owned
    by another user / NULL, each stat card renders its own value within its own
    slice — so a swapped/mislabeled card fails — and the noise rows leave user
    1's counts unchanged (proving the per-user filter and NULL exclusion).

    ``member-of`` is 4, not 3: the fixture seeds 3 UTubs where user 1 is a plain
    MEMBER plus 1 where user 1 is a CO_CREATOR, and the "member of" filter
    excludes only ``Member_Role.CREATOR`` — so co-ownership counts."""
    logged_in_client, _, _ = login_first_user_with_distinct_stats

    resp = logged_in_client.get(url_for(ROUTES.USERS.SETTINGS))

    assert resp.status_code == 200

    # Distinct values catch a swapped card; tags_created==7, tags_applied==11,
    # urls_added==5 double as the noise-exclusion assertions (a user-2 tag, a
    # user-2 URL, and a NULL-attributed applied-tag row were also seeded).
    # member-of==4 confirms a CO_CREATOR membership counts (only CREATOR is
    # excluded by the filter).
    expected_card_values = {
        "utubs-created": b">2</dd>",
        "member-of": b">4</dd>",
        "urls-added": b">5</dd>",
        "tags-created": b">7</dd>",
        "tags-applied": b">11</dd>",
    }
    for stat_name, expected_value in expected_card_values.items():
        card_slice = _slice_stat_card(resp.data, stat_name)
        assert (
            expected_value in card_slice
        ), f"{stat_name} card missing {expected_value!r}: {card_slice!r}"


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
