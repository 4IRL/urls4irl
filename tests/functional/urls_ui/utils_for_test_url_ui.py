# Standard library
from time import sleep

# External libraries
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

# Internal libraries
from tests.functional.locators import MainPageLocators as MPL
from tests.functional.utils_for_test import (
    clear_then_send_keys,
    wait_then_click_element,
    wait_then_get_element,
)


def create_url(browser: WebDriver, url_title: str, url_string: str):
    """
    Streamlines actions required to create a URL in the selected UTub.

    Args:
        WebDriver open to a selected UTub
        URL title
        URL
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


def update_url_string(browser: WebDriver, url_row: WebElement, url_string: str):
    """
    Streamlines actions required to updated a URL in the selected URL.

    Args:
        WebDriver open to a selected URL
        New URL string

    Returns:
        Yields WebDriver to tests
    """

    # Select editURL button
    url_row.find_element(By.CSS_SELECTOR, MPL.BUTTON_URL_STRING_UPDATE).click()

    # Input new URL string
    url_string_input_field = url_row.find_element(
        By.CSS_SELECTOR, MPL.INPUT_URL_STRING_UPDATE
    )
    clear_then_send_keys(url_string_input_field, url_string)


def update_url_title(browser: WebDriver, selected_url_row: WebElement, url_title: str):
    """
    Streamlines actions required to updated a URL in the selected URL.

    Args:
        WebDriver open to a selected URL
        New URL title

    Returns:
        Yields WebDriver to tests
    """

    # Select editURL button
    url_title_text = selected_url_row.find_element(By.CSS_SELECTOR, MPL.URL_TITLE_READ)

    actions = ActionChains(browser)

    # Hover over URL title to display editURLTitle button
    actions.move_to_element(url_title_text)

    # Pause to make sure editURLTitle button is visible
    actions.pause(3).perform()

    update_url_title_button = selected_url_row.find_element(
        By.CSS_SELECTOR, MPL.BUTTON_URL_TITLE_UPDATE
    )

    actions.move_to_element(update_url_title_button).pause(2)

    actions.click(update_url_title_button)

    actions.perform()

    # Input new URL Title
    url_title_input_field = selected_url_row.find_element(
        By.CSS_SELECTOR, MPL.INPUT_URL_TITLE_UPDATE
    )
    clear_then_send_keys(url_title_input_field, url_title)


def delete_url(browser: WebDriver, url_row: WebElement):
    """
    Simplifies interaction with URL WebElement to initiate deletion request.

    Args:
        WebDriver open to a selected URL

    Returns:
        Yields WebDriver to tests
    """

    # Select deleteURL button
    url_row.find_element(By.CSS_SELECTOR, MPL.BUTTON_URL_DELETE).click()


def delete_url_confirmed(browser: WebDriver, url_row: WebElement):
    """
    Simplifies interaction with URL WebElement to initiate and confirm deletion request.

    Args:
        WebDriver open to a selected URL

    Returns:
        Yields WebDriver to tests
    """

    # Select deleteURL button
    delete_url(browser, url_row)
    # Confirm warning modal
    wait_then_click_element(browser, MPL.BUTTON_MODAL_SUBMIT)
    # Wait for DELETE request
    sleep(4)


def delete_all_urls(browser: WebDriver):
    """
    Automates deletion of all URLs in selected UTub

    Args:
        WebDriver open to a selected UTub

    Returns:
        Yields WebDriver to tests
    """

    url_rows = browser.find_elements(By.CSS_SELECTOR, MPL.ROWS_URLS)

    for url_row in url_rows:
        url_row.click()
        delete_url_confirmed(browser, url_row)
