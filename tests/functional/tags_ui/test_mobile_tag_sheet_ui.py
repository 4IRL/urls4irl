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
    click_on_navbar,
    wait_then_click_element,
    wait_until_in_focus,
)
from tests.functional.tags_ui.selenium_utils import (
    apply_tag_filter_based_on_id,
    swipe_tag_sheet_closed,
    swipe_tag_sheet_open,
    swipe_tag_sheet_up_below_threshold,
    wait_until_tag_sheet_collapsed,
    wait_until_tag_sheet_open,
)

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
        then tap the handle again to close it
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

    # Before-state: sheet collapsed to its peek (header lip visible) on the URL deck.
    wait_until_tag_sheet_collapsed(browser)
    assert_visible_css_selector(browser, HPL.TAG_SHEET_HANDLE)

    # Tap the handle to open the sheet; wait_until_tag_sheet_open gates on the
    # open class AND the slide settling, so a following tag-row tap does not land
    # on a still-moving target.
    wait_then_click_element(browser, HPL.TAG_SHEET_HANDLE)
    wait_until_tag_sheet_open(browser)

    # Sheet overlays the URL deck — the URL deck stays visible behind it.
    assert_visible_css_selector(browser, HPL.URL_DECK)

    # Apply a tag filter; URL rows filter live behind the open sheet.
    apply_tag_filter_based_on_id(browser, tag_id)
    _wait_until_visible_url_count(browser, num_urls_tagged)
    assert len(_visible_url_rows(browser)) == num_urls_tagged

    # Tap the handle again to close (toggle); sheet collapses, filter persists.
    wait_then_click_element(browser, HPL.TAG_SHEET_HANDLE)
    wait_until_tag_sheet_collapsed(browser)

    # The handle's count badge surfaces the active-filter count on the collapsed
    # peek (it is hidden on the slimmed handle while the sheet is open, so it is
    # asserted here, after collapse).
    handle_count = browser.find_element(By.CSS_SELECTOR, HPL.TAG_SHEET_HANDLE_COUNT)
    assert HIDDEN_CLASS not in (handle_count.get_attribute("class") or "")
    assert handle_count.text == EXPECTED_SINGLE_FILTER_COUNT_TEXT

    _wait_until_visible_url_count(browser, num_urls_tagged)
    assert len(_visible_url_rows(browser)) == num_urls_tagged


def test_tag_sheet_opens_over_url_deck_from_member_deck(
    browser_mobile_portrait: WebDriver, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user who has navigated to the Member deck
    WHEN they tap Tags in the navbar
    THEN the app switches to the URL deck and opens the tag sheet over it — the
        sheet must never overlay the Member deck
    """
    browser = browser_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )

    # Navigate to the Member deck first.
    click_on_navbar(browser)
    wait_then_click_element(browser, HPL.NAVBAR_MEMBER_DECK)
    assert_panel_visibility_mobile(browser, visible_deck=Decks.MEMBERS)

    # Tap Tags in the navbar.
    click_on_navbar(browser)
    wait_then_click_element(browser, HPL.NAVBAR_TAGS_DECK)

    # The sheet opens over the URL deck, not the Member deck.
    wait_until_tag_sheet_open(browser)
    assert_visible_css_selector(browser, HPL.URL_DECK)
    assert_not_visible_css_selector(browser, HPL.MEMBER_DECK)


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

    wait_until_tag_sheet_collapsed(browser)
    wait_then_click_element(browser, HPL.TAG_SHEET_HANDLE)
    wait_until_tag_sheet_open(browser)

    # The backdrop spans all of <main> but the sheet overlays its bottom 62%, so a
    # default pointer click at the element center would land on the sheet, and
    # offset clicks are unreliable across drivers (center- vs top-left-origin
    # ambiguity). The backdrop's own click handler is the unit under test, so
    # dispatch a real click directly on the backdrop element.
    backdrop = browser.find_element(By.CSS_SELECTOR, HPL.TAG_SHEET_BACKDROP)
    browser.execute_script("arguments[0].click();", backdrop)

    wait_until_tag_sheet_collapsed(browser)


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
    GIVEN the tag sheet is open on mobile with focus on the handle
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

    wait_until_tag_sheet_collapsed(browser)
    wait_then_click_element(browser, HPL.TAG_SHEET_HANDLE)
    wait_until_tag_sheet_open(browser)

    # Focus moves to the handle on open; wait for it before sending ESC so the
    # keydown lands on a focused element (per the flake-hardening rule).
    wait_until_in_focus(browser, HPL.TAG_SHEET_HANDLE)
    browser.switch_to.active_element.send_keys(Keys.ESCAPE)

    wait_until_tag_sheet_collapsed(browser)

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
    wait_until_tag_sheet_open(browser)

    assert_visible_css_selector(browser, HPL.TAG_SHEET_EMPTY)


def test_tag_sheet_swipe_open_and_close(
    browser_mobile_portrait: WebDriver, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user on the URL deck with the tag sheet closed
    WHEN they swipe up from the peeking handle, then swipe down from the handle
    THEN the sheet opens on the upward swipe and closes on the downward swipe,
        proving the real browser commits the drag gesture end-to-end
    """
    browser = browser_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(browser=browser, visible_deck=Decks.URLS)

    # Before-state: sheet collapsed to its peek, handle ready to be dragged up.
    wait_until_tag_sheet_collapsed(browser)
    assert_visible_css_selector(browser, HPL.TAG_SHEET_HANDLE)

    # Swipe up from the handle to commit the open gesture.
    swipe_tag_sheet_open(browser)
    wait_until_tag_sheet_open(browser)

    # Swipe down from the handle to commit the close gesture.
    swipe_tag_sheet_closed(browser)
    wait_until_tag_sheet_collapsed(browser)


def test_tag_sheet_swipe_below_threshold_snaps_back_closed(
    browser_mobile_portrait: WebDriver, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user on the URL deck with the tag sheet collapsed
    WHEN they swipe up from the peeking handle by a small amount well below the
        ~35% commit threshold (sub-threshold drag)
    THEN the sheet snaps back to its collapsed peek and does not open, proving the
        real browser only commits the open gesture once the threshold is crossed
    """
    browser = browser_mobile_portrait
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, browser=browser, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(browser=browser, visible_deck=Decks.URLS)

    # Before-state: sheet collapsed to its peek, handle ready to be dragged up.
    wait_until_tag_sheet_collapsed(browser)
    assert_visible_css_selector(browser, HPL.TAG_SHEET_HANDLE)

    # Swipe up only a short distance (below the commit threshold).
    swipe_tag_sheet_up_below_threshold(browser)

    # The sheet must snap back to collapsed; it must NOT open. Asserting the
    # collapsed wait passes (open class absent + slide settled) confirms snap-back.
    wait_until_tag_sheet_collapsed(browser)
