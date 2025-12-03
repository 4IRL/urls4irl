from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from src.utils.strings.tag_strs import DELETE_UTUB_TAG_WARNING
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.selenium_utils import (
    wait_then_get_element,
)


def assert_btns_shown_on_cancel_url_tag_input_creator(browser: WebDriver):
    visible_elements = (
        HPL.BUTTON_URL_ACCESS,
        HPL.BUTTON_URL_STRING_UPDATE,
        HPL.BUTTON_URL_DELETE,
    )

    for elem_selector in visible_elements:
        visible_elem_selector = f"{HPL.ROW_SELECTED_URL} {elem_selector}"
        visible_btn = wait_then_get_element(browser, visible_elem_selector, time=3)
        assert visible_btn is not None
        assert visible_btn.is_displayed()

    # Verify Add Tag button now includes class and text indicating it is the big cancel button
    add_tag_btn_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_CREATE}"
    add_tag_btn = browser.find_element(By.CSS_SELECTOR, add_tag_btn_selector)
    assert add_tag_btn.is_displayed()
    classes = add_tag_btn.get_attribute("class")
    assert classes and HPL.BUTTON_BIG_TAG_CANCEL_CREATE not in classes


def assert_btns_shown_on_cancel_url_tag_input_member(browser: WebDriver):
    visible_elem_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}"
    visible_btn = wait_then_get_element(browser, visible_elem_selector, time=3)
    assert visible_btn is not None
    assert visible_btn.is_displayed()

    # Verify Add Tag button now includes class and text indicating it is the big cancel button
    add_tag_btn_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_CREATE}"
    add_tag_btn = browser.find_element(By.CSS_SELECTOR, add_tag_btn_selector)
    assert add_tag_btn.is_displayed()
    classes = add_tag_btn.get_attribute("class")
    assert classes and HPL.BUTTON_BIG_TAG_CANCEL_CREATE not in classes


def assert_create_utub_tag_input_form_is_shown(browser: WebDriver):
    visible_elems = (
        HPL.INPUT_UTUB_TAG_CREATE,
        HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE,
        HPL.BUTTON_UTUB_TAG_CANCEL_CREATE,
    )

    for visible_elem_selector in visible_elems:
        visible_elem = browser.find_element(By.CSS_SELECTOR, visible_elem_selector)
        assert visible_elem.is_displayed()
        assert visible_elem.is_enabled()

    non_visible_elems = (
        HPL.BUTTON_UTUB_TAG_CREATE,
        HPL.LIST_TAGS,
        HPL.WRAP_BUTTONS_CREATE_UNFILTER_UTUB_TAGS,
    )
    for non_visible_elem_selector in non_visible_elems:
        non_visible_elem = browser.find_element(
            By.CSS_SELECTOR, non_visible_elem_selector
        )
        assert not non_visible_elem.is_displayed()


def assert_create_utub_tag_input_form_is_hidden(browser: WebDriver):
    non_visible_elems = (
        HPL.INPUT_UTUB_TAG_CREATE,
        HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE,
        HPL.BUTTON_UTUB_TAG_CANCEL_CREATE,
    )
    for non_visible_elem_selector in non_visible_elems:
        non_visible_elem = browser.find_element(
            By.CSS_SELECTOR, non_visible_elem_selector
        )
        assert not non_visible_elem.is_displayed()

    visible_elems = (
        HPL.BUTTON_UTUB_TAG_CREATE,
        HPL.LIST_TAGS,
        HPL.BUTTON_UNSELECT_ALL,
    )
    for visible_elem_selector in visible_elems:
        visible_elem = browser.find_element(By.CSS_SELECTOR, visible_elem_selector)
        assert visible_elem.is_displayed()
        assert visible_elem.is_enabled()


def assert_new_utub_tag_created(
    browser: WebDriver, new_tag_str: str, init_utub_tag_count: int
):
    assert_create_utub_tag_input_form_is_hidden(browser)

    utub_tag_container = wait_then_get_element(browser, HPL.LIST_TAGS)
    assert utub_tag_container is not None

    utub_tags = utub_tag_container.find_elements(By.CSS_SELECTOR, HPL.TAG_FILTERS)
    assert len(utub_tags) == init_utub_tag_count + 1

    # Verify the text of the new tag is found in a tag element
    utub_tag_spans = utub_tag_container.find_elements(
        By.CSS_SELECTOR, HPL.TAG_FILTERS + " span"
    )
    assert new_tag_str in [tag.text for tag in utub_tag_spans]


def assert_delete_utub_tag_modal_shown(browser: WebDriver):
    warning_modal = wait_then_get_element(browser, HPL.HOME_MODAL)
    assert warning_modal is not None

    assert warning_modal.is_displayed()

    warning_modal_body = warning_modal.find_element(By.CSS_SELECTOR, HPL.BODY_MODAL)
    confirmation_modal_body_text = warning_modal_body.get_attribute("innerText")

    utub_tag_delete_check_text = DELETE_UTUB_TAG_WARNING

    # Assert warning modal appears with appropriate text
    assert confirmation_modal_body_text == utub_tag_delete_check_text
