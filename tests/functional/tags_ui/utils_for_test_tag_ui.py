from typing import Tuple

from flask import Flask
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from src import db
from src.models.utub_tags import Utub_Tags
from src.models.utub_urls import Utub_Urls
from src.models.utub_url_tags import Utub_Url_Tags
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.utils_for_test import (
    clear_then_send_keys,
    login_user_and_select_utub_by_name,
    login_user_and_select_utub_by_utubid,
    wait_then_click_element,
    wait_then_get_element,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)


# CREATE
def add_tag_to_url(browser: WebDriver, selected_url_id: int, tag_string: str) -> None:
    """
    Once logged in, with users, UTub, and URLs this function initiates the action to create one tag applied to the selected URL in the selected UTub.
    """
    open_url_tag_input(browser, selected_url_id)
    input_url_tag_selector = f"{HPL.ROW_SELECTED_URL} {HPL.INPUT_TAG_CREATE}"

    create_tag_input = browser.find_element(By.CSS_SELECTOR, input_url_tag_selector)
    assert create_tag_input.is_displayed()
    clear_then_send_keys(create_tag_input, tag_string)


def add_tag_to_utub_user_created(
    app: Flask, utub_id: int, user_id: int, tag_string: str
) -> Utub_Tags:
    with app.app_context():
        new_tag: Utub_Tags = Utub_Tags(
            utub_id=utub_id, tag_string=tag_string, created_by=user_id
        )
        db.session.add(new_tag)
        db.session.commit()

        return Utub_Tags.query.filter(Utub_Tags.tag_string == tag_string).first()


def add_two_tags_across_urls_in_utub(
    app: Flask, utub_id: int, first_tag_id: int, second_tag_id: int
) -> Tuple[int, int, int]:
    with app.app_context():
        utub_urls: list[Utub_Urls] = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id
        ).all()
        num_utub_urls = len(utub_urls)
        urls_for_first_tag = utub_urls[: len(utub_urls) - 1]
        num_urls_for_first_tag = len(urls_for_first_tag)
        urls_for_second_tag = urls_for_first_tag[: len(urls_for_first_tag) // 2]
        num_urls_for_second_tag = len(urls_for_second_tag)

        for first_tag_url in urls_for_first_tag:
            url_id = first_tag_url.id
            new_url_tag = Utub_Url_Tags(
                utub_id=utub_id, utub_url_id=url_id, utub_tag_id=first_tag_id
            )
            db.session.add(new_url_tag)

            if first_tag_url in urls_for_second_tag:
                new_url_tag = Utub_Url_Tags(
                    utub_id=utub_id, utub_url_id=url_id, utub_tag_id=second_tag_id
                )
                db.session.add(new_url_tag)
        db.session.commit()
        return num_utub_urls, num_urls_for_first_tag, num_urls_for_second_tag


# READ
def get_tag_string_already_on_url_in_utub_and_delete(
    app: Flask, utub_id: int, utub_url_id: int
) -> str:
    with app.app_context():
        utub_url_tag: Utub_Url_Tags = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id, Utub_Url_Tags.utub_url_id == utub_url_id
        ).all()
        tag_string = utub_url_tag[0].utub_tag_item.tag_string
        db.session.delete(utub_url_tag[1])
        db.session.commit()
        return tag_string


def get_tag_on_url_in_utub(app: Flask, utub_id: int, utub_url_id: int) -> Utub_Url_Tags:
    with app.app_context():
        return Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id, Utub_Url_Tags.utub_url_id == utub_url_id
        ).first()


def get_urls_count_with_tag_applied_from_tag_filter_by_tag_id(
    browser: WebDriver, tag_id: int
) -> int:
    """
    Extracts the count of URLs that have a specific tag applied from the Tag Deck assocaited tag filter based on the tag ID.
    """
    tag_filter = browser.find_element(
        By.CSS_SELECTOR, get_utub_tag_filter_selector(tag_id)
    )
    tag_filter_count_elem = tag_filter.find_element(By.CSS_SELECTOR, f"{HPL.TAG_COUNT}")
    tag_filter_count = int(tag_filter_count_elem.text)
    return tag_filter_count if tag_filter_count else 0


def count_urls_with_tag_applied_by_tag_id(
    app: Flask,
    tag_id: int,
) -> int:
    """
    Counts the number of URLs displayed with a specific tag applied by its ID.
    """
    with app.app_context():
        return Utub_Url_Tags.query.filter(Utub_Url_Tags.utub_tag_id == tag_id).count()


