from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend import db
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS as UTS
from tests.functional.db_utils import (
    add_tag_to_utub_user_created,
    get_utub_this_user_created,
)
from tests.functional.locators import HomePageLocators as HPL
from tests.functional.playwright_assert_utils import assert_panel_visibility_mobile
from tests.functional.playwright_login_utils import (
    login_user_and_select_utub_by_utubid_mobile,
)
from tests.functional.playwright_utils import (
    Decks,
    click_on_navbar,
    get_all_url_ids_in_selected_utub,
    wait_for_class_to_be_removed,
    wait_then_click_element,
)
from tests.functional.tags_ui.playwright_utils import (
    apply_tag_filter_based_on_id,
    wait_until_tag_sheet_collapsed,
    wait_until_tag_sheet_open,
)
from tests.functional.urls_ui.playwright_assert_utils import (
    assert_urls_are_multi_selected,
)

pytestmark = [pytest.mark.urls_ui, pytest.mark.mobile_ui]

USER_ID_FOR_TEST = 1

# The collapsed tag-sheet peek (--tag-sheet-peek: 3rem = 48px) pokes this many
# px above the sheet viewport's bottom edge when shown. In selection mode the
# whole sheet is transformed off-screen (translateY(100%)) so the gap collapses
# to ~0 — the assertion boundary the two waiters below use.
_PEEK_SHOWN_MIN_GAP_PX = 20
_PEEK_SUPPRESSED_MAX_GAP_PX = 4

_TAG_SHEET_PEEK_GAP_JS = """() => {
    const handle = document.querySelector('#tagSheetHandle');
    const viewport = document.querySelector('#tagSheetViewport');
    if (!handle || !viewport) return null;
    const handleRect = handle.getBoundingClientRect();
    const viewportRect = viewport.getBoundingClientRect();
    return viewportRect.bottom - handleRect.top;
}"""


def _wait_tag_sheet_peek_shown(*, page: Page) -> None:
    """Wait until the collapsed tag-sheet peek pokes above the viewport bottom
    (the normal on-URL-deck resting state, not in selection mode)."""
    page.wait_for_function(
        f"() => {{ const gap = ({_TAG_SHEET_PEEK_GAP_JS})();"
        f" return gap !== null && gap >= {_PEEK_SHOWN_MIN_GAP_PX}; }}"
    )


def _wait_tag_sheet_peek_suppressed(*, page: Page) -> None:
    """Wait until the collapsed tag-sheet peek is slid fully off-screen — the
    DD-11 double-drawer dissolution while multi-select mode is active."""
    page.wait_for_function(
        f"() => {{ const gap = ({_TAG_SHEET_PEEK_GAP_JS})();"
        f" return gap !== null && gap <= {_PEEK_SUPPRESSED_MAX_GAP_PX}; }}"
    )


def _seed_tag_on_all_but_last_url(
    *, app: Flask, utub_id: int, tag_string: str
) -> tuple[int, int]:
    """Add a UTub tag and apply it to every URL except the last, so filtering by
    it hides exactly one (still-selected) row. Returns (tag_id, num_tagged)."""
    tag = add_tag_to_utub_user_created(app, utub_id, USER_ID_FOR_TEST, tag_string)
    tag_id = tag.id
    with app.app_context():
        utub_urls: list[Utub_Urls] = (
            Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id)
            .order_by(Utub_Urls.id)
            .all()
        )
        urls_to_tag = utub_urls[:-1]
        for utub_url in urls_to_tag:
            db.session.add(
                Utub_Url_Tags(
                    utub_id=utub_id, utub_url_id=utub_url.id, utub_tag_id=tag_id
                )
            )
        db.session.commit()
        num_tagged = len(urls_to_tag)
    return tag_id, num_tagged


def _enter_multi_select_mode(*, page: Page) -> None:
    """Tap the header toggle and settle into multi-select mode (bottom-docked
    bar visible, aria-pressed reflecting the pressed state)."""
    toggle = page.locator(HPL.BUTTON_MULTI_SELECT_TOGGLE)
    expect(toggle).to_be_visible()
    toggle.click()
    expect(toggle).to_have_attribute("aria-pressed", "true")
    expect(page.locator(HPL.BULK_ACTION_BAR)).to_be_visible()


def _tap_url_checkbox(*, page: Page, utub_url_id: int) -> None:
    """Tap a row's 44px multi-select checkbox to toggle that row's selection."""
    checkbox_selector = (
        f"{HPL.ROWS_URLS}[utuburlid='{utub_url_id}'] {HPL.URL_SELECT_CHECKBOX}"
    )
    page.locator(checkbox_selector).first.click()


def test_mobile_bulk_bar_appears_and_checkbox_toggles(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a logged-in mobile user on the URL deck
    WHEN they enter multi-select mode and tap a 44px row checkbox
    THEN the bottom-docked bulk bar appears and the checkbox tap toggles the
        row's selection on, then off
    """
    page = page_mobile_portrait
    app = provide_app
    utub: Utubs = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    url_ids = get_all_url_ids_in_selected_utub(page=page)
    assert len(url_ids) >= 1

    _enter_multi_select_mode(page=page)
    expect(page.locator(HPL.URL_SELECT_CHECKBOX).first).to_be_visible()

    _tap_url_checkbox(page=page, utub_url_id=url_ids[0])
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("1")
    expect(page.locator(HPL.ROW_MULTI_SELECTED)).to_have_count(1)
    assert_urls_are_multi_selected(page=page, utub_url_ids=[url_ids[0]])

    _tap_url_checkbox(page=page, utub_url_id=url_ids[0])
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("0")
    expect(page.locator(HPL.ROW_MULTI_SELECTED)).to_have_count(0)


def test_mobile_switching_panel_exits_mode(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a mobile user with a live multi-selection on the URL deck
    WHEN they switch to another panel (fires MOBILE_DECK_SWITCHED)
    THEN multi-select mode exits: the bar hides and no rows remain marked
    """
    page = page_mobile_portrait
    app = provide_app
    utub: Utubs = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    url_ids = get_all_url_ids_in_selected_utub(page=page)
    assert len(url_ids) >= 1

    _enter_multi_select_mode(page=page)
    _tap_url_checkbox(page=page, utub_url_id=url_ids[0])
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("1")

    # Switch to the Members panel via the mobile navbar.
    click_on_navbar(page=page)
    wait_then_click_element(page=page, css_selector=HPL.NAVBAR_MEMBER_DECK)
    wait_for_class_to_be_removed(
        page=page, css_selector=HPL.NAVBAR_DROPDOWN, class_name="collapsing"
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.MEMBERS)

    expect(page.locator(HPL.BULK_ACTION_BAR)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_MULTI_SELECT_TOGGLE)).to_have_attribute(
        "aria-pressed", "false"
    )
    expect(page.locator(HPL.ROW_MULTI_SELECTED)).to_have_count(0)


