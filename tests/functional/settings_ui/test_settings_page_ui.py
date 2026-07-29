from __future__ import annotations

import re

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend import db
from backend.config import ConfigTestUI
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from backend.utils.strings.user_strs import USER_FAILURE
from tests.functional.locators import SettingsPageLocators as SPL
from tests.functional.playwright_utils import (
    click_on_navbar,
    wait_for_element_presence,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_in_focus,
)
from tests.functional.settings_ui.playwright_utils import (
    login_user_and_open_home,
    login_user_and_open_settings,
)
from tests.utils_for_test import seed_distinct_stats_for_user_one

pytestmark = pytest.mark.settings_ui

DEFAULT_USER_ID: int = 1

_OAUTH_ONLY_USERNAME = "settingspwoauthonlyui"
_OAUTH_ONLY_EMAIL = "settingspwoauthonlyui@example.com"
_OAUTH_ONLY_GOOGLE_SUBJECT = "fake-google-subject-settings-pw-oauth-only"


def _seed_oauth_only_user(app: Flask) -> int:
    """Create and commit a password-less user with one linked google identity,
    returning its id — a local helper scoped to this module (independent of the
    similarly-named helpers in other test modules). Used to prove the
    change-password form is not rendered for OAuth-only accounts."""
    with app.app_context():
        user = Users(
            username=_OAUTH_ONLY_USERNAME,
            email=_OAUTH_ONLY_EMAIL,
            plaintext_password=None,
        )
        user.oauth_identities.append(
            UserOAuthIdentity(
                provider="google", provider_subject=_OAUTH_ONLY_GOOGLE_SUBJECT
            )
        )
        user.email_validated = True
        db.session.add(user)
        db.session.commit()
        return user.id


def _seed_distinct_stats_for_user_one(app: Flask) -> None:
    """Seed mutually-distinct per-user activity counts for user 1 so each
    Stats card renders a unique value (2/3/5/7/11) and a swapped card is
    caught. Users 1-5 already exist (seeded by the `seeded_users` autouse
    fixture via `flask addmock users`). Delegates the shared 2/3/5/7/11 seed
    block to `seed_distinct_stats_for_user_one`, using a UI-specific label
    prefix to keep this test's URL/tag strings distinct from other callers'."""
    with app.app_context():
        seed_distinct_stats_for_user_one(label_prefix="user1-ui")
        db.session.commit()


