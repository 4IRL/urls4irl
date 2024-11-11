# Standard library

# External libraries
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

# Internal libraries
from tests.functional.locators import MainPageLocators as MPL
from tests.functional.utils_for_test import (
    clear_then_send_keys,
    user_is_selected_utub_owner,
    wait_then_click_element,
    wait_then_get_element,
)


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
    wait_then_click_element(browser, MPL.BUTTON_UTUB_CREATE)

    # Types new UTub name
    create_utub_name_input = wait_then_get_element(browser, MPL.INPUT_UTUB_NAME_CREATE)
    clear_then_send_keys(create_utub_name_input, utub_name)

    # Types new UTub description
    create_utub_description_input = wait_then_get_element(
        browser, MPL.INPUT_UTUB_DESCRIPTION_CREATE
    )
    clear_then_send_keys(create_utub_description_input, utub_description)


def update_utub_name(browser: WebDriver, utub_name: str):
    """
    Once logged in and UTub selected, this function conducts the actions for editing the selected UTub name. First hover over the UTub name to display the edit button. Then clicks the edit button, interacts with the input field and submits it.

    Args:
        WebDriver open to U4I Home Page
        New UTub name

    Returns:
        WebDriver handoff to UTub tests
    """

    utub_name_update_wrap = wait_then_get_element(browser, MPL.WRAP_UTUB_NAME_UPDATE)

    actions = ActionChains(browser)

    if user_is_selected_utub_owner(browser):
        # Hover over UTub name to display utubNameBtnUpdate button
        url_header = utub_name_update_wrap.find_element(
            By.CSS_SELECTOR, MPL.HEADER_URL_DECK
        )
        actions.move_to_element(url_header)

        # Pause to make sure utubNameBtnUpdate button is visible
        actions.pause(3).perform()

        utub_name_update_button = utub_name_update_wrap.find_element(
            By.CSS_SELECTOR, MPL.BUTTON_UTUB_NAME_UPDATE
        )

        actions.move_to_element(utub_name_update_button).pause(2)

        actions.click(utub_name_update_button)

        # Update UTub name input field visible
        actions.perform()

        # Types new UTub name
        utub_name_update_input = wait_then_get_element(
            browser, MPL.INPUT_UTUB_NAME_UPDATE
        )
        clear_then_send_keys(utub_name_update_input, utub_name)

        # Submits new UTub name
        wait_then_click_element(browser, MPL.BUTTON_UTUB_NAME_SUBMIT_UPDATE)

        return True
    else:
        return False


def update_utub_description(browser: WebDriver, utub_description: str):
    """
    Once logged in and UTub selected, this function conducts the actions for editing the selected UTub description. First hover over the UTub decsription to display the edit button. Then clicks the edit button, interacts with the input field and submits it.

    Args:
        WebDriver open to U4I Home Page
        New UTub description

    Returns:
        WebDriver handoff to UTub tests
    """

    utub_description_update_wrap = wait_then_get_element(
        browser, MPL.WRAP_UTUB_DESCRIPTION_UPDATE
    )

    actions = ActionChains(browser)

    if user_is_selected_utub_owner(browser):
        # Hover over UTub name to display utubNameBtnUpdate button
        url_header = utub_description_update_wrap.find_element(
            By.CSS_SELECTOR, MPL.HEADER_URL_DECK
        )
        actions.move_to_element(url_header)

        # Pause to make sure utubNameBtnUpdate button is visible
        actions.pause(3).perform()

        utub_name_update_button = utub_description_update_wrap.find_element(
            By.CSS_SELECTOR, MPL.BUTTON_UTUB_NAME_UPDATE
        )

        actions.move_to_element(utub_name_update_button).pause(2)

        actions.click(utub_name_update_button)

        # Update UTub name input field visible
        actions.perform()

        # Types new UTub name
        utub_name_update_input = wait_then_get_element(
            browser, MPL.INPUT_UTUB_NAME_UPDATE
        )
        clear_then_send_keys(utub_name_update_input, utub_description)

        # Submits new UTub name
        wait_then_click_element(browser, MPL.BUTTON_UTUB_NAME_SUBMIT_UPDATE)

        return True
    else:
        return False


def delete_active_utub(browser: WebDriver):
    """
    Once logged in, this function adds new UTub by selecting the option to open the input field, fills in the fields with the specified values for utub_name and utub_description, and submits the form.

    Args:
        WebDriver open to a selected UTub to be deleted

    Returns:
        Boolean confirmation of successful deletion of UTub
        WebDriver handoff to UTub tests
    """

    if user_is_selected_utub_owner(browser):
        wait_then_click_element(browser, MPL.BUTTON_UTUB_DELETE)
        return True
    else:
        return False


def delete_active_utub_confirmed(browser: WebDriver):
    """
    Simplifies interaction with UTub WebElement to initiate and confirm deletion request.

    Args:
        WebDriver open to a selected UTub

    Returns:
        Yields WebDriver to tests
    """

    # Select deleteUTub button
    delete_active_utub(browser)
    # Confirm warning modal
    wait_then_click_element(browser, MPL.BUTTON_MODAL_SUBMIT)
