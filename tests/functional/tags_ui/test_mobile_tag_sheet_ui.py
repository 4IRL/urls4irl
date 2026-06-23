from flask import Flask
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.wait import WebDriverWait

from backend import db
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.assert_utils import (
    assert_not_visible_css_selector,
    assert_panel_visibility_mobile,
    assert_visible_css_selector,
)
from tests.functional.db_utils import (
    add_tag_to_utub_user_created,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.login_utils import login_user_and_select_utub_by_utubid_mobile
from tests.functional.selenium_utils import (
    Decks,
    wait_then_click_element,
    wait_until_hidden,
    wait_until_in_focus,
    wait_until_visible_css_selector,
)
from tests.functional.tags_ui.selenium_utils import apply_tag_filter_based_on_id

pytestmark = [pytest.mark.tags_ui, pytest.mark.mobile_ui]

USER_ID_FOR_TEST = 1
HIDDEN_CLASS = "hidden"
EXPECTED_SINGLE_FILTER_COUNT_TEXT = "1"


def _visible_url_rows(browser: WebDriver) -> list:
    return [
        url_row
        for url_row in browser.find_elements(By.CSS_SELECTOR, HPL.ROWS_URLS)
        if url_row.is_displayed()
    ]


def _wait_until_visible_url_count(
    browser: WebDriver, expected: int, timeout: int = 3
) -> None:
    """Tag filtering updates URL-row visibility asynchronously via the
    TAG_FILTER_CHANGED event after the tag is tapped; counting rows immediately
    races that DOM update under parallel load. Gate on the expected count first.
    """
    WebDriverWait(browser, timeout).until(
        lambda driver: len(_visible_url_rows(driver)) == expected
    )


def _add_tag_to_subset_of_urls(
    app: Flask, utub_id: int, tag_string: str
) -> tuple[int, int]:
    """
    Adds a single UTub tag and applies it to all-but-the-last URL in the UTub so
    that filtering by it produces a deterministic, partial result set.

    Returns:
        (utub_tag_id, number_of_urls_the_tag_was_applied_to)
    """
    tag = add_tag_to_utub_user_created(app, utub_id, USER_ID_FOR_TEST, tag_string)
    tag_id = tag.id
    with app.app_context():
        utub_urls: list[Utub_Urls] = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id
        ).all()
        urls_to_tag = utub_urls[: len(utub_urls) - 1]
        for utub_url in urls_to_tag:
            db.session.add(
                Utub_Url_Tags(
                    utub_id=utub_id,
                    utub_url_id=utub_url.id,
                    utub_tag_id=tag_id,
                )
            )
        db.session.commit()
        num_urls_tagged = len(urls_to_tag)

    return tag_id, num_urls_tagged


