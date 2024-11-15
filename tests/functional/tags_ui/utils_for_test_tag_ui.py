# Standard library

# External libraries
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

# Internal libraries
from tests.functional.locators import MainPageLocators as MPL
from tests.functional.utils_for_test import (
    clear_then_send_keys,
    wait_then_get_element,
)


def open_create_tag_input(
    browser: WebDriver, selected_url_row: WebElement, tag_string: str
):
    """
    Once logged in, with users, UTub, and URLs this function initiates the action to create one tag applied to the selected URL in the selected UTub.
    """

    # Select createTag button
    selected_url_row.find_element(By.CSS_SELECTOR, MPL.BUTTON_TAG_CREATE).click()

    # Input new tag
    tag_input_field = wait_then_get_element(browser, MPL.INPUT_TAG_CREATE)
    clear_then_send_keys(tag_input_field, tag_string)


def delete_tag(browser: WebDriver, tag_badge: WebElement):
    """
    Once logged in, with users, UTubs, URLs, and tags this function initiates the action to delete the first tag in the tagList in the selected URL. Modal confirmation handled in test.
    """

    actions = ActionChains(browser)

    # Hover over tag to display deleteTag button
    actions.move_to_element(tag_badge)

    # Pause to make sure deleteTag button is visible
    actions.pause(3).perform()

    delete_tag_button = tag_badge.find_element(By.CSS_SELECTOR, MPL.BUTTON_TAG_DELETE)

    actions.move_to_element(delete_tag_button).pause(2)

    actions.click(delete_tag_button)

    actions.perform()
