# Standard library

# External libraries

# Internal libraries
from tests.functional.locators import MainPageLocators as MPL
from tests.functional.utils_for_test import (
    clear_then_send_keys,
    is_owner,
    wait_then_click_element,
    wait_then_get_element,
)


def create_url(browser, url_title: str, url_string: str):
    """
    Once logged in, with users, UTub this function initiates the action to create one URL in the UTub.
    """

    # Select createURL button
    wait_then_click_element(browser, MPL.BUTTON_URL_CREATE)

    # Input new URL Title
    url_title_input_field = wait_then_get_element(browser, MPL.INPUT_URL_TITLE_CREATE)
    clear_then_send_keys(url_title_input_field, url_title)

    # Input new URL String
    url_string_input_field = wait_then_get_element(browser, MPL.INPUT_URL_STRING_CREATE)
    clear_then_send_keys(url_string_input_field, url_string)

    # Submit
    wait_then_click_element(browser, MPL.BUTTON_URL_CREATE)


def delete_url(browser, user_name):
    """
    Once logged in, with users, UTubs, and URLs this function initiates the action to delete one URL from the UTub. Modal confirmation handled in test.
    """

    if is_owner(user_name):
        wait_then_click_element(browser, MPL.BUTTON_UTUB_DELETE)
    else:
        return False
