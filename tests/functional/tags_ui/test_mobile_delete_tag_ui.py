from flask import Flask
import pytest
from playwright.sync_api import Page

from tests.functional.db_utils import (
    get_tag_on_url_in_utub,
    get_url_in_utub,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import assert_panel_visibility_mobile
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import (
    Decks,
    get_selected_url,
    wait_for_element_to_be_removed,
    wait_then_click_element,
    wait_until_visible_css_selector,
)
from tests.functional.tags_ui.playwright_utils import (
    get_tag_badge_selector_on_selected_url_by_tag_id,
)

pytestmark = [pytest.mark.tags_ui, pytest.mark.mobile_ui]


def test_delete_tag_mobile(
    page_mobile_portrait: Page, create_test_tags, provide_app: Flask
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
    app = provide_app
    user_id_for_test = 1
    utub_user_created = get_utub_this_user_created(app, user_id_for_test)
    utub_id = utub_user_created.id
    url_in_utub = get_url_in_utub(app, utub_id)
    url_id = url_in_utub.id
    url_tag = get_tag_on_url_in_utub(app, utub_id, url_id)
    tag_id = url_tag.utub_tag_id

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page_mobile_portrait, user_id=user_id_for_test, utub_id=utub_id
    )
    assert_panel_visibility_mobile(page=page_mobile_portrait, visible_deck=Decks.URLS)

    wait_then_click_element(
        page=page_mobile_portrait,
        css_selector=f"{HPL.ROWS_URLS}[utuburlid='{url_id}']",
    )
    assert get_selected_url(page=page_mobile_portrait) is not None

    tag_badge_selector = get_tag_badge_selector_on_selected_url_by_tag_id(
        url_tag_id=tag_id
    )
    tag_badge = page_mobile_portrait.locator(tag_badge_selector).first
    delete_tag_selector = f"{tag_badge_selector} {HPL.BUTTON_TAG_DELETE}"

    # Before-state: the delete "×" is hidden at rest (clean, label-only tags).
    delete_tag_button = page_mobile_portrait.locator(delete_tag_selector).first
    assert not delete_tag_button.is_visible()

    # Tapping the tag reveals its "×" without closing the card.
    wait_then_click_element(page=page_mobile_portrait, css_selector=tag_badge_selector)
    wait_until_visible_css_selector(
        page=page_mobile_portrait, css_selector=delete_tag_selector
    )
    assert page_mobile_portrait.locator(HPL.ROW_SELECTED_URL).first.is_visible()

    # Tapping the revealed "×" deletes the tag.
    wait_then_click_element(page=page_mobile_portrait, css_selector=delete_tag_selector)
    wait_for_element_to_be_removed(page=page_mobile_portrait, locator=tag_badge)
    assert page_mobile_portrait.locator(tag_badge_selector).count() == 0

    # The URL card must stay open (selected) after deleting the tag.
    assert page_mobile_portrait.locator(HPL.ROW_SELECTED_URL).first.is_visible()
