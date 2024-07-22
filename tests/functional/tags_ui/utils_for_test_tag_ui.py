# Standard library

# External libraries
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

# Internal libraries
from tests.functional.locators import MainPageLocators as MPL
from tests.functional.utils_for_test import (
    clear_then_send_keys,
    wait_then_click_element,
    wait_then_get_element,
)


def create_tag(browser, selected_url_row, tag_string: str):
    """
    Once logged in, with users, UTub, and URLs this function initiates the action to create one tag applied to the selected URL in the UTub.
    """

    # Select createTag button
    selected_url_row.find_element(By.CSS_SELECTOR, MPL.BUTTON_TAG_CREATE).click()

    # Input new tag
    tag_input_field = wait_then_get_element(browser, MPL.INPUT_TAG_CREATE)
    clear_then_send_keys(tag_input_field, tag_string)

    # Submit
    wait_then_click_element(browser, MPL.BUTTON_TAG_SUBMIT_CREATE)


def delete_tag(browser, selected_url_row, tag_string: str):
    """
    Once logged in, with users, UTubs, URLs, and tags this function initiates the action to delete one tag from the selected URL. Modal confirmation handled in test.
    """

    actions = ActionChains(browser)

    # Hover over URL title to display editURLTitle button
    actions.move_to_element(tag_string)

    # Pause to make sure editURLTitle button is visible
    actions.pause(3).perform()

    update_url_title_button = selected_url_row.find_element(
        By.CSS_SELECTOR, MPL.BUTTON_URL_TITLE_UPDATE
    )

    actions.move_to_element(update_url_title_button).pause(2)

    actions.click(update_url_title_button)

    actions.perform()
