from __future__ import annotations

import re

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend import db
from backend.cli.mock_constants import EMAIL_SUFFIX
from backend.config import ConfigTestUI
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.utils.strings.splash_form_strs import EMAILS_NOT_IDENTICAL
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from backend.utils.strings.user_strs import EMAIL_CHANGE_CONFIRMATION_SENT, USER_FAILURE
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

# `flask addmock users` promotes user 1 (`u4i_test1`) to the sole ADMIN role, so
# a self delete by user 1 is blocked by the sole-admin guard
# (`reject_self_sole_admin`, guard step 2 — ahead of the password check). The
# actual-submit delete/logout-everywhere tests therefore act as a NON-admin user
# (user 2), whose seeded password follows the seeder's `plaintext_password =
# email = username + EMAIL_SUFFIX` convention.
_NON_ADMIN_USER_ID: int = 2
_NON_ADMIN_PASSWORD: str = UI_TEST_STRINGS.TEST_USERNAME_2 + EMAIL_SUFFIX

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
    expect(page.locator(SPL.CHANGE_EMAIL_NEW_INPUT)).to_be_hidden()

    # Opening each disclosure reveals its fields.
    wait_then_click_element(page=page, css_selector=SPL.CHANGE_USERNAME_SUMMARY)
    expect(page.locator(SPL.CHANGE_USERNAME_INPUT)).to_be_visible()

    wait_then_click_element(page=page, css_selector=SPL.CHANGE_PASSWORD_SUMMARY)
    expect(page.locator(SPL.CHANGE_PASSWORD_CURRENT_INPUT)).to_be_visible()

    wait_then_click_element(page=page, css_selector=SPL.CHANGE_EMAIL_SUMMARY)
    expect(page.locator(SPL.CHANGE_EMAIL_NEW_INPUT)).to_be_visible()


_TAKEN_TARGET_USERNAME = "changeemailtakentarget"
_TAKEN_TARGET_EMAIL = "already.taken.ui@example.com"


def _seed_user_with_email(app: Flask, *, username: str, email: str) -> None:
    """Create a committed password user owning ``email`` — used as the
    already-taken target for the change-email uniqueness field-error test."""
    with app.app_context():
        user = Users(username=username, email=email, plaintext_password="Sup3rSecret!1")
        user.email_validated = True
        db.session.add(user)
        db.session.commit()


def _seed_pending_email(app: Flask, *, user_id: int, pending_email: str) -> None:
    """Stage a not-yet-confirmed pending email on ``user_id`` so the settings
    page's server-rendered pending-change notices (DD-6 / DD-16) render. Uses the
    model's ``stage_email_change`` helper (same path the START endpoint uses), not
    a raw column write, for parity with how pending state is really produced."""
    with app.app_context():
        user = Users.query.get(user_id)
        user.stage_email_change(pending_email)
        db.session.commit()


