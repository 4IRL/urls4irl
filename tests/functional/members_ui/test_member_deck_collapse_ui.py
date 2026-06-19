from flask import Flask
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait

from locators import HomePageLocators as HPL
from tests.functional.db_utils import get_utub_this_user_did_not_create
from tests.functional.login_utils import login_user_and_select_utub_by_name
from tests.functional.selenium_utils import (
    wait_then_click_element,
    wait_then_get_element,
)

pytestmark = pytest.mark.members_ui


def _wait_member_deck_collapsed(browser: WebDriver, collapsed: bool):
    WebDriverWait(browser, 5).until(
        lambda driver: driver.execute_script(
            "return document.querySelector(arguments[0])"
            ".classList.contains('collapsed');",
            HPL.MEMBER_DECK,
        )
        is collapsed
    )


def test_add_member_button_stays_hidden_for_non_owner_after_deck_collapse(
    browser: WebDriver,
    create_test_utubmembers,
    provide_app: Flask,
):
    """
    GIVEN a non-owner member of a UTub has it selected
    WHEN they collapse and then re-expand the Member deck
    THEN the add-member button must remain hidden (only the owner may add members)
    """
    app = provide_app
    user_id_for_test = 1
    utub_user_member_of = get_utub_this_user_did_not_create(app, user_id_for_test)
    login_user_and_select_utub_by_name(
        app, browser, user_id_for_test, utub_user_member_of.name
    )

    # Before-state: non-owner sees the leave button, never the add-member button
    leave_btn = wait_then_get_element(browser, HPL.BUTTON_UTUB_LEAVE, time=3)
    assert leave_btn is not None
    assert leave_btn.is_displayed()
    add_member_btn = browser.find_element(By.CSS_SELECTOR, HPL.BUTTON_MEMBER_CREATE)
    assert not add_member_btn.is_displayed()

    # Collapse then re-expand the Member deck
    wait_then_click_element(browser, HPL.HEADER_AND_CARET_MEMBER_DECK, time=3)
    _wait_member_deck_collapsed(browser, collapsed=True)
    wait_then_click_element(browser, HPL.HEADER_AND_CARET_MEMBER_DECK, time=3)
    _wait_member_deck_collapsed(browser, collapsed=False)

    # The add-member button must still be hidden for the non-owner
    add_member_btn = browser.find_element(By.CSS_SELECTOR, HPL.BUTTON_MEMBER_CREATE)
    assert not add_member_btn.is_displayed()
