# External libraries
from flask import Flask
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from src import db
from src.models.utubs import Utubs
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.utils_for_test import (
    clear_then_send_keys,
    user_is_selected_utub_owner,
    wait_then_click_element,
    wait_then_get_element,
)


def get_utub_this_user_created(app: Flask, user_id: int) -> Utubs:
    with app.app_context():
        return Utubs.query.filter(Utubs.utub_creator == user_id).first()


def get_utub_this_user_did_not_create(app: Flask, user_id: int) -> Utubs:
    with app.app_context():
        return Utubs.query.filter(Utubs.utub_creator != user_id).first()


def update_utub_to_empty_desc(app: Flask, utub_id: int):
    with app.app_context():
        utub: Utubs = Utubs.query.get(utub_id)
        utub.utub_description = ""
        db.session.commit()


def create_utub(browser: WebDriver, utub_name: str, utub_description: str):
    """
    Once logged in, this function adds new UTub by selecting the option to open the input field, fills in the fields with the specified values for utub_name and utub_description, and submits the form.

    Args:
        WebDriver open to U4I Home Page
        UTub name and description inputs for creation of a new UTub

    Returns:
        WebDriver handoff to UTub tests
    """

    # Click createUTub button to show input
    wait_then_click_element(browser, HPL.BUTTON_UTUB_CREATE)

    # Types new UTub name
    create_utub_name_input = wait_then_get_element(browser, HPL.INPUT_UTUB_NAME_CREATE)
    assert create_utub_name_input is not None
    clear_then_send_keys(create_utub_name_input, utub_name)

    # Types new UTub description
    create_utub_description_input = wait_then_get_element(
        browser, HPL.INPUT_UTUB_DESCRIPTION_CREATE
    )
    assert create_utub_description_input is not None
    clear_then_send_keys(create_utub_description_input, utub_description)


def assert_active_utub(browser: WebDriver, utub_name: str):
    """
    Streamlines actions needed to confirm the UTub named utub_name is active.

    Args:
        WebDriver open to U4I Home Page

    Returns:
        Boolean True, if new UTub was created
    """

    # Extract new UTub selector. Selector should be active.
    selector_utub = wait_then_get_element(browser, HPL.SELECTOR_SELECTED_UTUB)
    assert selector_utub is not None

    # Assert new UTub is now active and displayed to user
    class_attrib = selector_utub.get_attribute("class")
    assert class_attrib is not None
    assert "active" in class_attrib

    # Assert new UTub selector was created with input UTub Name
    assert selector_utub.text == utub_name

    current_url_deck_header = wait_then_get_element(browser, HPL.HEADER_URL_DECK)
    assert current_url_deck_header is not None

    # Assert new UTub name is displayed as the URL Deck header
    assert current_url_deck_header.text == utub_name


def open_update_utub_name_input(browser: WebDriver):
    """
    Once logged in and UTub selected, this function conducts the actions for opening either the update UTub name or description input field. First hover over the UTub name or description to display the edit button. Then clicks the edit button.

    Args:
        WebDriver open to U4I Home Page
    """

    update_wrap_element = wait_then_get_element(browser, HPL.WRAP_UTUB_NAME_UPDATE)
    assert update_wrap_element is not None

    _update_utub_input(
        browser, update_wrap_element, HPL.HEADER_URL_DECK, HPL.BUTTON_UTUB_NAME_UPDATE
    )


def open_update_utub_desc_input(browser: WebDriver):
    """
    Once logged in and UTub selected, this function conducts the actions for opening either the update UTub name or description input field. First hover over the UTub name or description to display the edit button. Then clicks the edit button.

    Args:
        WebDriver open to U4I Home Page
    """
    update_wrap_element = wait_then_get_element(
        browser, HPL.WRAP_UTUB_DESCRIPTION_UPDATE
    )
    assert update_wrap_element is not None

    _update_utub_input(
        browser,
        update_wrap_element,
        HPL.SUBHEADER_URL_DECK,
        HPL.BUTTON_UTUB_DESCRIPTION_UPDATE,
    )


def _update_utub_input(
    browser: WebDriver, wrap_elem: WebElement, elem_locator: str, btn_locator: str
):
    # Hover over UTub name to display utubNameBtnUpdate button
    actions = ActionChains(browser)

    update_element = wrap_elem.find_element(By.CSS_SELECTOR, elem_locator)
    actions.move_to_element(update_element)

    # Pause to make sure utubNameBtnUpdate button is visible
    actions.pause(3).perform()

    update_button = wrap_elem.find_element(By.CSS_SELECTOR, btn_locator)

    actions.move_to_element(update_button).pause(2)

    actions.click(update_button)

    actions.perform()
    # Update input field visible


def update_utub_name(browser: WebDriver, utub_name: str) -> bool:
    """
    Once logged in and UTub selected, this function conducts the actions for editing the selected UTub name. First hover over the UTub name to display the edit button. Then clicks the edit button, interacts with the input field and submits it.

    Args:
        WebDriver open to U4I Home Page
        New UTub name

    Returns:
        WebDriver handoff to UTub tests
    """

    if user_is_selected_utub_owner(browser):
        open_update_utub_name_input(browser)

        # Types new UTub name
        utub_name_update_input = wait_then_get_element(
            browser, HPL.INPUT_UTUB_NAME_UPDATE
        )
        assert utub_name_update_input is not None
        clear_then_send_keys(utub_name_update_input, utub_name)

        return True
    else:
        return False


def update_utub_description(browser: WebDriver, utub_description: str):
    """
    Once logged in and UTub selected, this function conducts the actions for editing the selected UTub description. First hover over the UTub decsription to display the edit button. Then clicks the edit button, interacts with the input field and submits it.

    Args:
        WebDriver open to U4I Home Page
        New UTub description
    """

    open_update_utub_desc_input(browser)

    # Types new UTub description
    utub_description_update_input = wait_then_get_element(
        browser, HPL.INPUT_UTUB_DESCRIPTION_UPDATE
    )
    assert utub_description_update_input is not None
    clear_then_send_keys(utub_description_update_input, utub_description)


def hover_over_utub_title_to_show_add_utub_description(browser: WebDriver):
    # Hover over UTub name to display utubNameBtnUpdate button
    actions = ActionChains(browser)

    utub_title_elem = browser.find_element(By.CSS_SELECTOR, HPL.HEADER_URL_DECK)
    actions.move_to_element(utub_title_elem)

    # Pause to make sure utubNameBtnUpdate button is visible
    actions.perform()

    utub_desc_elem = browser.find_element(By.CSS_SELECTOR, HPL.SUBHEADER_URL_DECK)
    assert not utub_desc_elem.is_displayed()