def count_urls_with_tag_applied_by_tag_string(
    app: Flask,
    utub_id: int,
    tag_text: int,
) -> int:
    """
    Counts the number of URLs displayed with a specific tag applied by its string and UTub ID.
    """
    with app.app_context():
        utub_tag: Utub_Tags = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_id,
            Utub_Tags.tag_string == tag_text,
        ).first()

        return (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id,
                Utub_Url_Tags.utub_tag_id == utub_tag.id,
            ).count()
            if utub_tag
            else 0
        )


# UPDATE
def apply_tag_filter_by_id_and_get_shown_urls(
    browser: WebDriver, utub_tag_id: int
) -> list[WebElement]:
    apply_tag_filter_based_on_id(browser, utub_tag_id)
    url_row_elements = browser.find_elements(By.CSS_SELECTOR, HPL.ROWS_URLS)
    return [url_row for url_row in url_row_elements if url_row.is_displayed()]


# DELETE
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


# CSS SELECTORS
def get_tag_badge_selector_on_selected_url_by_tag_id(url_tag_id: int) -> str:
    return f"{HPL.ROW_SELECTED_URL} {HPL.TAG_BADGES}[{HPL.TAG_BADGE_ID_ATTRIB}='{url_tag_id}']"


def get_utub_tag_filter_selector(utub_tag_id: int) -> str:
    return f"{HPL.TAG_FILTERS}[data-utub-tag-id='{utub_tag_id}']"


# OPERATION
def login_user_select_utub_by_id_open_create_utub_tag(
    app: Flask, browser: WebDriver, user_id: int, utub_id: int
):
    login_user_and_select_utub_by_utubid(app, browser, user_id, utub_id)
    wait_then_click_element(browser, HPL.BUTTON_UTUB_TAG_CREATE)


def login_user_select_utub_by_name_open_create_utub_tag(
    app: Flask, browser: WebDriver, user_id: int, utub_name: str
):
    login_user_and_select_utub_by_name(app, browser, user_id, utub_name)
    wait_then_click_element(browser, HPL.BUTTON_UTUB_TAG_CREATE)


def open_url_tag_input(browser: WebDriver, selected_url_id: int):
    url_selector = f"{HPL.ROWS_URLS}[utuburlid='{selected_url_id}']"

    open_tag_input_selector = f"{url_selector} {HPL.BUTTON_TAG_CREATE}"
    wait_then_click_element(browser, open_tag_input_selector, time=3)

    url_tag_input_selector = f"{url_selector} {HPL.INPUT_TAG_CREATE}"
    wait_until_visible_css_selector(browser, url_tag_input_selector, timeout=3)

    wait_until_in_focus(browser, url_tag_input_selector, timeout=3)


def apply_tag_filter_based_on_id(browser: WebDriver, utub_tag_id: int):
    utub_tag_filter = get_utub_tag_filter_selector(utub_tag_id)
    wait_then_click_element(browser, utub_tag_filter, time=3)


# VERIFICATION
def verify_create_utub_tag_input_form_is_hidden(browser: WebDriver):
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


def verify_new_utub_tag_created(
    browser: WebDriver, new_tag_str: str, init_utub_tag_count: int
):
    verify_create_utub_tag_input_form_is_hidden(browser)

    utub_tag_container = wait_then_get_element(browser, HPL.LIST_TAGS)
    assert utub_tag_container is not None

    utub_tags = utub_tag_container.find_elements(By.CSS_SELECTOR, HPL.TAG_FILTERS)
    assert len(utub_tags) == init_utub_tag_count + 1

    # Verify the text of the new tag is found in a tag element
    utub_tag_spans = utub_tag_container.find_elements(
        By.CSS_SELECTOR, HPL.TAG_FILTERS + " span"
    )
    assert new_tag_str in [tag.text for tag in utub_tag_spans]


def verify_btns_shown_on_cancel_url_tag_input_creator(browser: WebDriver):
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


def verify_btns_shown_on_cancel_url_tag_input_member(browser: WebDriver):
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


# ASSERTION
def assert_unselect_all_tag_filters_disabled(browser: WebDriver):
    unselect_all_selector = browser.find_element(
        By.CSS_SELECTOR, HPL.BUTTON_UNSELECT_ALL
    )

    # Assert Unselect All filter is disabled
    assert "disabled" in unselect_all_selector.get_attribute("class").split()
