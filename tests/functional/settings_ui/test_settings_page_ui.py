from __future__ import annotations

import re

import pytest
from flask import Flask
from playwright.sync_api import Page, expect

from backend.config import ConfigTestUI
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
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

pytestmark = pytest.mark.settings_ui

DEFAULT_USER_ID: int = 1


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
