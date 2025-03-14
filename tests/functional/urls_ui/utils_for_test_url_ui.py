from typing import Tuple

from flask import Flask
import pytest
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from src.models.urls import Urls
from src.models.utub_urls import Utub_Urls
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.locators import ModalLocators as ML
from tests.functional.utils_for_test import (
    clear_then_send_keys,
    get_selected_url,
    login_user_select_utub_by_name_and_url_by_string,
    wait_for_animation_to_end,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_visible,
    wait_until_visible_css_selector,
)


def create_url(browser: WebDriver, url_title: str, url_string: str):
    """
    Streamlines actions required to create a URL in the selected UTub.

    Args:
        WebDriver open to a selected UTub
        URL title
        URL
    """
    fill_create_url_form(browser, url_title, url_string)

    # Submit
    wait_then_click_element(browser, HPL.BUTTON_URL_SUBMIT_CREATE)


def fill_create_url_form(browser: WebDriver, url_title: str, url_string: str):
    """
    Streamlines actions required to create a URL in the selected UTub.

    Args:
        WebDriver open to a selected UTub
        URL title
        URL
    """

    # Select createURL button
    wait_then_click_element(browser, HPL.BUTTON_CORNER_URL_CREATE)
    url_creation_row = wait_then_get_element(browser, HPL.WRAP_URL_CREATE)
    assert url_creation_row is not None
    assert url_creation_row.is_displayed()

    # Input new URL Title
    url_title_input_field = wait_then_get_element(browser, HPL.INPUT_URL_TITLE_CREATE)
    assert url_title_input_field is not None
    clear_then_send_keys(url_title_input_field, url_title)

    # Input new URL String
    url_string_input_field = wait_then_get_element(browser, HPL.INPUT_URL_STRING_CREATE)
    assert url_string_input_field is not None
    clear_then_send_keys(url_string_input_field, url_string)


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
    url_row.find_element(By.CSS_SELECTOR, HPL.BUTTON_URL_STRING_UPDATE).click()

    # Input new URL string
    url_string_input_field = url_row.find_element(
        By.CSS_SELECTOR, HPL.INPUT_URL_STRING_UPDATE
    )
    url_string_input_field = wait_until_visible(
        browser, url_string_input_field, timeout=3
    )
    clear_then_send_keys(url_string_input_field, url_string)


def open_update_url_title(browser: WebDriver, selected_url_row: WebElement):
    """
    Streamlines actions required to updated a URL in the selected URL.

    Args:
        WebDriver open to a selected URL
        New URL title

    Returns:
        Yields WebDriver to tests
    """

    # Select editURL button
    url_title_text = selected_url_row.find_element(By.CSS_SELECTOR, HPL.URL_TITLE_READ)

    actions = ActionChains(browser)

    # Hover over URL title to display editURLTitle button
    actions.move_to_element(url_title_text)

    # Pause to make sure editURLTitle button is visible
    actions.pause(3).perform()

    update_url_title_button = selected_url_row.find_element(
        By.CSS_SELECTOR, HPL.BUTTON_URL_TITLE_UPDATE
    )

    actions.move_to_element(update_url_title_button).pause(2)

    actions.click(update_url_title_button)

    actions.perform()

    update_url_title_selector = f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_URL_TITLE_UPDATE}"
    wait_until_visible_css_selector(browser, update_url_title_selector)


def update_url_title(browser: WebDriver, selected_url_row: WebElement, url_title: str):
    """
    Streamlines actions required to updated a URL in the selected URL.

    Args:
        WebDriver open to a selected URL
        New URL title

    Returns:
        Yields WebDriver to tests
    """
    open_update_url_title(browser, selected_url_row)

    # Input new URL Title
    url_title_input_field = selected_url_row.find_element(
        By.CSS_SELECTOR, HPL.INPUT_URL_TITLE_UPDATE
    )
    clear_then_send_keys(url_title_input_field, url_title)


def login_select_utub_select_url_click_delete_get_modal_url(
    browser: WebDriver,
    app: Flask,
    user_id: int,
    utub_name: str,
    url_string: str,
    timeout: int = 5,
) -> Tuple[WebElement, WebElement]:
    login_user_select_utub_by_name_and_url_by_string(
        app, browser, user_id, utub_name, url_string
    )
    url_row = get_selected_url(browser)
    wait_for_animation_to_end(
        browser, f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}"
    )

    wait_then_click_element(
        browser, f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_DELETE}", time=timeout
    )
    wait_until_visible_css_selector(browser, ML.ELEMENT_MODAL, timeout)
    modal = wait_then_get_element(browser, HPL.BODY_MODAL)
    assert modal is not None

    return modal, url_row


def verify_select_url_as_utub_owner_or_url_creator(
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
    wait_for_animation_to_end(
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


def verify_select_url_as_non_utub_owner_and_non_url_adder(
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
    wait_for_animation_to_end(
        browser, f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}"
    )

    actions = ActionChains(browser)
    actions.scroll_to_element(url_title).move_to_element(url_title).perform()

    with pytest.raises(NoSuchElementException):
        url_row.find_element(By.CSS_SELECTOR, HPL.BUTTON_URL_TITLE_UPDATE)


def get_selected_utub_id(browser: WebDriver) -> int:
    utub = browser.find_element(By.CSS_SELECTOR, HPL.SELECTOR_SELECTED_UTUB)
    utub_id = utub.get_attribute("utubid")
    assert utub_id is not None
    return int(utub_id)


def get_utub_url_id_for_added_url_in_utub_as_member(
    app: Flask, utub_id: int, user_id: int
) -> int:
    with app.app_context():
        url_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id, Utub_Urls.user_id == user_id
        ).first()
        return url_in_utub.id


def verify_keyed_url_is_selected(browser: WebDriver, url_row: WebElement):
    """
    Verifies whether a URL that is switched to via key pressed is open by checking
    if the Access URL button is visible
    """
    access_url_btn = url_row.find_element(By.CSS_SELECTOR, HPL.BUTTON_URL_ACCESS)
    access_url_btn = wait_until_visible(browser, access_url_btn)
    assert access_url_btn.is_enabled()
    assert access_url_btn.is_displayed()


def get_newly_added_utub_url_id_by_url_string(
    app: Flask, utub_id: int, url_string: str
) -> int:
    with app.app_context():
        url: Urls = Urls.query.filter(Urls.url_string == url_string).first()
        assert url is not None
        utub_url: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.url_id == url.id, Utub_Urls.utub_id == utub_id
        ).first()
        assert utub_url is not None
        return utub_url.id


def add_invalid_url_header_for_ui_test(browser: WebDriver):
    browser.execute_script(
        """
        (function() {
            var originalBeforeSend = $.ajaxSetup().beforeSend;

            $.ajaxSetup({
                beforeSend: function(xhr, settings) {
                    if (originalBeforeSend) {
                        originalBeforeSend(xhr, settings); // Preserve existing behavior
                    }
                    xhr.setRequestHeader("X-U4I-Testing-Invalid", "true");
                }
            });
        })();
    """
    )


def get_url_in_utub(app: Flask, utub_id: int) -> Utub_Urls:
    with app.app_context():
        return Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id).first()
