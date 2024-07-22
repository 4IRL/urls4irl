# Standard library

# External libraries

# Internal libraries
from tests.functional.locators import MainPageLocators as MPL
from tests.functional.utils_for_test import (
    clear_then_send_keys,
    user_is_selected_utub_owner,
    wait_then_click_element,
    wait_then_get_element,
)


def create_utub(browser, utub_name: str, utub_description: str):
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

    # Submits new UTub
    wait_then_click_element(browser, MPL.BUTTON_UTUB_SUBMIT_CREATE)


def delete_active_utub(browser):
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
