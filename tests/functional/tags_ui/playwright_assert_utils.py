from flask import Flask
from playwright.sync_api import Page, expect

from backend.utils.strings.tag_strs import DELETE_UTUB_TAG_WARNING
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_utils import wait_then_get_element
from tests.functional.tags_ui.db_utils import get_tag_in_utub


def assert_btns_shown_on_cancel_url_tag_input_creator(*, page: Page) -> None:
    visible_selectors = (
        HPL.BUTTON_URL_ACCESS,
        HPL.BUTTON_URL_STRING_UPDATE,
        HPL.BUTTON_URL_DELETE,
    )
    for elem_selector in visible_selectors:
        visible_elem_selector = f"{HPL.ROW_SELECTED_URL} {elem_selector}"
        visible_btn = wait_then_get_element(
            page=page, css_selector=visible_elem_selector
        )
        assert visible_btn is not None
        expect(visible_btn).to_be_visible()
    add_tag_btn_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_CREATE}"
    add_tag_btn = page.locator(add_tag_btn_selector).first
    expect(add_tag_btn).to_be_visible()
    classes = add_tag_btn.get_attribute("class")
    assert classes and HPL.BUTTON_BIG_TAG_CANCEL_CREATE not in classes


def assert_btns_shown_on_cancel_url_tag_input_member(*, page: Page) -> None:
    visible_elem_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_URL_ACCESS}"
    visible_btn = wait_then_get_element(page=page, css_selector=visible_elem_selector)
    assert visible_btn is not None
    expect(visible_btn).to_be_visible()
    add_tag_btn_selector = f"{HPL.ROW_SELECTED_URL} {HPL.BUTTON_TAG_CREATE}"
    add_tag_btn = page.locator(add_tag_btn_selector).first
    expect(add_tag_btn).to_be_visible()
    classes = add_tag_btn.get_attribute("class")
    assert classes and HPL.BUTTON_BIG_TAG_CANCEL_CREATE not in classes


def assert_create_utub_tag_input_form_is_shown(*, page: Page) -> None:
    visible_selectors = (
        HPL.INPUT_UTUB_TAG_CREATE,
        HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE,
        HPL.BUTTON_UTUB_TAG_CANCEL_CREATE,
    )
    for visible_elem_selector in visible_selectors:
        visible_elem = page.locator(visible_elem_selector).first
        expect(visible_elem).to_be_visible()
        expect(visible_elem).to_be_enabled()
    non_visible_selectors = (
        HPL.BUTTON_UTUB_TAG_CREATE,
        HPL.LIST_TAGS,
        HPL.WRAP_BUTTONS_CREATE_UNFILTER_UTUB_TAGS,
    )
    for non_visible_elem_selector in non_visible_selectors:
        non_visible_elem = page.locator(non_visible_elem_selector).first
        expect(non_visible_elem).to_be_hidden()


def assert_create_utub_tag_input_form_is_hidden(*, page: Page) -> None:
    non_visible_selectors = (
        HPL.INPUT_UTUB_TAG_CREATE,
        HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE,
        HPL.BUTTON_UTUB_TAG_CANCEL_CREATE,
    )
    for non_visible_elem_selector in non_visible_selectors:
        non_visible_elem = page.locator(non_visible_elem_selector).first
        expect(non_visible_elem).to_be_hidden()
    visible_selectors = (
        HPL.BUTTON_UTUB_TAG_CREATE,
        HPL.LIST_TAGS,
        HPL.BUTTON_UNSELECT_ALL,
    )
    for visible_elem_selector in visible_selectors:
        visible_elem = page.locator(visible_elem_selector).first
        expect(visible_elem).to_be_visible()
        expect(visible_elem).to_be_enabled()


def assert_new_utub_tag_created(
    *, page: Page, new_tag_str: str, init_utub_tag_count: int
) -> None:
    assert_create_utub_tag_input_form_is_hidden(page=page)
    utub_tag_container = wait_then_get_element(page=page, css_selector=HPL.LIST_TAGS)
    assert utub_tag_container is not None
    utub_tags = utub_tag_container.locator(HPL.TAG_FILTERS).all()
    assert len(utub_tags) == init_utub_tag_count + 1
    utub_tag_spans = utub_tag_container.locator(f"{HPL.TAG_FILTERS} span").all()
    assert new_tag_str in [tag_span.inner_text() for tag_span in utub_tag_spans]


def assert_delete_utub_tag_modal_shown(*, page: Page, tag_id: int, app: Flask) -> None:
    warning_modal = wait_then_get_element(page=page, css_selector=HPL.HOME_MODAL)
    assert warning_modal is not None
    expect(warning_modal).to_be_visible()
    warning_modal_body = warning_modal.locator(HPL.BODY_MODAL)
    confirmation_modal_body_text = warning_modal_body.inner_text()
    utub_tag_delete_check_text = DELETE_UTUB_TAG_WARNING
    utub_tag = get_tag_in_utub(app, tag_id)
    utub_tag_delete_check_text = utub_tag_delete_check_text.replace(
        "{{ tag_string }}", f"'{utub_tag.tag_string}'"
    )
    assert confirmation_modal_body_text == utub_tag_delete_check_text