def test_account_tab_is_default(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in, email-validated user
    WHEN the user opens `/settings`
    THEN the Account tab is selected by default and its panel is displayed.
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    expect(page.locator(SPL.TAB_ACCOUNT_BUTTON)).to_have_attribute(
        "aria-selected", "true"
    )
    expect(page.locator(SPL.PANEL_ACCOUNT)).to_be_visible()


def test_click_stats_tab_switches_panel(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in user on the settings page with the Account tab active
    WHEN the user clicks the Stats tab
    THEN the Stats tab becomes selected, the Stats panel is shown, the
        Account panel gains the `hidden` attribute, and the Stats panel
        heading renders the localized Stats label.
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(page=page, css_selector=SPL.TAB_STATS_BUTTON)

    expect(page.locator(SPL.TAB_STATS_BUTTON)).to_have_attribute(
        "aria-selected", "true"
    )
    expect(page.locator(SPL.PANEL_STATS)).to_be_visible()

    # Attribute-exact check mirroring the Selenium
    # `get_attribute("hidden") is not None` assertion — a present-but-
    # valueless HTML attribute reads as "".
    expect(page.locator(SPL.PANEL_ACCOUNT)).to_have_attribute("hidden", "")

    stats_heading = page.locator(SPL.PANEL_STATS).locator("h2")
    expect(stats_heading).to_have_text(UI_TEST_STRINGS.SETTINGS_TAB_STATS)


def test_page_title_renders(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in user
    WHEN the user opens `/settings`
    THEN the page `<h1>` renders the localized Settings page title.
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    page_title = wait_then_get_element(page=page, css_selector=f"{SPL.PAGE_ROOT} h1")
    expect(page_title).to_have_text(UI_TEST_STRINGS.SETTINGS_PAGE_TITLE)


def test_back_home_btn_navigates_to_home(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in user on the settings page
    WHEN the user clicks the Back-to-Home control
    THEN the browser navigates to the authenticated home page.
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    # The back-home button lives inside the always-collapsed navbar
    # dropdown; open the hamburger before the button is clickable.
    click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=SPL.BACK_HOME_BTN)

    expect(page).to_have_url(re.compile(r"/home$"))


def test_settings_nav_link_present_on_home(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in user on the authenticated home page
    WHEN the navbar renders
    THEN the Settings nav link (`#userSettingsLink`) rendered in the home
        navbar dropdown is present — proving it is reachable from the home page.

    Cross-page dependency note: this test exercises the home page nav,
    not the settings page.
    """
    login_user_and_open_home(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    # DOM presence, not visibility — the link is in a collapsed dropdown.
    wait_for_element_presence(page=page, css_selector=SPL.SETTINGS_NAV_LINK)


def test_arrow_key_navigates_tabs(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in user on the settings page with the Account tab focused
    WHEN the user presses ArrowRight
    THEN the Stats tab becomes selected (roving-tabindex keyboard nav).
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    account_tab = page.locator(SPL.TAB_ACCOUNT_BUTTON)
    expect(account_tab).to_have_attribute("aria-selected", "true")
    # Click activates the Account tab; the controller focuses the Account
    # panel on mouse activation. Wait for that focus to land as a barrier
    # confirming the click handler ran before sending the key. press()
    # then re-focuses the tab button itself, delivering the keydown to the
    # bound listener.
    account_tab.click()
    wait_until_in_focus(page=page, css_selector=SPL.PANEL_ACCOUNT)
    account_tab.press("ArrowRight")

    expect(page.locator(SPL.TAB_STATS_BUTTON)).to_have_attribute(
        "aria-selected", "true"
    )


def test_account_info_renders_on_default_tab(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in, email-validated user
    WHEN the user opens `/settings` (Account tab is default)
    THEN the read-only account-info block renders the user's username and email
        values and the verified email indicator, without switching tabs.
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    expect(page.locator(SPL.PANEL_ACCOUNT)).to_be_visible()
    expect(page.locator(SPL.ACCOUNT_INFO_USERNAME_VALUE)).to_have_text(
        UI_TEST_STRINGS.TEST_USERNAME_1
    )
    expect(page.locator(SPL.ACCOUNT_INFO_EMAIL_VALUE)).to_have_text(
        UI_TEST_STRINGS.TEST_PASSWORD_1
    )
    expect(page.locator(SPL.ACCOUNT_INFO_EMAIL_STATUS)).to_contain_text(
        UI_TEST_STRINGS.SETTINGS_ACCOUNT_EMAIL_VERIFIED
    )


def test_stats_panel_renders_seeded_counts(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in user with mutually-distinct seeded activity counts
        (2 UTubs created / member of 3 / 5 URLs / 7 tags created / 11 applied)
    WHEN the user opens `/settings` and clicks the Stats tab
    THEN each stat card renders its own seeded value — so a swapped or
        mislabeled card is caught by the per-card assertions.
    """
    _seed_distinct_stats_for_user_one(provide_app)

    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(page=page, css_selector=SPL.TAB_STATS_BUTTON)
    expect(page.locator(SPL.PANEL_STATS)).to_be_visible()

    expect(page.locator(SPL.STAT_UTUBS_CREATED)).to_have_text("2")
    expect(page.locator(SPL.STAT_MEMBER_OF)).to_have_text("3")
    expect(page.locator(SPL.STAT_URLS_ADDED)).to_have_text("5")
    expect(page.locator(SPL.STAT_TAGS_CREATED)).to_have_text("7")
    expect(page.locator(SPL.STAT_TAGS_APPLIED)).to_have_text("11")


def test_change_username_happy_path_updates_in_place(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in user on the settings Account tab
    WHEN they open the (collapsed-by-default) form, enter a new, unique username
        and click Save
    THEN the success banner is shown and the input, the read-only account-info
        username card, AND the navbar "Logged in as" label all update in place
        (no page reload).
    """
    new_username = "renamed_ui_user"

    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    # The change-username form defaults to collapsed; open the disclosure first.
    wait_then_click_element(page=page, css_selector=SPL.CHANGE_USERNAME_SUMMARY)
    page.fill(SPL.CHANGE_USERNAME_INPUT, new_username)
    wait_then_click_element(page=page, css_selector=SPL.CHANGE_USERNAME_BTN)

    status = page.locator(SPL.USERNAME_STATUS)
    expect(status).to_be_visible()
    expect(status).to_have_text(UI_TEST_STRINGS.SETTINGS_USERNAME_CHANGE_SUCCESS)

    # Update-in-place (DD-15): every display reflects the new username, including
    # the navbar "Logged in as" label.
    expect(page.locator(SPL.CHANGE_USERNAME_INPUT)).to_have_value(new_username)
    expect(page.locator(SPL.ACCOUNT_INFO_USERNAME_VALUE)).to_have_text(new_username)
    expect(page.locator(SPL.NAV_LOGGED_IN_AS_USERNAME)).to_have_text(new_username)


def test_change_username_duplicate_name_shows_field_error(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in user on the settings Account tab
    WHEN they try to rename to a username already taken by another account
    THEN a field-level error is shown on the input and the read-only
        account-info username card is unchanged.
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    # The change-username form defaults to collapsed; open the disclosure first.
    wait_then_click_element(page=page, css_selector=SPL.CHANGE_USERNAME_SUMMARY)
    page.fill(SPL.CHANGE_USERNAME_INPUT, UI_TEST_STRINGS.TEST_USERNAME_2)
    wait_then_click_element(page=page, css_selector=SPL.CHANGE_USERNAME_BTN)

    feedback = page.locator(SPL.USERNAME_INVALID_FEEDBACK)
    expect(feedback).to_have_text(USER_FAILURE.USERNAME_TAKEN)
    # The read-only card still shows the original username.
    expect(page.locator(SPL.ACCOUNT_INFO_USERNAME_VALUE)).to_have_text(
        UI_TEST_STRINGS.TEST_USERNAME_1
    )


def test_change_password_happy_path_shows_success_banner(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in local-password user on the settings Account tab
    WHEN they open the (collapsed-by-default) form, enter the correct current
        password and a valid new password (twice) and click Save
    THEN the success banner is shown.
    """
    new_password = "BrandNewPassword5678"

    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    # The change-password form defaults to collapsed; open the disclosure first.
    wait_then_click_element(page=page, css_selector=SPL.CHANGE_PASSWORD_SUMMARY)
    page.fill(SPL.CHANGE_PASSWORD_CURRENT_INPUT, UI_TEST_STRINGS.TEST_PASSWORD_1)
    page.fill(SPL.CHANGE_PASSWORD_NEW_INPUT, new_password)
    page.fill(SPL.CHANGE_PASSWORD_CONFIRM_INPUT, new_password)
    wait_then_click_element(page=page, css_selector=SPL.CHANGE_PASSWORD_BTN)

    status = page.locator(SPL.PASSWORD_STATUS)
    expect(status).to_be_visible()
    expect(status).to_have_text(UI_TEST_STRINGS.SETTINGS_PASSWORD_CHANGE_SUCCESS)


def test_change_password_form_absent_for_oauth_only_user(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in OAuth-only (password-less) user on the settings Account tab
    WHEN the page renders
    THEN the change-password form controls are NOT rendered, and the OAuth-only
        explanatory note is shown in their place.
    """
    oauth_only_user_id = _seed_oauth_only_user(provide_app)

    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=oauth_only_user_id,
        config=provide_config,
    )

    expect(page.locator(SPL.PANEL_ACCOUNT)).to_be_visible()
    # The form controls are gated out entirely for OAuth-only accounts.
    expect(page.locator(SPL.CHANGE_PASSWORD_CURRENT_INPUT)).to_have_count(0)
    expect(page.locator(SPL.CHANGE_PASSWORD_BTN)).to_have_count(0)
    # The explanatory note renders in their place.
    expect(page.locator(SPL.CHANGE_PASSWORD_OAUTH_NOTE)).to_be_visible()


def test_account_forms_default_collapsed(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in local-password user on the settings Account tab
    WHEN the page renders
    THEN the change-username and change-password forms are collapsed by default
        (their inputs are hidden) and become visible only after their disclosure
        summary is clicked.
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    # Rendered in the DOM but hidden while the <details> is closed.
    expect(page.locator(SPL.CHANGE_USERNAME_INPUT)).to_be_hidden()
    expect(page.locator(SPL.CHANGE_PASSWORD_CURRENT_INPUT)).to_be_hidden()

    # Opening each disclosure reveals its fields.
    wait_then_click_element(page=page, css_selector=SPL.CHANGE_USERNAME_SUMMARY)
    expect(page.locator(SPL.CHANGE_USERNAME_INPUT)).to_be_visible()

    wait_then_click_element(page=page, css_selector=SPL.CHANGE_PASSWORD_SUMMARY)
    expect(page.locator(SPL.CHANGE_PASSWORD_CURRENT_INPUT)).to_be_visible()
