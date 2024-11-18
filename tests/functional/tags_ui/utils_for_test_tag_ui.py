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


def create_tag(browser: WebDriver, selected_url_row: WebElement, tag_string: str = ""):
    """
    Once logged in, with users, UTub, and URLs this function initiates the action to create one tag applied to the selected URL in the selected UTub.
    """

    # Select createTag button
    selected_url_row.find_element(By.CSS_SELECTOR, MPL.BUTTON_TAG_CREATE).click()

    create_tag_input = selected_url_row.find_element(
        By.CSS_SELECTOR, MPL.INPUT_TAG_CREATE
    )

    assert create_tag_input.is_displayed()

    if tag_string:
        # Input new tag
        tag_input_field = wait_then_get_element(browser, MPL.INPUT_TAG_CREATE)
        clear_then_send_keys(tag_input_field, tag_string)


def show_delete_tag_button_on_hover(browser: WebDriver, tag_badge: WebElement):
    """
    Args:
        WebDriver open to a selected URL
        Tag badge element to remove from the selected URL

    Returns:
        Boolean confirmation of successful deletion of tag
        WebDriver handoff to member tests
    """

    actions = ActionChains(browser)

    actions.move_to_element(tag_badge)

    # Pause to make sure deleteTag button is visible
    actions.pause(3).perform()

    delete_tag_button = tag_badge.find_element(By.CSS_SELECTOR, MPL.BUTTON_TAG_DELETE)

    return delete_tag_button


def delete_tag(browser: WebDriver, url_tag_to_delete: WebElement):
    """
    Once logged in, with users, UTubs, URLs, and tags this function initiates the action to delete the first tag in the tagList in the selected URL.
    """
    delete_tag_button = show_delete_tag_button_on_hover(browser, url_tag_to_delete)

    actions = ActionChains(browser)

    actions.move_to_element(delete_tag_button).pause(2)

    actions.click(delete_tag_button)

    actions.perform()

    return True