def test_change_email_happy_path_shows_confirmation_banner(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in local-password user on the settings Account tab
    WHEN they open the (collapsed-by-default) change-email form, enter a new,
        unused email (twice) plus their correct current password and click Save
    THEN the "confirmation sent" banner is shown AND the read-only account-info
        email card is UNCHANGED — the live email is not swapped until the user
        opens the confirmation link (Approach B: stay on the page).
    """
    new_email = "brand.new.ui.email@example.com"

    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(page=page, css_selector=SPL.CHANGE_EMAIL_SUMMARY)
    page.fill(SPL.CHANGE_EMAIL_NEW_INPUT, new_email)
    page.fill(SPL.CHANGE_EMAIL_CONFIRM_INPUT, new_email)
    page.fill(SPL.CHANGE_EMAIL_CURRENT_PASSWORD_INPUT, UI_TEST_STRINGS.TEST_PASSWORD_1)
    wait_then_click_element(page=page, css_selector=SPL.CHANGE_EMAIL_BTN)

    status = page.locator(SPL.EMAIL_STATUS)
    expect(status).to_be_visible()
    expect(status).to_have_text(EMAIL_CHANGE_CONFIRMATION_SENT)

    # Live email card stays on the current (unswapped) address.
    expect(page.locator(SPL.ACCOUNT_INFO_EMAIL_VALUE)).to_have_text(
        UI_TEST_STRINGS.TEST_PASSWORD_1
    )


def test_change_email_taken_email_shows_field_error(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in user and a second account already owning an email
    WHEN the user tries to change to that already-taken email
    THEN a field-level error is shown on the new-email input and the live
        account-info email card is unchanged.
    """
    _seed_user_with_email(
        provide_app, username=_TAKEN_TARGET_USERNAME, email=_TAKEN_TARGET_EMAIL
    )

    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(page=page, css_selector=SPL.CHANGE_EMAIL_SUMMARY)
    page.fill(SPL.CHANGE_EMAIL_NEW_INPUT, _TAKEN_TARGET_EMAIL)
    page.fill(SPL.CHANGE_EMAIL_CONFIRM_INPUT, _TAKEN_TARGET_EMAIL)
    page.fill(SPL.CHANGE_EMAIL_CURRENT_PASSWORD_INPUT, UI_TEST_STRINGS.TEST_PASSWORD_1)
    wait_then_click_element(page=page, css_selector=SPL.CHANGE_EMAIL_BTN)

    feedback = page.locator(SPL.EMAIL_INVALID_FEEDBACK)
    expect(feedback).to_have_text(USER_FAILURE.EMAIL_TAKEN)
    expect(page.locator(SPL.ACCOUNT_INFO_EMAIL_VALUE)).to_have_text(
        UI_TEST_STRINGS.TEST_PASSWORD_1
    )


def test_change_email_invalid_email_shows_field_error(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in user on the settings Account tab
    WHEN they submit a malformed new email (the button is type=button, so the
        request reaches the server and its EmailStr validation rejects it)
    THEN a field-level error is shown on the new-email input and no success
        banner appears.
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(page=page, css_selector=SPL.CHANGE_EMAIL_SUMMARY)
    page.fill(SPL.CHANGE_EMAIL_NEW_INPUT, "not-a-valid-email")
    page.fill(SPL.CHANGE_EMAIL_CONFIRM_INPUT, "not-a-valid-email")
    page.fill(SPL.CHANGE_EMAIL_CURRENT_PASSWORD_INPUT, UI_TEST_STRINGS.TEST_PASSWORD_1)
    wait_then_click_element(page=page, css_selector=SPL.CHANGE_EMAIL_BTN)

    expect(page.locator(SPL.EMAIL_INVALID_FEEDBACK)).to_be_visible()
    expect(page.locator(SPL.EMAIL_STATUS)).not_to_have_class(
        re.compile(r"alert-success")
    )


def test_change_email_confirm_mismatch_shows_field_error(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in user on the settings Account tab (DD-8)
    WHEN they enter a new email but a DIFFERENT confirm email
    THEN a field-level "emails do not match" error is shown on the confirm
        input, no success banner appears, and the live email card is unchanged.
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(page=page, css_selector=SPL.CHANGE_EMAIL_SUMMARY)
    page.fill(SPL.CHANGE_EMAIL_NEW_INPUT, "typed.one.ui@example.com")
    page.fill(SPL.CHANGE_EMAIL_CONFIRM_INPUT, "typed.two.ui@example.com")
    page.fill(SPL.CHANGE_EMAIL_CURRENT_PASSWORD_INPUT, UI_TEST_STRINGS.TEST_PASSWORD_1)
    wait_then_click_element(page=page, css_selector=SPL.CHANGE_EMAIL_BTN)

    feedback = page.locator(SPL.CHANGE_EMAIL_CONFIRM_INVALID_FEEDBACK)
    expect(feedback).to_have_text(EMAILS_NOT_IDENTICAL)
    expect(page.locator(SPL.EMAIL_STATUS)).not_to_have_class(
        re.compile(r"alert-success")
    )
    expect(page.locator(SPL.ACCOUNT_INFO_EMAIL_VALUE)).to_have_text(
        UI_TEST_STRINGS.TEST_PASSWORD_1
    )


def test_change_email_form_absent_for_oauth_only_user(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in OAuth-only (password-less) user on the settings Account tab
    WHEN the page renders (DD-7)
    THEN the change-email form controls are NOT rendered, the OAuth-only note is
        shown as a PLAIN paragraph (no collapsible <details>/<summary>), matching
        the change-password OAuth-only fallback shape.
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
    # Form controls gated out entirely for OAuth-only accounts.
    expect(page.locator(SPL.CHANGE_EMAIL_NEW_INPUT)).to_have_count(0)
    expect(page.locator(SPL.CHANGE_EMAIL_BTN)).to_have_count(0)
    # DD-7: the OAuth-only note is a plain <div>, never a <details>/<summary>.
    expect(page.locator(SPL.CHANGE_EMAIL_DETAILS)).to_have_count(0)
    expect(page.locator(SPL.CHANGE_EMAIL_SUMMARY)).to_have_count(0)
    expect(page.locator(SPL.CHANGE_EMAIL_OAUTH_NOTE)).to_be_visible()


def test_change_email_pending_warning_visible_when_pending(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in user who already has a pending email change staged
        (DD-16 in-form warning + DD-6 account-info pending note)
    WHEN they view the Account tab and open the change-email disclosure
    THEN the account-info pending note renders the staged address (DD-6) and the
        in-form pending-change warning is visible with the DD-16 copy.
    """
    pending_email = "pending.ui@example.com"
    _seed_pending_email(
        provide_app, user_id=DEFAULT_USER_ID, pending_email=pending_email
    )

    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    # DD-6: the account-info card's pending note is server-rendered (outside the
    # disclosure) with the staged address.
    account_note = page.locator(SPL.ACCOUNT_PENDING_EMAIL_NOTE)
    expect(account_note).to_be_visible()
    expect(account_note).to_have_text(
        UI_TEST_STRINGS.SETTINGS_ACCOUNT_PENDING_EMAIL_INITIAL_NOTE.format(
            email=pending_email
        )
    )

    # DD-16: the in-form warning renders inside the change-email disclosure.
    wait_then_click_element(page=page, css_selector=SPL.CHANGE_EMAIL_SUMMARY)
    warning = page.locator(SPL.CHANGE_EMAIL_PENDING_WARNING)
    expect(warning).to_be_visible()
    expect(warning).to_have_text(UI_TEST_STRINGS.SETTINGS_CHANGE_EMAIL_PENDING_WARNING)


def test_change_email_pending_warning_absent_when_no_pending(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in user with NO pending email change (DD-16)
    WHEN they open the change-email disclosure
    THEN the in-form pending-change warning is not rendered at all (the
        `{% if account_pending_email %}` gate omits it from the DOM).
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(page=page, css_selector=SPL.CHANGE_EMAIL_SUMMARY)
    expect(page.locator(SPL.CHANGE_EMAIL_PENDING_WARNING)).to_have_count(0)


# ---------------------------------------------------------------------------
# Account tab — self-service session-revocation ("Log out everywhere") + the
# irreversible Delete flow.
#
# End-to-end UI coverage against the built app. The happy paths assert the
# post-logout redirect to the splash page (`/`); the gate paths assert the
# in-modal behavior (typed-username gate, focus return, field-clear on dismiss).
# These exercise the real Bootstrap `hidden.bs.modal` lifecycle end to end —
# something the `_resetAccountRemovalForTests()`-mocked Vitest suite, running
# against a synthetic HTML fixture, cannot catch.
# ---------------------------------------------------------------------------

# The client navigates to the splash page (`/`, ROUTES.SPLASH.SPLASH_PAGE) after
# a successful logout-everywhere/delete logs the acting session out. Matches
# `scheme://host:port/` exactly — the settings URL (`.../settings`, no trailing
# slash) never matches.
_SPLASH_ROOT_URL = re.compile(r"://[^/]+/$")


def _current_username(page: Page) -> str:
    """Read the logged-in user's username from the account-info card — the exact
    text the delete modal's typed-confirmation gate compares against (a DOM read,
    mirroring account-removal.ts's `USERNAME_VALUE_SELECTOR`)."""
    return page.locator(SPL.ACCOUNT_INFO_USERNAME_VALUE).inner_text().strip()


def test_logout_everywhere_happy_path_redirects_to_splash(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in user on the settings Account tab
    WHEN they open the "Log out everywhere" modal and click Confirm (no typed
        username or password fields — the flow is non-destructive, D-1)
    THEN the acting session is logged out and the browser navigates to the
        splash page.
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=_NON_ADMIN_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(page=page, css_selector=SPL.LOGOUT_EVERYWHERE_TRIGGER)
    expect(page.locator(SPL.LOGOUT_EVERYWHERE_MODAL)).to_be_visible()
    wait_then_click_element(page=page, css_selector=SPL.LOGOUT_EVERYWHERE_SUBMIT_BTN)

    expect(page).to_have_url(_SPLASH_ROOT_URL)


def test_delete_happy_path_redirects_to_splash(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in local-password user on the settings Account tab
    WHEN they open the Delete modal, type their exact username, enter their
        correct current password, and click Delete
    THEN the account is erased, the acting session is logged out, and the
        browser navigates to the splash page.
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=_NON_ADMIN_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(page=page, css_selector=SPL.DELETE_TRIGGER)
    expect(page.locator(SPL.DELETE_MODAL)).to_be_visible()

    username = _current_username(page)
    # press_sequentially fires the keyup the DD-8 gate listens on (fill() does
    # not), so the disabled submit re-enables once username matches AND password
    # is non-empty.
    page.locator(SPL.DELETE_CONFIRM_USERNAME_INPUT).press_sequentially(username)
    page.locator(SPL.DELETE_CURRENT_PASSWORD_INPUT).press_sequentially(
        _NON_ADMIN_PASSWORD
    )

    submit = page.locator(SPL.DELETE_SUBMIT_BTN)
    expect(submit).to_be_enabled()
    submit.click()

    expect(page).to_have_url(_SPLASH_ROOT_URL)


def test_delete_typed_confirmation_gates_submit(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in local-password user with the Delete modal open
    WHEN the typed username does not exactly match their own (or the password is
        empty)
    THEN the Delete submit button stays disabled, becoming enabled only once the
        exact username is typed AND a password is present (DD-C / DD-8).
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(page=page, css_selector=SPL.DELETE_TRIGGER)
    expect(page.locator(SPL.DELETE_MODAL)).to_be_visible()

    submit = page.locator(SPL.DELETE_SUBMIT_BTN)
    # Disabled on open (no confirmation typed yet).
    expect(submit).to_be_disabled()

    # A wrong username keeps it disabled even with a password present.
    username = _current_username(page)
    page.locator(SPL.DELETE_CONFIRM_USERNAME_INPUT).press_sequentially(
        username + "-nope"
    )
    page.locator(SPL.DELETE_CURRENT_PASSWORD_INPUT).press_sequentially(
        UI_TEST_STRINGS.TEST_PASSWORD_1
    )
    expect(submit).to_be_disabled()

    # Correcting the username to the exact match enables the submit.
    page.locator(SPL.DELETE_CONFIRM_USERNAME_INPUT).fill("")
    page.locator(SPL.DELETE_CONFIRM_USERNAME_INPUT).press_sequentially(username)
    expect(submit).to_be_enabled()


@pytest.mark.parametrize(
    "trigger_selector, modal_selector, cancel_selector",
    [
        pytest.param(
            SPL.DELETE_TRIGGER,
            SPL.DELETE_MODAL,
            SPL.DELETE_CANCEL_BTN,
            id="delete-modal",
        ),
        pytest.param(
            SPL.LOGOUT_EVERYWHERE_TRIGGER,
            SPL.LOGOUT_EVERYWHERE_MODAL,
            SPL.LOGOUT_EVERYWHERE_CANCEL_BTN,
            id="logout-everywhere-modal",
        ),
    ],
)
def test_removal_modal_focus_returns_to_trigger_on_cancel(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    trigger_selector: str,
    modal_selector: str,
    cancel_selector: str,
):
    """
    GIVEN a logged-in user who opened one of the settings modals (Delete or
        Log out everywhere)
    WHEN they dismiss it with the Cancel button
    THEN keyboard focus returns to the trigger that opened it.
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(page=page, css_selector=trigger_selector)
    expect(page.locator(modal_selector)).to_be_visible()
    wait_then_click_element(page=page, css_selector=cancel_selector)
    expect(page.locator(modal_selector)).to_be_hidden()

    wait_until_in_focus(page=page, css_selector=trigger_selector)


@pytest.mark.parametrize(
    "trigger_selector, modal_selector, cancel_selector, field_selectors",
    [
        pytest.param(
            SPL.DELETE_TRIGGER,
            SPL.DELETE_MODAL,
            SPL.DELETE_CANCEL_BTN,
            (SPL.DELETE_CONFIRM_USERNAME_INPUT, SPL.DELETE_CURRENT_PASSWORD_INPUT),
            id="delete-modal-two-fields",
        ),
    ],
)
def test_removal_modal_clears_fields_on_dismiss(
    page: Page,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
    trigger_selector: str,
    modal_selector: str,
    cancel_selector: str,
    field_selectors: tuple[str, ...],
):
    """
    GIVEN a logged-in local-password user with the Delete modal (the only
        removal modal carrying input fields — Log out everywhere has none)
    WHEN they type into every field of the modal, dismiss it, then reopen it
    THEN every one of that modal's fields renders empty (DD-7 field-clear on the
        real `hidden.bs.modal` lifecycle — Cancel/Escape/backdrop all fire it).
    """
    login_user_and_open_settings(
        app=provide_app,
        context=page.context,
        page=page,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(page=page, css_selector=trigger_selector)
    expect(page.locator(modal_selector)).to_be_visible()
    for field_selector in field_selectors:
        page.fill(field_selector, "scratch-value-to-be-cleared")

    wait_then_click_element(page=page, css_selector=cancel_selector)
    expect(page.locator(modal_selector)).to_be_hidden()

    # Reopen and confirm every field was cleared by the dismissal.
    wait_then_click_element(page=page, css_selector=trigger_selector)
    expect(page.locator(modal_selector)).to_be_visible()
    for field_selector in field_selectors:
        expect(page.locator(field_selector)).to_have_value("")
