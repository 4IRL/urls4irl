import pytest
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from tests.functional.locators import HomePageLocators as HPL
from tests.functional.selenium_utils import (
    wait_for_animation_to_end_check_top_lhs_corner,
    wait_then_get_element,
    wait_until_visible,
)


def assert_select_url_as_non_utub_owner_and_non_url_adder(
    browser: WebDriver, url_selector: str
):
    """
    Verifies that a UTub sees limited valid elements of the URL

    Args:
        url_row (WebElement): URL Card with all visible elements
    """
    url_row = wait_then_get_element(browser, url_selector, time=3)
    assert url_row is not None

    visible_elements = (
        HPL.BUTTON_URL_ACCESS,
        HPL.BUTTON_TAG_CREATE,
    )
    non_visible_elements = (
        HPL.BUTTON_URL_STRING_UPDATE,
        HPL.BUTTON_URL_DELETE,
    )

    for visible_elem_selector in visible_elements:
        visible_elem = url_row.find_element(By.CSS_SELECTOR, visible_elem_selector)
        wait_until_visible(browser, visible_elem)
        assert visible_elem.is_displayed()
        assert visible_elem.is_enabled()

    for non_visible_elem_selector in non_visible_elements:
        with pytest.raises(NoSuchElementException):
            url_row.find_element(By.CSS_SELECTOR, non_visible_elem_selector)

    url_title = url_row.find_element(By.CSS_SELECTOR, HPL.URL_TITLE_READ)
    assert url_title.is_displayed()
    assert url_title.is_enabled()

    # Wait for element to fully get in view
    wait_for_animation_to_end_check_top_lhs_corner(
        browser, f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}"
    )

    actions = ActionChains(browser)
    actions.scroll_to_element(url_title).move_to_element(url_title).perform()

    with pytest.raises(NoSuchElementException):
        url_row.find_element(By.CSS_SELECTOR, HPL.BUTTON_URL_TITLE_UPDATE)


def assert_select_url_as_utub_owner_or_url_creator(
    browser: WebDriver, url_selector: str
):
    """
    Verifies that the owner of a UTub or adder of the URL correctly sees all valid elements of the URL

    Args:
        url_row (WebElement): URL Card with all visible elements
    """
    url_row = wait_then_get_element(browser, url_selector, time=3)
    assert url_row is not None

    assert "true" == url_row.get_attribute("urlselected")

    visible_elements = (
        HPL.BUTTON_URL_ACCESS,
        HPL.BUTTON_TAG_CREATE,
        HPL.BUTTON_URL_STRING_UPDATE,
        HPL.BUTTON_URL_DELETE,
    )

    for visible_elem_selector in visible_elements:
        visible_elem = url_row.find_element(By.CSS_SELECTOR, visible_elem_selector)
        wait_until_visible(browser, visible_elem)
        assert visible_elem.is_displayed()
        assert visible_elem.is_enabled()

    url_title = url_row.find_element(By.CSS_SELECTOR, HPL.URL_TITLE_READ)
    assert url_title.is_displayed()
    assert url_title.is_enabled()

    # Wait for element to fully get in view
    wait_for_animation_to_end_check_top_lhs_corner(
        browser, f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}"
    )

    actions = ActionChains(browser)
    actions.scroll_to_element(url_title).move_to_element(url_title).perform()

    edit_url_title_icon = url_row.find_element(
        By.CSS_SELECTOR, HPL.BUTTON_URL_TITLE_UPDATE
    )
    wait_until_visible(browser, edit_url_title_icon, 5)

    assert edit_url_title_icon.is_displayed()
    assert edit_url_title_icon.is_enabled()


def assert_keyed_url_is_selected(browser: WebDriver, url_row: WebElement):
    """
    Verifies whether a URL that is switched to via key pressed is open by checking
    if the Access URL button is visible
    """
    access_url_btn = url_row.find_element(By.CSS_SELECTOR, HPL.BUTTON_URL_ACCESS)
    access_url_btn = wait_until_visible(browser, access_url_btn)
    assert access_url_btn.is_enabled()
    assert access_url_btn.is_displayed()