def test_mobile_back_button_exits_mode(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a mobile user with a live multi-selection on the URL deck
    WHEN they press the browser Back button (leaving the URL deck)
    THEN multi-select mode exits: the bar hides and no rows remain marked
    """
    page = page_mobile_portrait
    app = provide_app
    utub: Utubs = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    url_ids = get_all_url_ids_in_selected_utub(page=page)
    assert len(url_ids) >= 1

    _enter_multi_select_mode(page=page)
    _tap_url_checkbox(page=page, utub_url_id=url_ids[0])
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("1")

    # Back leaves the selected UTub's URL deck for the pre-selection UTub list,
    # deselecting the UTub and firing the deck switch — both exit multi-select.
    page.go_back()
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.UTUBS)

    expect(page.locator(HPL.BULK_ACTION_BAR)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_MULTI_SELECT_TOGGLE)).to_have_attribute(
        "aria-pressed", "false"
    )
    expect(page.locator(HPL.ROW_MULTI_SELECTED)).to_have_count(0)


def test_mobile_tag_sheet_peek_suppressed_in_mode_icon_opens_and_filters(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a mobile user on the URL deck of a UTub whose URLs are partly tagged
    WHEN they enter multi-select mode, select every row, then filter by tag via
        the header #bulkTagFilterIcon
    THEN the persistent tag-sheet peek is suppressed in mode (no double drawer);
        the icon opens the sheet on demand; applying a tag filter hides the
        untagged (still-selected) row while the selection count is unchanged and
        the hidden hint surfaces it; and closing the sheet + Exit restores the
        peek.
    """
    page = page_mobile_portrait
    app = provide_app
    utub: Utubs = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    tag_id, num_tagged = _seed_tag_on_all_but_last_url(
        app=app, utub_id=utub.id, tag_string=UTS.TEST_TAG_NAME_1
    )

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    url_ids = get_all_url_ids_in_selected_utub(page=page)
    total_urls = len(url_ids)
    assert total_urls >= 2
    expected_hidden = total_urls - num_tagged
    assert expected_hidden == 1

    # Before mode: the collapsed tag-sheet peek pokes above the deck (its normal
    # resting state).
    _wait_tag_sheet_peek_shown(page=page)

    _enter_multi_select_mode(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BULK_SELECT_ALL)
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text(str(total_urls))
    assert_urls_are_multi_selected(page=page, utub_url_ids=url_ids)

    # In mode: the peek is slid off-screen (no second bottom drawer) and the
    # mobile tag-filter icon is revealed.
    _wait_tag_sheet_peek_suppressed(page=page)
    expect(page.locator(HPL.BULK_TAG_FILTER_ICON)).to_be_visible()

    # Tap the icon to open the sheet on demand, then filter by the seeded tag.
    wait_then_click_element(page=page, css_selector=HPL.BULK_TAG_FILTER_ICON)
    wait_until_tag_sheet_open(page=page)
    expect(page.locator(HPL.BULK_TAG_FILTER_ICON)).to_have_attribute(
        "aria-expanded", "true"
    )
    apply_tag_filter_based_on_id(page=page, utub_tag_id=tag_id)

    # The untagged row is hidden but the full selection survives; the count is
    # unchanged and the hidden hint surfaces the newly-hidden selection.
    expect(page.locator(HPL.ROW_VISIBLE_URL)).to_have_count(num_tagged)
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text(str(total_urls))
    expect(page.locator(HPL.ROW_MULTI_SELECTED)).to_have_count(total_urls)
    assert_urls_are_multi_selected(page=page, utub_url_ids=url_ids)
    hidden_hint = page.locator(HPL.BULK_SELECT_HIDDEN_HINT)
    expect(hidden_hint).to_be_visible()
    expect(hidden_hint).to_have_text(
        UTS.URL_BULK_N_HIDDEN.replace("{n}", str(expected_hidden))
    )

    # Close the sheet (tap its handle) — still in mode, so the peek stays
    # suppressed — then Exit restores the peek and single-select.
    wait_then_click_element(page=page, css_selector=HPL.TAG_SHEET_HANDLE)
    wait_until_tag_sheet_collapsed(page=page)
    _wait_tag_sheet_peek_suppressed(page=page)

    wait_then_click_element(page=page, css_selector=HPL.BULK_SELECT_EXIT)
    expect(page.locator(HPL.BULK_ACTION_BAR)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_MULTI_SELECT_TOGGLE)).to_have_attribute(
        "aria-pressed", "false"
    )
    expect(page.locator(HPL.ROW_MULTI_SELECTED)).to_have_count(0)
    _wait_tag_sheet_peek_shown(page=page)
