# Standard library

# External libraries
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

# Internal libraries
from tests.functional.locators import MainPageLocators as MPL
from tests.functional.utils_for_test import (
    clear_then_send_keys,
    current_user_is_owner,
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
    wait_then_click_element(browser, MPL.BUTTON_URL_SUBMIT_CREATE)


def update_url_string(browser, url_row, url_string: str):
    """
    Once logged in, with users, UTub, URLs, and a URL selected this function initiates the action to update the string of the active URL in the UTub.
    """

    # Activate URL
    url_row.click()

    # Select editURL button
    url_row.find_element(By.CSS_SELECTOR, MPL.BUTTON_URL_UPDATE).click()

    # Input new URL string
    url_string_input_field = url_row.find_element(
        By.CSS_SELECTOR, MPL.INPUT_URL_STRING_UPDATE
    )
    clear_then_send_keys(url_string_input_field, url_string)

    # Submit
    url_row.find_element(By.CSS_SELECTOR, MPL.BUTTON_URL_STRING_SUBMIT_UPDATE).click()


def update_url_title(browser, url_row, url_title: str):
    """
    Once logged in, with users, UTub, URLs, and a URL selected this function initiates the action to update the title of the active URL in the UTub.
    """

    # Activate URL
    url_row.click()

    # Select editURL button
    url_title_text = url_row.find_element(By.CSS_SELECTOR, ".urlTitle")

    actions = ActionChains(browser)

    # Hover over URL title to display editURLTitle button
    actions.move_to_element(url_title_text)

    # Pause to make sure editURLTitle button is visible
    actions.pause(3).perform()

    update_url_title_button = url_row.find_element(
        By.CSS_SELECTOR, MPL.BUTTON_URL_TITLE_UPDATE
    )

    actions.move_to_element(update_url_title_button).pause(2)

    actions.click(update_url_title_button)

    actions.perform()

    # Input new URL Title
    url_title_input_field = url_row.find_element(
        By.CSS_SELECTOR, MPL.INPUT_URL_TITLE_UPDATE
    )
    clear_then_send_keys(url_title_input_field, url_title)

    # Submit
    url_row.find_element(By.CSS_SELECTOR, MPL.BUTTON_URL_TITLE_SUBMIT_UPDATE).click()


def delete_active_url(browser):
    """
    Once logged in, with users, UTubs, and URLs this function initiates the action to delete one URL from the UTub. Modal confirmation handled in test.
    """

    if current_user_is_owner(browser):
        wait_then_click_element(browser, MPL.BUTTON_UTUB_DELETE)
    else:
        return False
