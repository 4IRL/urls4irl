from __future__ import annotations

from flask import Flask
import pytest
from playwright.sync_api import Locator, Page

from backend import db
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import (
    add_tag_to_utub_user_created,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import (
    assert_not_visible_css_selector,
    assert_panel_visibility_mobile,
    assert_visible_css_selector,
)
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import (
    Decks,
    click_on_navbar,
    wait_then_click_element,
    wait_until_in_focus,
)
from tests.functional.tags_ui.playwright_utils import (
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


def _visible_url_rows(*, page: Page) -> list[Locator]:
    return [
        url_row for url_row in page.locator(HPL.ROWS_URLS).all() if url_row.is_visible()
    ]


def _wait_until_visible_url_count(
    *, page: Page, expected: int, timeout: int = 3
) -> None:
    """Tag filtering updates URL-row visibility asynchronously via the
    TAG_FILTER_CHANGED event after the tag is tapped; counting rows immediately
    races that DOM update under parallel load. Gate on the expected count first.
    """
    page.wait_for_function(
        """({ selector, expected }) => {
            const rows = document.querySelectorAll(selector);
            const visible = Array.from(rows).filter(
                r => r.offsetParent !== null &&
                     getComputedStyle(r).display !== 'none' &&
                     getComputedStyle(r).visibility !== 'hidden'
            ).length;
            return visible === expected;
        }""",
        arg={"selector": HPL.ROWS_URLS, "expected": expected},
        timeout=timeout * 1000,
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
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user on the URL deck of a UTub with tagged URLs
    WHEN they tap the peeking handle to open the tag sheet, apply a tag filter,
        then tap the handle again to close it
    THEN the sheet and URL deck show simultaneously, URL rows filter live behind
        the sheet, the handle count badge shows "1", and the filter persists after
        the sheet closes
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    tag_id, num_urls_tagged = _add_tag_to_subset_of_urls(
        app, utub.id, UTS.TEST_TAG_NAME_1
    )

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page_mobile_portrait, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page_mobile_portrait, visible_deck=Decks.URLS)

    # Before-state: sheet collapsed to its peek (header lip visible) on the URL deck.
    wait_until_tag_sheet_collapsed(page=page_mobile_portrait)
    assert_visible_css_selector(
        page=page_mobile_portrait, css_selector=HPL.TAG_SHEET_HANDLE
    )

    # Tap the handle to open the sheet; wait_until_tag_sheet_open gates on the
    # open class AND the slide settling, so a following tag-row tap does not land
    # on a still-moving target.
    wait_then_click_element(
        page=page_mobile_portrait, css_selector=HPL.TAG_SHEET_HANDLE
    )
    wait_until_tag_sheet_open(page=page_mobile_portrait)

    # Sheet overlays the URL deck — the URL deck stays visible behind it.
    assert_visible_css_selector(page=page_mobile_portrait, css_selector=HPL.URL_DECK)

    # Apply a tag filter; URL rows filter live behind the open sheet.
    apply_tag_filter_based_on_id(page=page_mobile_portrait, utub_tag_id=tag_id)
    _wait_until_visible_url_count(page=page_mobile_portrait, expected=num_urls_tagged)
    assert len(_visible_url_rows(page=page_mobile_portrait)) == num_urls_tagged

    # Tap the handle again to close (toggle); sheet collapses, filter persists.
    wait_then_click_element(
        page=page_mobile_portrait, css_selector=HPL.TAG_SHEET_HANDLE
    )
    wait_until_tag_sheet_collapsed(page=page_mobile_portrait)

    # The handle's count badge surfaces the active-filter count on the collapsed
    # peek (it is hidden on the slimmed handle while the sheet is open, so it is
    # asserted here, after collapse).
    handle_count = page_mobile_portrait.locator(HPL.TAG_SHEET_HANDLE_COUNT).first
    handle_count_classes = handle_count.get_attribute("class") or ""
    assert HIDDEN_CLASS not in handle_count_classes
    assert handle_count.inner_text() == EXPECTED_SINGLE_FILTER_COUNT_TEXT

    _wait_until_visible_url_count(page=page_mobile_portrait, expected=num_urls_tagged)
    assert len(_visible_url_rows(page=page_mobile_portrait)) == num_urls_tagged


def test_create_utub_tag_buttons_sit_below_input_mobile(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    Regression test for issue #424 (tag-create half of the fix): on mobile the
    create-UTub-tag submit/cancel row must sit directly beneath the tag input
    rather than growing to fill the deck and pinning to its bottom, so the
    on-screen keyboard raised by the autofocused input does not hide the buttons.
    On mobile the Tag deck (with the create-tag control) is relocated into the
    bottom sheet, so the form is opened by opening the sheet then tapping create.

    GIVEN a logged-in mobile user on the URL deck of one of their UTubs
    WHEN they open the tag sheet and open the create-tag form
    THEN the submit (check) button sits immediately below the tag input, not
        anchored to the bottom of the sheet
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page_mobile_portrait, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page_mobile_portrait, visible_deck=Decks.URLS)

    # The Tag deck lives inside the bottom sheet on mobile; open it before the
    # create control is interactable (the sheet body is visibility:hidden while
    # collapsed). wait_until_tag_sheet_open gates on the slide settling.
    wait_until_tag_sheet_collapsed(page=page_mobile_portrait)
    wait_then_click_element(
        page=page_mobile_portrait, css_selector=HPL.TAG_SHEET_HANDLE
    )
    wait_until_tag_sheet_open(page=page_mobile_portrait)

    wait_then_click_element(
        page=page_mobile_portrait, css_selector=HPL.BUTTON_UTUB_TAG_CREATE
    )
    wait_until_in_focus(
        page=page_mobile_portrait, css_selector=HPL.INPUT_UTUB_TAG_CREATE
    )

    input_box = page_mobile_portrait.locator(HPL.INPUT_UTUB_TAG_CREATE).bounding_box()
    submit_box = page_mobile_portrait.locator(
        HPL.BUTTON_UTUB_TAG_SUBMIT_CREATE
    ).bounding_box()
    assert input_box is not None
    assert submit_box is not None

    input_bottom = input_box["y"] + input_box["height"]
    gap_below_input = submit_box["y"] - input_bottom

    # Same fixed layout as the UTub-create form: the wrap's 20px row-gap separates
    # the input from the button row on coarse pointers. The ceiling absorbs
    # sub-pixel/padding slack while still catching the pre-fix layout, where the
    # row grew and bottom-anchored to the sheet with the buttons behind the
    # keyboard.
    assert 0 <= gap_below_input <= 80, (
        "Create-tag submit button should sit directly below the tag input on "
        f"mobile; gap was {gap_below_input}px"
    )


def test_tag_sheet_opens_over_url_deck_from_member_deck(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user who has navigated to the Member deck
    WHEN they tap Tags in the navbar
    THEN the app switches to the URL deck and opens the tag sheet over it — the
        sheet must never overlay the Member deck
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page_mobile_portrait, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )

    # Navigate to the Member deck first.
    click_on_navbar(page=page_mobile_portrait)
    wait_then_click_element(
        page=page_mobile_portrait, css_selector=HPL.NAVBAR_MEMBER_DECK
    )
    assert_panel_visibility_mobile(
        page=page_mobile_portrait, visible_deck=Decks.MEMBERS
    )

    # Tap Tags in the navbar.
    click_on_navbar(page=page_mobile_portrait)
    wait_then_click_element(
        page=page_mobile_portrait, css_selector=HPL.NAVBAR_TAGS_DECK
    )

    # The sheet opens over the URL deck, not the Member deck.
    wait_until_tag_sheet_open(page=page_mobile_portrait)
    assert_visible_css_selector(page=page_mobile_portrait, css_selector=HPL.URL_DECK)
    assert_not_visible_css_selector(
        page=page_mobile_portrait, css_selector=HPL.MEMBER_DECK
    )


def test_tag_sheet_close_via_backdrop(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the tag sheet is open on mobile
    WHEN the user taps the dimmed backdrop
    THEN the sheet closes
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page_mobile_portrait, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page_mobile_portrait, visible_deck=Decks.URLS)

    wait_until_tag_sheet_collapsed(page=page_mobile_portrait)
    wait_then_click_element(
        page=page_mobile_portrait, css_selector=HPL.TAG_SHEET_HANDLE
    )
    wait_until_tag_sheet_open(page=page_mobile_portrait)

    # The backdrop spans all of <main> but the sheet overlays its bottom 62%, so a
    # default pointer click at the element center would land on the sheet, and
    # offset clicks are unreliable across drivers (center- vs top-left-origin
    # ambiguity). The backdrop's own click handler is the unit under test, so
    # dispatch a real click directly on the backdrop element.
    backdrop = page_mobile_portrait.locator(HPL.TAG_SHEET_BACKDROP).first
    backdrop.evaluate("element => element.click()")

    wait_until_tag_sheet_collapsed(page=page_mobile_portrait)


def test_tag_sheet_handle_count_hidden_with_no_selection(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user on the URL deck with no tag filter applied
    WHEN they view the peeking handle
    THEN the handle count badge is hidden (no count shown without a selection)
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page_mobile_portrait, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page_mobile_portrait, visible_deck=Decks.URLS)

    assert_visible_css_selector(
        page=page_mobile_portrait, css_selector=HPL.TAG_SHEET_HANDLE
    )
    handle_count = page_mobile_portrait.locator(HPL.TAG_SHEET_HANDLE_COUNT).first
    handle_count_classes = handle_count.get_attribute("class") or ""
    assert HIDDEN_CLASS in handle_count_classes


def test_tag_sheet_close_via_escape(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN the tag sheet is open on mobile with focus on the handle
    WHEN the user presses Escape
    THEN the sheet closes and focus returns to the handle that opened it
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page_mobile_portrait, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page_mobile_portrait, visible_deck=Decks.URLS)

    wait_until_tag_sheet_collapsed(page=page_mobile_portrait)
    wait_then_click_element(
        page=page_mobile_portrait, css_selector=HPL.TAG_SHEET_HANDLE
    )
    wait_until_tag_sheet_open(page=page_mobile_portrait)

    # Focus moves to the handle on open; wait for it before sending ESC so the
    # keydown lands on a focused element (per the flake-hardening rule).
    wait_until_in_focus(page=page_mobile_portrait, css_selector=HPL.TAG_SHEET_HANDLE)
    page_mobile_portrait.keyboard.press("Escape")

    wait_until_tag_sheet_collapsed(page=page_mobile_portrait)

    # Opener-based focus restore (WCAG 2.4.3): focus returns to the handle.
    wait_until_in_focus(page=page_mobile_portrait, css_selector=HPL.TAG_SHEET_HANDLE)


def test_tag_sheet_empty_state_no_tags(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user on a UTub that has URLs but no tags
    WHEN they open the tag sheet
    THEN the inline empty-state message is shown
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page_mobile_portrait, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page_mobile_portrait, visible_deck=Decks.URLS)

    wait_then_click_element(
        page=page_mobile_portrait, css_selector=HPL.TAG_SHEET_HANDLE
    )
    wait_until_tag_sheet_open(page=page_mobile_portrait)

    assert_visible_css_selector(
        page=page_mobile_portrait, css_selector=HPL.TAG_SHEET_EMPTY
    )


def test_tag_sheet_swipe_open_and_close(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user on the URL deck with the tag sheet closed
    WHEN they swipe up from the peeking handle, then swipe down from the handle
    THEN the sheet opens on the upward swipe and closes on the downward swipe,
        proving the real browser commits the drag gesture end-to-end
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page_mobile_portrait, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page_mobile_portrait, visible_deck=Decks.URLS)

    # Before-state: sheet collapsed to its peek, handle ready to be dragged up.
    wait_until_tag_sheet_collapsed(page=page_mobile_portrait)
    assert_visible_css_selector(
        page=page_mobile_portrait, css_selector=HPL.TAG_SHEET_HANDLE
    )

    # Swipe up from the handle to commit the open gesture.
    swipe_tag_sheet_open(page=page_mobile_portrait)
    wait_until_tag_sheet_open(page=page_mobile_portrait)

    # Swipe down from the handle to commit the close gesture.
    swipe_tag_sheet_closed(page=page_mobile_portrait)
    wait_until_tag_sheet_collapsed(page=page_mobile_portrait)


def test_tag_sheet_swipe_below_threshold_snaps_back_closed(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user on the URL deck with the tag sheet collapsed
    WHEN they swipe up from the peeking handle by a small amount well below the
        ~35% commit threshold (sub-threshold drag)
    THEN the sheet snaps back to its collapsed peek and does not open, proving the
        real browser only commits the open gesture once the threshold is crossed
    """
    app = provide_app
    utub = get_utub_this_user_created(app, USER_ID_FOR_TEST)

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page_mobile_portrait, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page_mobile_portrait, visible_deck=Decks.URLS)

    # Before-state: sheet collapsed to its peek, handle ready to be dragged up.
    wait_until_tag_sheet_collapsed(page=page_mobile_portrait)
    assert_visible_css_selector(
        page=page_mobile_portrait, css_selector=HPL.TAG_SHEET_HANDLE
    )

    # Swipe up only a short distance (below the commit threshold).
    swipe_tag_sheet_up_below_threshold(page=page_mobile_portrait)

    # The sheet must snap back to collapsed; it must NOT open. Asserting the
    # collapsed wait passes (open class absent + slide settled) confirms snap-back.
    wait_until_tag_sheet_collapsed(page=page_mobile_portrait)
