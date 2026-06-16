from __future__ import annotations

import pytest
from flask import Flask
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from backend.config import ConfigTestUI
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS
from tests.functional.locators import SettingsPageLocators as SPL
from tests.functional.selenium_utils import (
    click_on_navbar,
    wait_for_element_presence,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_in_focus,
)
from tests.functional.settings_ui.selenium_utils import (
    login_user_and_open_home,
    login_user_and_open_settings,
)

pytestmark = pytest.mark.settings_ui

DEFAULT_USER_ID: int = 1
URL_CONTAINS_TIMEOUT_SECONDS: int = 10


def test_account_tab_is_default(
    browser: WebDriver,
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
        browser=browser,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    account_tab = wait_then_get_element(browser, SPL.TAB_ACCOUNT_BUTTON, time=5)
    assert account_tab is not None
    assert account_tab.get_attribute("aria-selected") == "true"

    account_panel = wait_then_get_element(browser, SPL.PANEL_ACCOUNT, time=5)
    assert account_panel is not None
    assert account_panel.is_displayed()


def test_click_stats_tab_switches_panel(
    browser: WebDriver,
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
        browser=browser,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    wait_then_click_element(browser, SPL.TAB_STATS_BUTTON, time=5)

    stats_tab = wait_then_get_element(browser, SPL.TAB_STATS_BUTTON, time=5)
    assert stats_tab is not None
    assert stats_tab.get_attribute("aria-selected") == "true"

    stats_panel = wait_then_get_element(browser, SPL.PANEL_STATS, time=5)
    assert stats_panel is not None
    assert stats_panel.is_displayed()

    account_panel = browser.find_element(By.CSS_SELECTOR, SPL.PANEL_ACCOUNT)
    assert account_panel.get_attribute("hidden") is not None

    stats_heading = stats_panel.find_element(By.CSS_SELECTOR, "h2")
    assert stats_heading.text == UI_TEST_STRINGS.SETTINGS_TAB_STATS


def test_page_title_renders(
    browser: WebDriver,
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
        browser=browser,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    page_title = wait_then_get_element(browser, f"{SPL.PAGE_ROOT} h1", time=5)
    assert page_title is not None
    assert page_title.text == UI_TEST_STRINGS.SETTINGS_PAGE_TITLE


def test_back_home_btn_navigates_to_home(
    browser: WebDriver,
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
        browser=browser,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    # The back-home button lives inside the always-collapsed navbar
    # dropdown; open the hamburger before the button is clickable.
    click_on_navbar(browser)
    wait_then_click_element(browser, SPL.BACK_HOME_BTN, time=5)

    WebDriverWait(browser, timeout=URL_CONTAINS_TIMEOUT_SECONDS).until(
        EC.url_contains("/home")
    )
    assert browser.current_url.endswith("/home")


def test_settings_nav_link_present_on_home(
    browser: WebDriver,
    provide_app: Flask,
    provide_port: int,
    provide_config: ConfigTestUI,
):
    """
    GIVEN a logged-in user on the authenticated home page
    WHEN the navbar renders
    THEN the Settings nav link (`#userSettingsLink`, added in Step 4) is
        present — proving it is reachable from the home page.

    Cross-page dependency note: this test exercises the home page nav,
    not the settings page.
    """
    login_user_and_open_home(
        app=provide_app,
        browser=browser,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    nav_link = wait_for_element_presence(browser, SPL.SETTINGS_NAV_LINK, timeout=10)
    assert nav_link is not None


def test_arrow_key_navigates_tabs(
    browser: WebDriver,
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
        browser=browser,
        port=provide_port,
        user_id=DEFAULT_USER_ID,
        config=provide_config,
    )

    account_tab = wait_then_get_element(browser, SPL.TAB_ACCOUNT_BUTTON, time=5)
    assert account_tab is not None
    assert account_tab.get_attribute("aria-selected") == "true"
    # Click activates the Account tab; the controller focuses the Account
    # panel on mouse activation. Wait for that focus to land as a barrier
    # confirming the click handler ran before sending the key. send_keys
    # then re-focuses the tab button itself, delivering the keydown to the
    # bound listener.
    account_tab.click()
    wait_until_in_focus(browser, SPL.PANEL_ACCOUNT)
    account_tab.send_keys(Keys.ARROW_RIGHT)

    stats_tab = wait_then_get_element(browser, SPL.TAB_STATS_BUTTON, time=5)
    assert stats_tab is not None
    WebDriverWait(browser, timeout=5).until(
        lambda driver: driver.find_element(
            By.CSS_SELECTOR, SPL.TAB_STATS_BUTTON
        ).get_attribute("aria-selected")
        == "true"
    )
