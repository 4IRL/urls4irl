from flask import Flask
import pytest
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from tests.functional.assert_utils import assert_panel_visibility_mobile
from tests.functional.db_utils import (
    get_tag_on_url_in_utub,
    get_url_in_utub,
    get_utub_this_user_created,
)
from tests.functional.login_utils import login_user_and_select_utub_by_utubid_mobile
from tests.functional.tags_ui.selenium_utils import (
    get_tag_badge_selector_on_selected_url_by_tag_id,
)
from tests.functional.selenium_utils import (
    Decks,
    get_selected_url,
    wait_for_element_to_be_removed,
    wait_then_click_element,
    wait_until_visible_css_selector,
)
from locators import HomePageLocators as HPL

pytestmark = [pytest.mark.tags_ui, pytest.mark.mobile_ui]


def test_delete_tag_mobile(
    browser_mobile_portrait: WebDriver, create_test_tags, provide_app: Flask
):
    """
    Tests a user's ability to delete a tag from a URL on a mobile (coarse-pointer)
    device, where there is no hover state to reveal the delete button.

    GIVEN a user views a selected URL with a tag on a mobile device
    WHEN the user taps the tag (revealing its "×") and then taps the "×"
    THEN the tag's "×" reveals on tap, the URL card stays open throughout, and
         tapping the "×" removes the tag

    Red before the fix: the delete "×" is hover-gated (excluded on coarse-pointer
    devices), so it never reveals and tapping the tag instead closes the card.
    Green after: tapping a tag reveals its "×" without closing the card, and
    tapping the "×" deletes the tag.
    """
    browser = browser_mobile_portrait
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    utub_id = utub_user_created.id
    url_in_utub = get_url_in_utub(app, utub_id)
    url_id = url_in_utub.id
    url_tag = get_tag_on_url_in_utub(app, utub_id, url_id)
    tag_id = url_tag.utub_tag_id

    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, user_id=user_id_for_test, utub_id=utub_id
    )
    assert_panel_visibility_mobile(browser=browser, visible_deck=Decks.URLS)

    wait_then_click_element(browser, f"{HPL.ROWS_URLS}[utuburlid='{url_id}']")
    assert get_selected_url(browser) is not None

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(tag_id)
    tag_badge = browser.find_element(By.CSS_SELECTOR, tag_badge_selector)
    delete_tag_selector = f"{tag_badge_selector} {HPL.BUTTON_TAG_DELETE}"

    # Before-state: the delete "×" is hidden at rest (clean, label-only tags).
    delete_tag_button = browser.find_element(By.CSS_SELECTOR, delete_tag_selector)
    assert not delete_tag_button.is_displayed()

    # Tapping the tag reveals its "×" without closing the card.
    wait_then_click_element(browser, tag_badge_selector)
    wait_until_visible_css_selector(browser, delete_tag_selector, timeout=3)
    assert browser.find_element(By.CSS_SELECTOR, HPL.ROW_SELECTED_URL).is_displayed()

    # Tapping the revealed "×" deletes the tag.
    wait_then_click_element(browser, delete_tag_selector)
    wait_for_element_to_be_removed(browser, tag_badge, timeout=3)
    with pytest.raises(NoSuchElementException):
        browser.find_element(By.CSS_SELECTOR, tag_badge_selector)

    # The URL card must stay open (selected) after deleting the tag.
    assert browser.find_element(By.CSS_SELECTOR, HPL.ROW_SELECTED_URL).is_displayed()