def test_tag_sheet_happy_path_open_filter_close(
    browser_mobile_portrait: WebDriver, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user on the URL deck of a UTub with tagged URLs
    WHEN they tap the peeking handle to open the tag sheet, apply a tag filter,
        then close the sheet via the grabber
    THEN the sheet and URL deck show simultaneously, URL rows filter live behind
        the sheet, the handle count badge shows "1", and the filter persists after
        the sheet closes
    """
    browser = browser_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    tag_id, num_urls_tagged = _add_tag_to_subset_of_urls(
        app, utub.id, UTS.TEST_TAG_NAME_1
    )

    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(browser=browser, visible_deck=Decks.URLS)

    # Before-state: sheet closed, handle peeks in the URL-showing state.
    assert_not_visible_css_selector(browser, HPL.TAG_SHEET)
    assert_visible_css_selector(browser, HPL.TAG_SHEET_HANDLE)

    # Tap the handle to open the sheet.
    wait_then_click_element(browser, HPL.TAG_SHEET_HANDLE)
    wait_until_visible_css_selector(browser, HPL.TAG_SHEET)

    # Sheet overlays the URL deck — both visible simultaneously (NOT a single deck).
    assert_visible_css_selector(browser, HPL.TAG_SHEET)
    assert_visible_css_selector(browser, HPL.URL_DECK)

    # Apply a tag filter; URL rows filter live and the handle count shows "1".
    apply_tag_filter_based_on_id(browser, tag_id)
    _wait_until_visible_url_count(browser, num_urls_tagged)
    assert len(_visible_url_rows(browser)) == num_urls_tagged

    handle_count = browser.find_element(By.CSS_SELECTOR, HPL.TAG_SHEET_HANDLE_COUNT)
    assert HIDDEN_CLASS not in (handle_count.get_attribute("class") or "")
    assert handle_count.text == EXPECTED_SINGLE_FILTER_COUNT_TEXT

    # Close via the grabber; sheet hides and the filter persists.
    wait_then_click_element(browser, HPL.TAG_SHEET_GRABBER)
    wait_until_hidden(browser, HPL.TAG_SHEET)
    assert_not_visible_css_selector(browser, HPL.TAG_SHEET)

    _wait_until_visible_url_count(browser, num_urls_tagged)
    assert len(_visible_url_rows(browser)) == num_urls_tagged


def test_tag_sheet_close_via_backdrop(
    browser_mobile_portrait: WebDriver, create_test_urls, provide_app: Flask
):
    """
    GIVEN the tag sheet is open on mobile
    WHEN the user taps the dimmed backdrop
    THEN the sheet closes
    """
    browser = browser_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(browser=browser, visible_deck=Decks.URLS)

    assert_not_visible_css_selector(browser, HPL.TAG_SHEET)
    wait_then_click_element(browser, HPL.TAG_SHEET_HANDLE)
    wait_until_visible_css_selector(browser, HPL.TAG_SHEET)

    # The backdrop spans all of <main> but the sheet overlays its bottom 62%, so a
    # default pointer click at the element center would land on the sheet, and
    # offset clicks are unreliable across drivers (center- vs top-left-origin
    # ambiguity). The backdrop's own click handler is the unit under test, so
    # dispatch a real click directly on the backdrop element.
    backdrop = browser.find_element(By.CSS_SELECTOR, HPL.TAG_SHEET_BACKDROP)
    browser.execute_script("arguments[0].click();", backdrop)

    wait_until_hidden(browser, HPL.TAG_SHEET)
    assert_not_visible_css_selector(browser, HPL.TAG_SHEET)


def test_tag_sheet_handle_count_hidden_with_no_selection(
    browser_mobile_portrait: WebDriver, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user on the URL deck with no tag filter applied
    WHEN they view the peeking handle
    THEN the handle count badge is hidden (no count shown without a selection)
    """
    browser = browser_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(browser=browser, visible_deck=Decks.URLS)

    assert_visible_css_selector(browser, HPL.TAG_SHEET_HANDLE)
    handle_count = browser.find_element(By.CSS_SELECTOR, HPL.TAG_SHEET_HANDLE_COUNT)
    assert HIDDEN_CLASS in (handle_count.get_attribute("class") or "")


def test_tag_sheet_close_via_escape(
    browser_mobile_portrait: WebDriver, create_test_urls, provide_app: Flask
):
    """
    GIVEN the tag sheet is open on mobile with focus on the grabber
    WHEN the user presses Escape
    THEN the sheet closes and focus returns to the handle that opened it
    """
    browser = browser_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(browser=browser, visible_deck=Decks.URLS)

    assert_not_visible_css_selector(browser, HPL.TAG_SHEET)
    wait_then_click_element(browser, HPL.TAG_SHEET_HANDLE)
    wait_until_visible_css_selector(browser, HPL.TAG_SHEET)

    # Focus moves to the grabber on open; wait for it before sending ESC so the
    # keydown lands on a focused element (per the flake-hardening rule).
    wait_until_in_focus(browser, HPL.TAG_SHEET_GRABBER)
    browser.switch_to.active_element.send_keys(Keys.ESCAPE)

    wait_until_hidden(browser, HPL.TAG_SHEET)
    assert_not_visible_css_selector(browser, HPL.TAG_SHEET)

    # Opener-based focus restore (WCAG 2.4.3): focus returns to the handle.
    wait_until_in_focus(browser, HPL.TAG_SHEET_HANDLE)


def test_tag_sheet_empty_state_no_tags(
    browser_mobile_portrait: WebDriver, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user on a UTub that has URLs but no tags
    WHEN they open the tag sheet
    THEN the inline empty-state message is shown
    """
    browser = browser_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(browser=browser, visible_deck=Decks.URLS)

    wait_then_click_element(browser, HPL.TAG_SHEET_HANDLE)
    wait_until_visible_css_selector(browser, HPL.TAG_SHEET)

    assert_visible_css_selector(browser, HPL.TAG_SHEET_EMPTY)
