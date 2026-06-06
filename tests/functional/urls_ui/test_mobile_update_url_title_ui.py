from typing import Tuple

from flask import Flask
from flask.testing import FlaskCliRunner
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from backend.models.utubs import Utubs
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.assert_utils import assert_panel_visibility_mobile
from tests.functional.db_utils import (
    add_mock_urls,
    get_url_in_utub,
    get_utub_this_user_created,
    get_utub_this_user_did_not_create,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import login_user_and_select_utub_by_utubid_mobile
from tests.functional.selenium_utils import (
    Decks,
    get_selected_url,
    wait_then_click_element,
    wait_until_visible_css_selector,
)

pytestmark = pytest.mark.mobile_ui


def _select_first_url_in_utub_mobile(
    browser: WebDriver, app: Flask, utub_id: int
) -> WebElement:
    """Select the first URL in the UTub and return the selected URL WebElement."""
    utub_url = get_url_in_utub(app, utub_id)
    wait_then_click_element(browser, f"{HPL.ROWS_URLS}[utuburlid='{utub_url.id}']")
    return get_selected_url(browser)


def test_url_title_pencil_visible_on_selected_url_mobile(
    browser_mobile_portrait: WebDriver,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests that the URL title pencil icon becomes visible when a URL card is selected
    on a mobile (coarse-pointer) device.

    GIVEN a user views a UTub on a mobile device
    WHEN the user taps on a URL card to select it
    THEN ensure the URL title pencil icon is visible on the selected card
    """
    browser = browser_mobile_portrait
    app = provide_app
    user_id_for_test = 1
    _, cli_runner = runner
    add_mock_urls(cli_runner, [UTS.TEST_URL_STRING_CREATE])
    utub: Utubs = get_utub_this_user_created(app, user_id=user_id_for_test)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, utub_id=utub.id, user_id=user_id_for_test
    )
    assert_panel_visibility_mobile(browser=browser, visible_deck=Decks.URLS)

    # Before-state: pencil is NOT visible on any unselected card.
    pencil_elements = browser.find_elements(
        By.CSS_SELECTOR, f"{HPL.ROWS_URLS} {HPL.BUTTON_URL_TITLE_UPDATE}"
    )
    assert all(not element.is_displayed() for element in pencil_elements)

    _select_first_url_in_utub_mobile(browser, app, utub.id)

    # After-state: pencil IS visible on the selected card.
    wait_until_visible_css_selector(
        browser,
        f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_TITLE_UPDATE}",
        timeout=3,
    )


def test_url_title_pencil_tap_opens_edit_form_mobile(
    browser_mobile_portrait: WebDriver,
    create_test_utubs,
    runner: Tuple[Flask, FlaskCliRunner],
    provide_app: Flask,
):
    """
    Tests that tapping the URL title pencil on a mobile device opens the title edit
    form without deselecting the URL card.

    GIVEN a user has a URL card selected on a mobile device
    WHEN the user taps the URL title pencil icon
    THEN ensure the URL title edit input is visible and the card remains selected
    """
    browser = browser_mobile_portrait
    app = provide_app
    user_id_for_test = 1
    _, cli_runner = runner
    add_mock_urls(cli_runner, [UTS.TEST_URL_STRING_CREATE])
    utub: Utubs = get_utub_this_user_created(app, user_id=user_id_for_test)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, utub_id=utub.id, user_id=user_id_for_test
    )
    assert_panel_visibility_mobile(browser=browser, visible_deck=Decks.URLS)

    _select_first_url_in_utub_mobile(browser, app, utub.id)

    pencil_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_TITLE_UPDATE}"
    wait_then_click_element(browser, pencil_selector)

    # Edit input becomes visible.
    wait_until_visible_css_selector(
        browser,
        f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_TITLE_UPDATE}",
        timeout=3,
    )
    # Card remained selected (guards the latent deselect bug).
    assert get_selected_url(browser).get_attribute("urlselected") == "true"


def test_url_title_pencil_absent_for_non_owner_mobile(
    browser_mobile_portrait: WebDriver,
    create_test_users,
    create_test_utubs,
    create_test_utubmembers,
    create_test_urls,
    provide_app: Flask,
):
    """
    Tests that the URL title pencil icon is NOT rendered for a user who is not the
    owner / creator of the URL on a mobile device.

    GIVEN a non-owner user views a UTub they did not create on a mobile device
    WHEN the user selects a URL card
    THEN ensure the URL title pencil icon is not present in the DOM
    """
    browser = browser_mobile_portrait
    app = provide_app
    user_id_for_test = 2
    non_owned_utub: Utubs = get_utub_this_user_did_not_create(
        app, user_id=user_id_for_test
    )
    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, utub_id=non_owned_utub.id, user_id=user_id_for_test
    )
    assert_panel_visibility_mobile(browser=browser, visible_deck=Decks.URLS)

    _select_first_url_in_utub_mobile(browser, app, non_owned_utub.id)

    # Pencil should not be in the DOM at all for non-owners.
    assert (
        len(
            browser.find_elements(
                By.CSS_SELECTOR,
                f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_TITLE_UPDATE}",
            )
        )
        == 0
    )
