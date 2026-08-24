from flask import Flask
import pytest
from playwright.sync_api import Page, expect

from backend import db
from backend.models.urls import Urls
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
from tests.functional.urls_ui.playwright_utils import (
    enter_multi_select_mode,
    tap_url_checkbox,
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


def _seed_url_in_utub(
    *, app: Flask, utub_id: int, user_id: int, url_string: str, url_title: str
) -> int:
    """Insert a globally-unique URL + a `Utub_Urls` row authored by `user_id` (so
    it is deletable by that user, letting the drawer's Delete action render) into
    the given UTub. Returns the new utub_url_id."""
    with app.app_context():
        raw_url: Urls | None = Urls.query.filter(Urls.url_string == url_string).first()
        if raw_url is None:
            raw_url = Urls(normalized_url=url_string, current_user_id=user_id)
            db.session.add(raw_url)
            db.session.flush()
        new_utub_url = Utub_Urls(
            utub_id=utub_id,
            url_id=raw_url.id,
            user_id=user_id,
            url_title=url_title,
        )
        db.session.add(new_utub_url)
        db.session.flush()
        new_id = new_utub_url.id
        db.session.commit()
        return new_id


def test_mobile_last_url_row_reachable_above_bulk_drawer(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a mobile user on a URL deck long enough to overflow the viewport
    WHEN they enter multi-select mode and Select All — so the multi-row drawer
        renders every row (Add tags + Delete, the full-width Copy row, and
        Select All / Clear) — then scroll the URL deck to the bottom
    THEN the last URL row sits directly ABOVE the in-flow bulk-action bar with
        no dead scroll space between them, AND the PAGE itself does not scroll
        (the deck is viewport-capped and its `.flex-column.content` is the sole
        scroller). The bar is an in-flow last child of #URLDeck (not fixed), so
        the scroll container shrinks to the space above it. Two regressions are
        guarded: (1) the last row must not be overlapped by the bar; (2) the last
        row's bottom must sit within a few px of the bar's top — a large gap means
        the obsolete `--tag-sheet-peek` bottom padding is still reserving ~48px of
        dead space in multi-select (where the tag-sheet peek is slid off-screen);
        (3) the body must be capped to the dynamic viewport so the whole page can
        never over-scroll past the list into the footer (iOS Safari regression).
    """
    page = page_mobile_portrait
    app = provide_app
    utub: Utubs = get_utub_this_user_created(app, USER_ID_FOR_TEST)

    # Seed enough deletable (user-authored) URLs to overflow the 900px viewport so
    # the last row is only reachable by scrolling past the docked drawer.
    for index in range(15):
        _seed_url_in_utub(
            app=app,
            utub_id=utub.id,
            user_id=USER_ID_FOR_TEST,
            url_string=f"https://bulk-drawer-overflow-{index}.test/",
            url_title=f"Bulk Drawer Overflow {index}",
        )

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    url_ids = get_all_url_ids_in_selected_utub(page=page)
    assert len(url_ids) >= 15

    enter_multi_select_mode(page=page)
    # Select every row so all three drawer rows render: Add tags + Delete (Delete
    # needs >=1 deletable selection), the full-width Copy row (other UTubs exist),
    # and the Select All / Clear row.
    wait_then_click_element(page=page, css_selector=HPL.BULK_SELECT_ALL)
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text(str(len(url_ids)))

    # Confirm the multi-row drawer is fully rendered (taller than the old 88px).
    expect(page.locator(HPL.BUTTON_BULK_ADD_TAGS)).to_be_visible()
    expect(page.locator(HPL.BUTTON_BULK_DELETE_URLS)).to_be_visible()
    expect(page.locator(HPL.BUTTON_BULK_COPY_URLS)).to_be_visible()
    expect(page.locator(HPL.BULK_SELECT_ALL)).to_be_visible()
    expect(page.locator(HPL.BULK_SELECT_CLEAR)).to_be_visible()

    # Scroll the URL deck's scroll container (`.flex-column.content`,
    # overflow-y:auto) to the very bottom.
    page.evaluate("""() => {
            const content = document.querySelector('#URLDeck .flex-column.content');
            content.scrollTop = content.scrollHeight;
        }""")

    # The last URL row must clear the docked drawer: its bottom edge sits at/above
    # the drawer's top edge (2px sub-pixel tolerance). wait_for_function lets the
    # scroll + reservation reflow settle; the Python assertion re-checks with the
    # bounding boxes so a failure reports the actual overlap.
    page.wait_for_function("""() => {
            const rows = document.querySelectorAll('.urlRow');
            const row = rows[rows.length - 1];
            const bar = document.querySelector('#bulkActionBar');
            if (!row || !bar) return false;
            const rowRect = row.getBoundingClientRect();
            const barRect = bar.getBoundingClientRect();
            return rowRect.bottom <= barRect.top + 2;
        }""")

    last_row_box = page.locator(HPL.ROWS_URLS).last.bounding_box()
    bar_box = page.locator(HPL.BULK_ACTION_BAR).bounding_box()
    assert last_row_box is not None and bar_box is not None
    last_row_bottom = last_row_box["y"] + last_row_box["height"]
    gap_to_bar = bar_box["y"] - last_row_bottom
    # (1) The last row must not be overlapped by the bar.
    assert last_row_bottom <= bar_box["y"] + 2, (
        "Last URL row is overlapped by the bulk-action drawer: row bottom "
        f"{last_row_bottom} > drawer top {bar_box['y']}"
    )
    # (2) No dead space: the last row's bottom sits within a few px of the bar's
    # top (the scroller keeps only its base ~3px padding + 2px border). A gap the
    # size of --tag-sheet-peek (~48px) means that obsolete reservation leaked into
    # multi-select, where the tag-sheet peek is slid off-screen.
    assert gap_to_bar <= 12, (
        "Dead scroll space between the last URL row and the bulk-action bar: gap "
        f"{gap_to_bar}px (row bottom {last_row_bottom}, bar top {bar_box['y']}). "
        "The obsolete --tag-sheet-peek padding is likely still reserved in mode."
    )

    # (3) The page itself must not over-scroll. Attempt to scroll the window past
    # its end; the deck is viewport-capped so the scrolling element stays at 0 and
    # its scroll height never exceeds the client height (the footer can never be
    # dragged up into the deck view).
    page_scroll = page.evaluate("""() => {
            window.scrollTo(0, 999999);
            const el = document.scrollingElement || document.documentElement;
            return {
                scrollTop: el.scrollTop,
                overflow: el.scrollHeight - el.clientHeight,
            };
        }""")
    assert page_scroll["scrollTop"] <= 1, (
        f"Page over-scrolled (scrollTop={page_scroll['scrollTop']}): the deck is "
        "not viewport-capped, so the whole page scrolls past the URL list."
    )
    assert page_scroll["overflow"] <= 1, (
        f"Page is taller than the viewport (overflow={page_scroll['overflow']}px): "
        "the body is not capped to the dynamic viewport, letting the footer intrude."
    )


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

    enter_multi_select_mode(page=page)
    expect(page.locator(HPL.URL_SELECT_CHECKBOX).first).to_be_visible()

    tap_url_checkbox(page=page, utub_url_id=url_ids[0])
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("1")
    expect(page.locator(HPL.ROW_MULTI_SELECTED)).to_have_count(1)
    assert_urls_are_multi_selected(page=page, utub_url_ids=[url_ids[0]])

    tap_url_checkbox(page=page, utub_url_id=url_ids[0])
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("0")
    expect(page.locator(HPL.ROW_MULTI_SELECTED)).to_have_count(0)


def test_mobile_range_strip_absent_drawer_keeps_select_all_clear(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a mobile user in multi-select mode
    THEN the desktop-only subheader range strip (#bulkSelectRangeStrip) is NOT
        visible, and the bottom drawer still exposes its own Select All / Clear
        (#bulkSelectAll / #bulkSelectClear) — the mobile drawer is unchanged
        (DD-4); the strip is a desktop-only addition.
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

    enter_multi_select_mode(page=page)

    # The desktop range strip never renders on mobile (force-hidden < 992px).
    expect(page.locator(HPL.BULK_SELECT_RANGE_STRIP)).to_be_hidden()

    # The drawer's own Select All / Clear stay present and visible on mobile.
    expect(page.locator(HPL.BULK_SELECT_ALL)).to_be_visible()
    expect(page.locator(HPL.BULK_SELECT_CLEAR)).to_be_visible()


def test_mobile_backgrounding_app_does_not_expand_selected_card(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a mobile user in multi-select mode with a URL selected (its card holds
        focus, as after tapping the checkbox)
    WHEN the browser app is backgrounded then refocused (window blur then focus)
    THEN the selected card must NOT auto-expand — regression: the visibility blur
        handler used to flip urlselected=true on the focused card, reopening it
        (tags + action buttons) on return, corrupting the selection view.
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

    enter_multi_select_mode(page=page)
    tap_url_checkbox(page=page, utub_url_id=url_ids[0])
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("1")

    # Simulate backgrounding + returning to the app while the selected card holds
    # focus (mobile Safari fires window blur then focus). closest('.urlRow')
    # resolves to this row whether a child or the row itself is the activeElement.
    page.evaluate(
        """(utubUrlId) => {
            const row = document.querySelector(
                `.urlRow[utuburlid="${utubUrlId}"]`
            );
            row.setAttribute('tabindex', '-1');
            row.focus();
            window.dispatchEvent(new Event('blur'));
            window.dispatchEvent(new Event('focus'));
        }""",
        url_ids[0],
    )

    # The card stays collapsed (never urlselected=true) and still selected.
    expect(
        page.locator(f'.urlRow[utuburlid="{url_ids[0]}"][urlselected="true"]')
    ).to_have_count(0)
    expect(page.locator(HPL.BULK_SELECT_COUNT)).to_have_text("1")
    expect(page.locator(HPL.ROW_MULTI_SELECTED)).to_have_count(1)


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

    enter_multi_select_mode(page=page)
    tap_url_checkbox(page=page, utub_url_id=url_ids[0])
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

    enter_multi_select_mode(page=page)
    tap_url_checkbox(page=page, utub_url_id=url_ids[0])
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

    enter_multi_select_mode(page=page)
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


def test_mobile_tag_sheet_is_filter_only_in_mode_full_toolbar_normally(
    page_mobile_portrait: Page, create_test_urls, provide_app: Flask
):
    """
    GIVEN a mobile user on the URL deck of a UTub that has a tag
    WHEN they open the tag sheet DURING multi-select mode (via #bulkTagFilterIcon)
    THEN the sheet is filter-only: the tag-management controls #utubTagBtnCreate,
        #utubTagBtnUpdateAllOpen, and the per-tag .utubTagBtnDelete are hidden;
    AND WHEN the sheet is later opened normally (mode inactive)
    THEN those management controls are available again (#utubTagBtnCreate +
        #utubTagBtnUpdateAllOpen visible, and the edit-tags toggle reveals the
        per-tag .utubTagBtnDelete).
    """
    page = page_mobile_portrait
    app = provide_app
    utub: Utubs = get_utub_this_user_created(app, USER_ID_FOR_TEST)
    # Seed a UTub tag so the tag deck renders a row (and its .utubTagBtnDelete).
    _seed_tag_on_all_but_last_url(
        app=app, utub_id=utub.id, tag_string=UTS.TEST_TAG_NAME_1
    )

    login_user_and_select_utub_by_utubid_mobile(
        app=app, page=page, user_id=USER_ID_FOR_TEST, utub_id=utub.id
    )
    assert_panel_visibility_mobile(page=page, visible_deck=Decks.URLS)

    # --- In multi-select mode: the tag sheet is filter-only. ---
    enter_multi_select_mode(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BULK_TAG_FILTER_ICON)
    wait_until_tag_sheet_open(page=page)

    expect(page.locator(HPL.BUTTON_UTUB_TAG_CREATE)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_UPDATE_TAG_BTN_ALL_OPEN)).to_be_hidden()
    expect(page.locator(HPL.BUTTON_UTUB_TAG_DELETE).first).to_be_hidden()

    # Close the sheet, then Exit mode.
    wait_then_click_element(page=page, css_selector=HPL.TAG_SHEET_HANDLE)
    wait_until_tag_sheet_collapsed(page=page)
    wait_then_click_element(page=page, css_selector=HPL.BULK_SELECT_EXIT)
    expect(page.locator(HPL.BULK_ACTION_BAR)).to_be_hidden()

    # --- Opened normally (mode inactive): the full toolbar is available. ---
    wait_then_click_element(page=page, css_selector=HPL.TAG_SHEET_HANDLE)
    wait_until_tag_sheet_open(page=page)

    expect(page.locator(HPL.BUTTON_UTUB_TAG_CREATE)).to_be_visible()
    expect(page.locator(HPL.BUTTON_UPDATE_TAG_BTN_ALL_OPEN)).to_be_visible()

    # The per-tag delete lives in the edit-tags ("update all") sub-toolbar; open
    # it to confirm the delete control is reachable when NOT in selection mode.
    wait_then_click_element(page=page, css_selector=HPL.BUTTON_UPDATE_TAG_BTN_ALL_OPEN)
    expect(page.locator(HPL.BUTTON_UTUB_TAG_DELETE).first).to_be_visible()
