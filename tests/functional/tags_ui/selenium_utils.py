from typing import Tuple
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from tests.functional.locators import HomePageLocators as HPL
from tests.functional.selenium_utils import (
    clear_then_send_keys,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)


def add_tag_to_url(browser: WebDriver, selected_url_id: int, tag_string: str) -> None:
    """
    Once logged in, with users, UTub, and URLs this function initiates the action to create one tag applied to the selected URL in the selected UTub.
    """
    open_url_tag_input(browser, selected_url_id)
    input_url_tag_selector = f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_TAG_CREATE}"

    create_tag_input = browser.find_element(By.CSS_SELECTOR, input_url_tag_selector)
    assert create_tag_input.is_displayed()
    clear_then_send_keys(create_tag_input, tag_string)


def open_url_tag_input(browser: WebDriver, selected_url_id: int):
    url_selector = f"{HPL.ROWS_URLS}[utuburlid='{selected_url_id}']"

    open_tag_input_selector = f"{url_selector} {HPL.BUTTON_TAG_CREATE}"
    wait_then_click_element(browser, open_tag_input_selector, time=3)

    url_tag_input_selector = f"{url_selector} {HPL.INPUT_TAG_CREATE}"
    wait_until_visible_css_selector(browser, url_tag_input_selector, timeout=3)

    wait_until_in_focus(browser, url_tag_input_selector, timeout=3)


def get_delete_tag_button_on_hover(browser: WebDriver, tag_badge_selector: str):
    """
    Args:
        WebDriver open to a selected URL
        Tag badge element to remove from the selected URL

    Returns:
        Boolean confirmation of successful deletion of tag
        WebDriver handoff to member tests
    """
    tag_badge = browser.find_element(By.CSS_SELECTOR, tag_badge_selector)

    actions = ActionChains(browser)

    actions.move_to_element(tag_badge)

    # Pause to make sure deleteTag button is visible
    actions.pause(3).perform()

    actions.move_to_element(tag_badge).pause(2).perform()

    return tag_badge.find_element(By.CSS_SELECTOR, HPL.BUTTON_TAG_DELETE)


def get_tag_badge_selector_on_selected_url_by_tag_id(url_tag_id: int) -> str:
    return f"{HPL.ROW_SELECTED_URL} {HPL.TAG_BADGES}[{HPL.TAG_BADGE_ID_ATTRIB}='{url_tag_id}']"


def get_utub_tag_filter_selector(utub_tag_id: int) -> str:
    return f"{HPL.TAG_FILTERS}[data-utub-tag-id='{utub_tag_id}']"


def apply_tag_filter_based_on_id(browser: WebDriver, utub_tag_id: int):
    utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id)
    wait_then_click_element(browser, utub_tag_filter, time=3)


def apply_tag_filter_by_id_and_get_shown_urls(
    browser: WebDriver, utub_tag_id: int
) -> list[WebElement]:
    apply_tag_filter_based_on_id(browser, utub_tag_id)
    url_row_elements = browser.find_elements(By.CSS_SELECTOR, HPL.ROWS_URLS)
    return [url_row for url_row in url_row_elements if url_row.is_displayed()]


def get_visible_urls_and_urls_with_tag_text_by_tag_id(
    browser: WebDriver, tag_id: int
) -> Tuple[int, int]:
    """
    Extracts the visible URLs and total count of URLs that have a specific tag from the Tag Deck associated with the tag filter based on the tag ID.
    """
    utub_tag_selector = (
        f'{HPL.TAG_FILTERS}[data-utub-tag-id="{tag_id}"] {HPL.TAG_COUNT}'
    )
    tag_filter_count_elem = wait_then_get_element(browser, utub_tag_selector)
    assert tag_filter_count_elem
    visible, total = tag_filter_count_elem.text.split(" / ")
    return int(visible), int(total)
